"""Tests for the training data shown by the web server."""
import json
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from bottle import TEMPLATE_PATH
from bottle import HTTPError
from fsrs import State

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.server.annotations import AcademyCaseContext
from term_timer.server.annotations import AcademyStepContext
from term_timer.server.annotations import AttemptsCurve
from term_timer.server.annotations import CaseTrainingPanel
from term_timer.server.annotations import ForgettingCurve
from term_timer.server.annotations import StepTrainingSummary
from term_timer.server.annotations import TrainingBannerInfo
from term_timer.server.app import Server
from term_timer.server.views import AcademyCaseView
from term_timer.server.views import AcademyStepView
from term_timer.server.views import SessionListView
from term_timer.server.views import TrainingForecastView
from term_timer.server.views import TrainingReviewView

NOW = datetime.now(UTC)


def card_data(
        state: State,
        due: timedelta,
        last_review: timedelta | None,
        stability: float | None = 3.0,
) -> dict[str, Any]:
    """
    Serialize an FSRS card the way training files store it.

    Args:
        state: FSRS state of the card.
        due: Due date relative to now.
        last_review: Last review relative to now, None when never reviewed.
        stability: Stability of the card in days.

    Returns:
        Raw fsrs entry of a training file.

    """
    return {
        'card_id': 1,
        'state': state.value,
        'step': None if state == State.Review else 0,
        'stability': stability,
        'difficulty': 5.0 if stability is not None else None,
        'due': (NOW + due).isoformat(),
        'last_review': (
            (NOW + last_review).isoformat()
            if last_review is not None else None
        ),
    }


class TrainingServerTestCase(unittest.TestCase):
    """Point the trainings directory at a temporary folder."""

    @classmethod
    def setUpClass(cls) -> None:
        """Register the templates of the web server."""
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)

    def setUp(self) -> None:
        """Patch the trainings directory."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name) / 'trainings'

        patcher = patch(
            'term_timer.in_out.TRAININGS_DIRECTORY', self.directory,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_step(self, step: str, content: dict[str, Any] | str) -> None:
        """
        Write the training file of a CFOP step.

        Args:
            step: Step name, as the file is named (OLL, PLL...).
            content: Cases of the file, or raw text for a corrupted one.

        """
        folder = self.directory / 'CFOP'
        folder.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content)
        (folder / f'{ step }.json').write_text(text, encoding='utf-8')


class TestAcademyCaseTraining(TrainingServerTestCase):
    """The case page shows the personal training of the case."""

    @staticmethod
    def context() -> AcademyCaseContext:
        """
        Build the context of the CFOP/OLL 27 case page.

        Returns:
            Context of the academy case view.

        """
        return AcademyCaseView('CFOP', 'OLL', '27', '').get_context()

    def panel(self) -> CaseTrainingPanel:
        """
        Build the training panel of the CFOP/OLL 27 case page.

        Returns:
            The panel, failing the test when there is none.

        """
        panel = self.context()['training']
        if panel is None:
            self.fail('No training panel')
        return panel

    def curve(self) -> AttemptsCurve:
        """
        Build the attempts curve of the training panel.

        Returns:
            The curve, failing the test when there is none.

        """
        curve = self.panel()['curve']
        if curve is None:
            self.fail('No attempts curve')
        return curve

    def forgetting(self) -> ForgettingCurve:
        """
        Build the forgetting curve of the training panel.

        Returns:
            The curve, failing the test when there is none.

        """
        forgetting = self.panel()['forgetting']
        if forgetting is None:
            self.fail('No forgetting curve')
        return forgetting

    def test_without_training_file(self) -> None:
        """No training file means no panel, and no error."""
        context = self.context()

        self.assertIsNone(context['training'])
        self.assertFalse(context['training_unavailable'])

    def test_case_never_trained(self) -> None:
        """A case absent from the training file has no panel."""
        self.write_step('OLL', {
            '21': {'last_date': 1790000000, 'timings': [1500]},
        })

        context = self.context()

        self.assertIsNone(context['training'])
        self.assertFalse(context['training_unavailable'])

    def test_truncated_file(self) -> None:
        """A file cut during a write is reported unavailable."""
        self.write_step('OLL', '{"27": {"last_da')

        context = self.context()

        self.assertIsNone(context['training'])
        self.assertTrue(context['training_unavailable'])

    def test_timings_without_card(self) -> None:
        """Timings saved before FSRS show as a New case with no memory."""
        self.write_step('OLL', {
            '27': {'last_date': 1790000000, 'timings': [2000, 1500, 1800]},
        })

        panel = self.panel()

        self.assertEqual(panel['attempts'], 3)
        self.assertEqual(panel['state_label'], 'New')
        self.assertEqual(panel['best'], 1_500_000_000)
        self.assertIsNone(panel['forgetting'])
        self.assertFalse(panel['overdue'])
        curve = self.curve()
        self.assertEqual(curve['labels'], ['1', '2', '3'])
        self.assertEqual(curve['times'], [2.0, 1.5, 1.8])
        self.assertEqual(curve['ao5'], [None, None, None])
        self.assertIsNone(curve['peak'])

    def test_rolling_averages(self) -> None:
        """Rolling Ao5 and Ao12 start once enough attempts exist."""
        timings = [1000 + index * 10 for index in range(13)]
        self.write_step('OLL', {
            '27': {'last_date': 1790000000, 'timings': timings},
        })

        curve = self.curve()

        self.assertIsNone(curve['ao5'][3])
        self.assertIsNotNone(curve['ao5'][4])
        self.assertIsNone(curve['ao12'][10])
        self.assertIsNotNone(curve['ao12'][11])
        self.assertIsNotNone(curve['peak'])

    def test_overdue_card(self) -> None:
        """An overdue review card says so and draws its memory decay."""
        self.write_step('OLL', {
            '27': {
                'last_date': 1790000000,
                'timings': [1500],
                'fsrs': card_data(
                    State.Review, timedelta(days=-2), timedelta(days=-6),
                ),
            },
        })

        panel = self.panel()

        self.assertTrue(panel['overdue'])
        self.assertEqual(panel['state_label'], 'Review')
        self.assertEqual(panel['due_relative'], 'overdue by 2 d')
        forgetting = self.forgetting()
        self.assertAlmostEqual(forgetting['points'][0]['y'], 100.0)
        self.assertAlmostEqual(forgetting['today'], 6.0, places=2)
        self.assertAlmostEqual(forgetting['due'], 4.0, places=2)
        self.assertLess(forgetting['retention'], 100.0)
        self.assertGreater(forgetting['points'][-1]['x'], forgetting['today'])

    def test_stable_card(self) -> None:
        """A review scheduled ahead is labelled Stable."""
        self.write_step('OLL', {
            '27': {
                'last_date': 1790000000,
                'timings': [1500],
                'fsrs': card_data(
                    State.Review, timedelta(days=10), timedelta(days=-1),
                ),
            },
        })

        panel = self.panel()

        self.assertEqual(panel['state_label'], 'Stable')
        self.assertEqual(panel['state_class'], 'stable')
        self.assertFalse(panel['overdue'])
        self.assertEqual(panel['due_relative'], 'in 9 d')

    def test_card_never_reviewed(self) -> None:
        """A card without last review has no forgetting curve."""
        self.write_step('OLL', {
            '27': {
                'last_date': 1790000000,
                'timings': [],
                'fsrs': card_data(
                    State.Learning, timedelta(days=1), None, stability=None,
                ),
            },
        })

        panel = self.panel()

        self.assertIsNone(panel['forgetting'])
        self.assertIsNone(panel['curve'])
        self.assertEqual(panel['attempts'], 0)

    def test_page_renders_panel(self) -> None:
        """The case page renders the training panel."""
        self.write_step('OLL', {
            '27': {
                'last_date': 1790000000,
                'timings': [1500, 1400],
                'fsrs': card_data(
                    State.Review, timedelta(days=-2), timedelta(days=-6),
                ),
            },
        })

        html = AcademyCaseView('CFOP', 'OLL', '27', '').as_view(debug=False)

        self.assertIn('id="training"', html)
        self.assertIn('forgettingChart', html)

    def test_page_renders_unavailable(self) -> None:
        """A truncated file renders a notice instead of failing."""
        self.write_step('OLL', '{')

        html = AcademyCaseView('CFOP', 'OLL', '27', '').as_view(debug=False)

        self.assertIn('Training data unavailable', html)


def trained(
        timings: list[int], card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the raw training entry of a case.

    Args:
        timings: Timings of the case in milliseconds.
        card: Raw FSRS card to attach, as built by card_data.

    Returns:
        Raw entry of a training file.

    """
    entry: dict[str, Any] = {'last_date': 1790000000, 'timings': timings}
    if card is not None:
        entry['fsrs'] = card
    return entry


class TestAcademyStepTraining(TrainingServerTestCase):
    """The step page tints each case with its training."""

    @staticmethod
    def context(group: str = '', family: str = '') -> AcademyStepContext:
        """
        Build the context of the CFOP/PLL step page.

        Returns:
            Context of the academy step view.

        """
        return AcademyStepView(
            'CFOP', 'PLL', group, family, '',
        ).get_context()

    def summary(self) -> StepTrainingSummary:
        """
        Build the training summary of the CFOP/PLL step page.

        Returns:
            The summary, failing the test when there is none.

        """
        summary = self.context()['training_summary']
        if summary is None:
            self.fail('No training summary')
        return summary

    def test_without_training_file(self) -> None:
        """No training file: no tile, no summary, no error."""
        context = self.context()

        self.assertEqual(context['training'], {})
        self.assertIsNone(context['training_summary'])
        self.assertFalse(context['training_unavailable'])

    def test_truncated_file(self) -> None:
        """A file cut during a write is reported unavailable."""
        self.write_step('PLL', '{"Aa": ')

        context = self.context()

        self.assertIsNone(context['training_summary'])
        self.assertTrue(context['training_unavailable'])

    def test_tiles(self) -> None:
        """Each trained case gets its state, due badge and Ao5."""
        self.write_step('PLL', {
            'Aa': trained(
                [2000] * 5,
                card_data(
                    State.Review, timedelta(days=-1), timedelta(days=-8),
                ),
            ),
            'Ab': trained([2500]),
        })

        tiles = self.context()['training']

        self.assertEqual(set(tiles), {'Aa', 'Ab'})
        self.assertEqual(tiles['Aa']['state_label'], 'Review')
        self.assertTrue(tiles['Aa']['overdue'])
        self.assertEqual(tiles['Aa']['ao5'], 2_000_000_000)
        self.assertIsNotNone(tiles['Aa']['retention'])
        self.assertEqual(tiles['Ab']['state_label'], 'New')
        self.assertEqual(tiles['Ab']['ao5'], -1)
        self.assertIsNone(tiles['Ab']['retention'])
        self.assertEqual(tiles['Ab']['memory'], '')

    def test_case_outside_collection_ignored(self) -> None:
        """A code of the file unknown to the collection is dropped."""
        self.write_step('PLL', {'Zz': trained([2000])})

        context = self.context()

        self.assertEqual(context['training'], {})

    def test_speed_needs_enough_cases(self) -> None:
        """Under the minimum of timed cases, no speed tint at all."""
        self.write_step('PLL', {
            'Aa': trained([2000] * 5),
            'Ab': trained([4000] * 5),
        })

        tiles = self.context()['training']

        self.assertEqual(tiles['Aa']['speed'], '')
        self.assertEqual(tiles['Ab']['speed'], '')

    def test_speed_relative_to_median(self) -> None:
        """The speed tint compares each Ao5 to the step median."""
        codes = ['Aa', 'Ab', 'E', 'F', 'Ga', 'Gb', 'Gc']
        times = [1000, 1800, 1950, 2000, 2050, 2200, 4000]
        self.write_step('PLL', {
            code: trained([time] * 5)
            for code, time in zip(codes, times, strict=True)
        })

        tiles = self.context()['training']

        self.assertEqual(tiles['Aa']['speed'], 'fast-2')
        self.assertEqual(tiles['Ab']['speed'], 'fast-1')
        self.assertEqual(tiles['F']['speed'], 'mid')
        self.assertEqual(tiles['Gb']['speed'], 'slow-1')
        self.assertEqual(tiles['Gc']['speed'], 'slow-2')

    def test_summary(self) -> None:
        """The summary counts every case of the step by state."""
        self.write_step('PLL', {
            'Aa': trained(
                [2000, 1800],
                card_data(
                    State.Review, timedelta(days=-1), timedelta(days=-8),
                ),
            ),
            'Ab': trained([2500]),
        })

        summary = self.summary()
        rows = {row['label']: row for row in summary['rows']}

        self.assertEqual(summary['total']['count'], 21)
        self.assertEqual(rows['Review']['count'], 1)
        self.assertEqual(rows['Review']['overdue'], 1)
        self.assertEqual(rows['Review']['best'], 1_800_000_000)
        self.assertEqual(rows['New']['count'], 20)
        self.assertEqual(summary['total']['overdue'], 1)
        self.assertEqual(summary['total']['worst'], 2_500_000_000)
        self.assertAlmostEqual(
            sum(row['share'] for row in summary['rows']), 100.0,
        )
        self.assertNotIn('Stable', rows)

    def test_summary_follows_filter(self) -> None:
        """A family filter restricts the summary to that family."""
        self.write_step('PLL', {'Aa': trained([2000])})

        context = self.context(family='Edges only')
        summary = context['training_summary']
        if summary is None:
            self.fail('No training summary')

        self.assertEqual(summary['total']['count'], len(context['cases']))

    def test_page_renders_tints(self) -> None:
        """The step page renders the tint selector and the summary."""
        self.write_step('PLL', {'Aa': trained([2000])})

        html = AcademyStepView(
            'CFOP', 'PLL', '', '', '',
        ).as_view(debug=False)

        self.assertIn('data-tint="state"', html)
        self.assertIn('training-summary', html)


PARIS = ZoneInfo('Europe/Paris')


def due_card(due: datetime) -> dict[str, Any]:
    """
    Build a trained case whose review falls at an absolute date.

    Returns:
        Raw entry of a training file.

    """
    card = card_data(State.Review, timedelta(0), timedelta(days=-30))
    card['due'] = due.isoformat()
    return {'last_date': 1790000000, 'timings': [2000], 'fsrs': card}


class TestTrainingForecast(TrainingServerTestCase):
    """The forecast counts the reviews of the next days, by step."""

    def test_buckets_by_local_day(self) -> None:
        """Reviews fall on their local day, overdue ones apart."""
        now = datetime(2026, 9, 26, 23, 50, tzinfo=PARIS)
        self.write_step('PLL', {
            'Aa': due_card(now - timedelta(hours=1)),
            'Ab': due_card(now + timedelta(minutes=5)),
            'E': due_card(now + timedelta(minutes=20)),
            'F': due_card(now + timedelta(days=2)),
            'Ga': due_card(now + timedelta(days=30)),
        })

        forecast = TrainingForecastView.build_forecast(
            TrainingForecastView.read_steps(), now,
        )

        self.assertEqual(forecast['labels'][:3], [
            'Overdue', 'Today', 'Tomorrow',
        ])
        self.assertEqual(len(forecast['labels']), 15)
        series = forecast['series'][0]
        self.assertEqual(series['label'], 'PLL')
        self.assertEqual(series['data'][:5], [1, 1, 1, 1, 0])
        self.assertEqual(sum(series['data']), 4)
        self.assertEqual(forecast['later'], 1)

    def test_steps_without_cards_skipped(self) -> None:
        """A step whose file holds no card adds no series."""
        now = datetime.now(PARIS)
        self.write_step('CROSS', {'cross': trained([2000])})
        self.write_step('OLL', {'27': due_card(now + timedelta(days=1))})

        forecast = TrainingForecastView.build_forecast(
            TrainingForecastView.read_steps(), now,
        )

        self.assertEqual(
            [series['label'] for series in forecast['series']], ['OLL'],
        )

    def test_page_renders(self) -> None:
        """The forecast page renders, even without any training."""
        html = TrainingForecastView().as_view(debug=False)

        self.assertIn('No training yet', html)


class TestTrainingBanner(TrainingServerTestCase):
    """The home banner sums up each trained step."""

    def banner(self) -> TrainingBannerInfo:
        """
        Build the training banner of the home page.

        Returns:
            The banner, failing the test when there is none.

        """
        banner = TrainingForecastView.banner()
        if banner is None:
            self.fail('No training banner')
        return banner

    def test_without_trainings(self) -> None:
        """Nothing trained, no banner."""
        self.assertIsNone(TrainingForecastView.banner())

    def test_step_status(self) -> None:
        """Due, new and mastered cases are counted per step."""
        now = datetime.now(UTC)
        mastered = card_data(
            State.Review, timedelta(days=5), timedelta(days=-2),
            stability=30.0,
        )
        self.write_step('PLL', {
            'Aa': due_card(now - timedelta(hours=2)),
            'Ab': {'last_date': 0, 'timings': [1500], 'fsrs': mastered},
            'E': trained([2000]),
        })

        banner = self.banner()
        pll = banner['steps'][0]

        self.assertEqual(pll['step'], 'PLL')
        self.assertEqual(pll['due'], 1)
        self.assertEqual(pll['new'], 19)
        self.assertEqual(pll['mastered'], 1)
        self.assertEqual(pll['total'], 21)
        self.assertTrue(pll['academy'])
        self.assertEqual(banner['due'], 1)

    def test_step_without_academy(self) -> None:
        """A carded step outside the Academy counts its own cases."""
        now = datetime.now(UTC)
        self.write_step('LL', {
            'll': due_card(now - timedelta(hours=2)),
        })

        step = self.banner()['steps'][0]

        self.assertEqual(step['total'], 1)
        self.assertEqual(step['new'], 0)
        self.assertFalse(step['academy'])

    def test_truncated_step(self) -> None:
        """A step being written is listed as unavailable."""
        self.write_step('OLL', '{"01": ')
        self.write_step('PLL', {'Aa': trained([2000])})

        banner = self.banner()

        self.assertEqual(banner['unavailable'], ['OLL'])
        self.assertEqual([step['step'] for step in banner['steps']], ['PLL'])

    def test_home_without_trainings(self) -> None:
        """The home page has no training banner without training."""
        with (
            patch(
                'term_timer.server.views.sessions.load_all_solves',
                return_value=[],
            ),
            patch(
                'term_timer.server.views.sessions.DailyListView.banner',
                return_value={},
            ),
            patch(
                'term_timer.server.views.sessions.load_all_daily_solves',
                return_value=[],
            ),
        ):
            context = SessionListView.get_context()

        self.assertIsNone(context['training'])


class TestTrainingReview(TrainingServerTestCase):
    """The review page shows the due cases as flashcards."""

    def test_due_cases_most_overdue_first(self) -> None:
        """Only due cases are served, the most overdue first."""
        now = datetime.now(UTC)
        self.write_step('PLL', {
            'Aa': due_card(now - timedelta(hours=1)),
            'T': due_card(now - timedelta(days=3)),
            'Ab': due_card(now + timedelta(days=2)),
            'E': trained([2000]),
        })

        cards = TrainingReviewView('CFOP', 'PLL').get_context()['cards']

        self.assertEqual([card['code'] for card in cards], ['T', 'Aa'])
        self.assertEqual(cards[0]['overdue'], 'overdue by 3 d')

    def test_custom_solution_revealed(self) -> None:
        """A solution saved in the training file wins over the main one."""
        entry = due_card(datetime.now(UTC) - timedelta(hours=1))
        entry['solution'] = "R U R' U'"
        self.write_step('PLL', {'Aa': entry})

        cards = TrainingReviewView('CFOP', 'PLL').get_context()['cards']

        self.assertEqual(cards[0]['algorithm'], "R U R' U'")

    def test_nothing_due(self) -> None:
        """Without due case the page says so."""
        self.write_step('PLL', {'Aa': trained([2000])})

        html = TrainingReviewView('CFOP', 'PLL').as_view(debug=False)

        self.assertIn('Nothing to review', html)

    def test_unknown_step(self) -> None:
        """A step outside the Academy is not found."""
        with self.assertRaises(HTTPError) as caught:
            TrainingReviewView('CFOP', 'LL')

        self.assertEqual(caught.exception.status_code, 404)

    def test_page_renders_cards(self) -> None:
        """The review page renders the hidden algorithm of each card."""
        self.write_step('PLL', {
            'Aa': due_card(datetime.now(UTC) - timedelta(hours=1)),
        })

        html = TrainingReviewView('CFOP', 'PLL').as_view(debug=False)

        self.assertIn('flashcard', html)
        self.assertIn('hidden', html)

    def test_training_routes_read_only(self) -> None:
        """No training route writes anything: GET only."""
        app = Server.create_app(debug=False)

        methods = {
            route.method for route in app.routes
            if route.rule.startswith('/training/')
        }

        self.assertEqual(methods, {'GET'})
