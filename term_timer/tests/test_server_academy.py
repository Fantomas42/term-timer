"""Tests for the Academy and Training pages of the web server."""
import json
import re
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from typing import cast

from bottle import TEMPLATE_PATH
from fsrs import State

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.server.annotations import AcademyOverviewContext
from term_timer.server.app import Server
from term_timer.server.filters import alg_text
from term_timer.server.filters import paragraphs
from term_timer.server.views import AcademyCaseView
from term_timer.server.views import AcademyStepView
from term_timer.server.views import AcademyView
from term_timer.server.views import TrainingForecastView
from term_timer.server.views import TrainingReviewView
from term_timer.tests.test_server_daily import WSGIClient
from term_timer.tests.test_server_training import TrainingServerTestCase
from term_timer.tests.test_server_training import card_data
from term_timer.tests.test_server_training import due_card
from term_timer.tests.test_server_training import trained

NOW = datetime.now(UTC)

JSON_BLOCK_RE = r'<script type="application/json" id="{}">(.*?)</script>'


def reviewed(retention_days: int, stability: float) -> dict[str, Any]:
    """
    Build a case reviewed some days ago, due in the future.

    Returns:
        Raw entry of a training file.

    """
    return trained([1500] * 5, card_data(
        State.Review, timedelta(days=30),
        timedelta(days=-retention_days), stability=stability,
    ))


class AcademyPageTestCase(TrainingServerTestCase):
    """Render the pages through the application, trainings patched."""

    client: WSGIClient

    @classmethod
    def setUpClass(cls) -> None:
        """Register the templates and build the application."""
        super().setUpClass()
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)
        cls.client = WSGIClient(Server.create_app(debug=False))

    def page(self, path: str) -> str:
        """
        Render a page, failing the test unless it answers 200. A page
        escapes no markup and holds no inline script.

        Returns:
            The body of the page.

        """
        status, _headers, body = self.client.get(path)
        self.assertEqual(status, HTTPStatus.OK, path)
        self.assertNotIn('&lt;span', body)
        self.assertNotIn('&lt;br', body)
        for attributes, content in re.findall(
                r'<script([^>]*)>(.*?)</script>', body, re.DOTALL):
            if content.strip():
                self.assertRegex(attributes, 'application/json|importmap')
        return body

    def json_block(self, body: str, block: str) -> dict[str, Any]:
        """
        Read a JSON data block of a page.

        Returns:
            The decoded data.

        """
        match = re.search(JSON_BLOCK_RE.format(block), body, re.DOTALL)
        if match is None:
            self.fail(f'No { block } block')
        data: dict[str, Any] = json.loads(match.group(1))
        return data


class TestAcademyNotFound(AcademyPageTestCase):
    """An Academy page of an unknown step or case is not found."""

    def test_unknown_step(self) -> None:
        """A step without collection is a 404, not a server error."""
        status, _headers, _body = self.client.get('/academy/CFOP/XYZ/')

        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_unknown_step_of_case(self) -> None:
        """A case of a step without collection is a 404."""
        status, _headers, _body = self.client.get('/academy/CFOP/XYZ/1/')

        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_unknown_case(self) -> None:
        """A case unknown to its collection is a 404."""
        status, _headers, _body = self.client.get('/academy/CFOP/PLL/Zz/')

        self.assertEqual(status, HTTPStatus.NOT_FOUND)


class TestAcademyHelpers(unittest.TestCase):
    """The helpers shared by the Academy and Training views."""

    def test_paragraphs(self) -> None:
        """The <br> tags of the database split a text in paragraphs."""
        self.assertEqual(
            paragraphs('One.<br><br>Two <br/> three.<BR>'),
            ['One.', 'Two', 'three.'],
        )
        self.assertEqual(paragraphs(''), [])

    def test_split_description(self) -> None:
        """A description splits on its dash, or stays a title."""
        self.assertEqual(
            AcademyView.split_description('OLL - Orient the layer'),
            ('OLL', 'Orient the layer'),
        )
        self.assertEqual(AcademyView.split_description('PBL'), ('PBL', ''))

    def test_train_command(self) -> None:
        """Only the steps the trainer knows get a command."""
        self.assertEqual(
            AcademyView.train_command('CFOP', 'OLL'),
            'term-timer train -s oll',
        )
        self.assertEqual(
            AcademyView.train_command('CFOP', 'PLL', ('Aa', 'T')),
            'term-timer train -s pll -c Aa T',
        )
        self.assertEqual(AcademyView.train_command('Roux', 'CMLL'), '')

    def test_weak_codes(self) -> None:
        """Weak cases: recall under 90% or slowing down, lowest first."""
        base: dict[str, Any] = {
            'state_label': 'Stable', 'state_class': 'stable',
            'overdue': False, 'attempts': 5, 'ao5': 1, 'speed': '',
            'memory': '',
        }
        tiles: Any = {
            'strong': {**base, 'trend': 'up', 'retention': 97.0},
            'weak': {**base, 'trend': 'flat', 'retention': 70.0},
            'weaker': {**base, 'trend': 'up', 'retention': 40.0},
            'slow': {**base, 'trend': 'down', 'retention': 95.0},
            'unseen': {**base, 'trend': 'down', 'retention': None},
        }

        self.assertEqual(
            AcademyView.weak_codes(tiles),
            ['weaker', 'weak', 'slow', 'unseen'],
        )


class TestAcademyOverviewPage(AcademyPageTestCase):
    """The overview lists every method, its steps and their training."""

    @staticmethod
    def overview() -> AcademyOverviewContext:
        """
        Build the context of the overview.

        Returns:
            Context of the academy overview view.

        """
        return cast('AcademyOverviewContext', AcademyView().get_context())

    def test_methods_and_steps(self) -> None:
        """Each method has its steps, linked, with their case count."""
        cards = self.overview()['method_cards']

        self.assertEqual(
            [card['name'] for card in cards], ['CFOP', 'Roux', 'Ortega'],
        )
        pll = cards[0]['steps'][2]
        self.assertEqual(pll['step'], 'PLL')
        self.assertEqual(pll['cases'], 21)
        self.assertEqual(pll['href'], '/academy/CFOP/PLL/')
        self.assertIsNone(pll['counts'])
        self.assertEqual(pll['review_url'], '')

    def test_trained_step(self) -> None:
        """A trained step counts its due and mastered cases."""
        self.write_step('PLL', {
            'Aa': due_card(NOW - timedelta(hours=2)),
            'Ab': reviewed(2, 30.0),
        })

        pll = self.overview()['method_cards'][0]['steps'][2]
        counts = pll['counts']
        if counts is None:
            self.fail('No counts')

        self.assertEqual(counts['due'], 1)
        self.assertEqual(counts['mastered'], 1)
        self.assertEqual(counts['trained'], 2)
        self.assertEqual(pll['review_url'], '/training/CFOP/PLL/review/')

    def test_page(self) -> None:
        """The page renders the methods and the review sheet link."""
        self.write_step('PLL', {'Aa': due_card(NOW - timedelta(hours=2))})

        body = self.page('/academy/')

        self.assertIn('3x3x3 CFOP', body)
        self.assertIn('2x2x2 Ortega', body)
        self.assertIn('/training/CFOP/PLL/review/', body)
        self.assertIn('state-bar', body)


class TestAcademyStepPage(AcademyPageTestCase):
    """The step page grids the cases of each family."""

    def test_families(self) -> None:
        """Every family is listed, the filtered ones without tiles."""
        context = AcademyStepView(
            'CFOP', 'PLL', '', 'Edges only', '',
        ).get_context()
        families = {family['name']: family for family in context['families']}

        self.assertEqual(
            set(families), {'Corners only', 'Corners and edges', 'Edges only'},
        )
        self.assertTrue(families['Edges only']['active'])
        self.assertEqual(len(families['Edges only']['tiles']), 4)
        self.assertEqual(families['Corners only']['tiles'], [])
        self.assertEqual(
            families['Edges only']['href'],
            '/academy/CFOP/PLL/?family=Edges+only',
        )

    def test_custom_solution(self) -> None:
        """A solution of the training file replaces the main algorithm."""
        entry = trained([2000])
        entry['solution'] = "R U R' U'"
        self.write_step('PLL', {'Aa': entry})

        context = AcademyStepView('CFOP', 'PLL', '', '', '').get_context()
        tiles = {
            tile['code']: tile
            for family in context['families'] for tile in family['tiles']
        }

        self.assertTrue(tiles['Aa']['custom'])
        self.assertEqual(alg_text(tiles['Aa']['tokens']), "R U R' U'")
        self.assertFalse(tiles['Ab']['custom'])

    def test_untrained_page(self) -> None:
        """Without training, no tint switch nor summary."""
        body = self.page('/academy/CFOP/PLL/')

        self.assertIn('data-quiz="off"', body)
        self.assertNotIn('data-segmented="tint"', body)
        self.assertIn('data-tint="none"', body)
        self.assertEqual(body.count('class="case-grid-tile"'), 21)

    def test_trained_page(self) -> None:
        """Trained, the page tints by state and sums the training up."""
        self.write_step('PLL', {'Aa': due_card(NOW - timedelta(hours=2))})

        body = self.page('/academy/CFOP/PLL/')

        self.assertIn('data-segmented="tint"', body)
        self.assertEqual(
            body.count('data-segmented-scope="academy"'), 2,
        )
        self.assertIn('data-tint="state"', body)
        self.assertIn('data-state="review"', body)
        self.assertIn('term-timer train -s pll', body)
        self.assertIn('/training/CFOP/PLL/review/', body)

    def test_family_page(self) -> None:
        """A family filter shows its cases only."""
        body = self.page('/academy/CFOP/PLL/?family=Edges+only')

        self.assertEqual(body.count('class="case-grid-tile"'), 4)


class TestAcademyCasePage(AcademyPageTestCase):
    """The case page teaches the case: algorithm, recognition, sources."""

    def test_focus_main_algorithm(self) -> None:
        """Without solution, the main algorithm is the one to learn."""
        context = AcademyCaseView('CFOP', 'PLL', 'Aa', '').get_context()

        self.assertFalse(context['focus']['custom'])
        self.assertEqual(
            context['focus']['text'], str(context['case'].main_algorithm),
        )
        self.assertEqual(context['player']['alg'], context['focus']['text'])
        self.assertEqual(context['player']['anchor'], 'end')
        self.assertEqual(context['command'], 'term-timer train -s pll -c Aa')

    def test_focus_custom_solution(self) -> None:
        """A saved solution is the one to learn, and the one played."""
        entry = trained([2000])
        entry['solution'] = "R U R' U R U2 R'"
        self.write_step('OLL', {'27': entry})

        context = AcademyCaseView('CFOP', 'OLL', '27', '').get_context()

        self.assertTrue(context['focus']['custom'])
        self.assertEqual(context['focus']['text'], "R U R' U R U2 R'")
        self.assertEqual(context['focus']['htm'], 7)
        self.assertEqual(context['player']['alg'], "R U R' U R U2 R'")

    def test_neighbours(self) -> None:
        """The first case has no previous one, the last no next one."""
        first = AcademyCaseView('CFOP', 'PLL', 'Aa', '').get_context()
        last = AcademyCaseView('CFOP', 'PLL', 'Z', '').get_context()

        self.assertEqual(first['previous_url'], '')
        self.assertEqual(first['next_url'], '/academy/CFOP/PLL/Ab/')
        self.assertEqual(last['next_url'], '')

    def test_sources(self) -> None:
        """Empty sources are dropped, the others ranked by comfort."""
        context = AcademyCaseView('CFOP', 'PLL', 'Aa', '').get_context()
        sources = {source['slug']: source for source in context['sources']}

        self.assertIn('database', sources)
        self.assertEqual(context['source_tabs'][0], ('database', 'Database'))
        rows = sources['database']['rows']
        self.assertEqual([row['rank'] for row in rows[:3]], [1, 2, 3])
        self.assertGreaterEqual(rows[0]['ergonomics'], rows[1]['ergonomics'])
        self.assertIn('Difficulty 3 / 5', sources['badmephisto']['note'])
        self.assertEqual(sources['setups']['image'], 'algo')

    def test_recognition(self) -> None:
        """PLL angles come split in paragraphs, one rotation each."""
        context = AcademyCaseView('CFOP', 'PLL', 'Aa', '').get_context()

        self.assertEqual(len(context['recognition']), 4)
        self.assertEqual(
            [angle['rotation'] for angle in context['recognition']],
            ['y45x-34', 'y135x-34', 'y225x-34', 'y315x-34'],
        )
        self.assertGreater(len(context['recognition'][0]['description']), 1)
        self.assertTrue(context['recognition_setup'])

    def test_no_recognition(self) -> None:
        """A case without recognition data has no angle."""
        context = AcademyCaseView('CFOP', 'OLL', '27', '').get_context()

        self.assertEqual(context['recognition'], [])
        self.assertEqual(context['recognition_setup'], '')

    def test_page(self) -> None:
        """The page renders the case, folding the long tables."""
        body = self.page('/academy/CFOP/PLL/Aa/')

        self.assertIn('data-verbatim>Aa<', body)
        self.assertIn('data-revealable hidden', body)
        self.assertIn('data-reveal="source-database"', body)
        self.assertIn('Headlights', body)
        player = self.json_block(body, 'case-player-data')
        self.assertEqual(player['puzzle'], '3x3x3')

    def test_page_with_training(self) -> None:
        """A trained case draws its attempts and its forgetting curve."""
        self.write_step('OLL', {
            '27': trained([1500, 1400], card_data(
                State.Review, timedelta(days=-2), timedelta(days=-6),
            )),
        })

        body = self.page('/academy/CFOP/OLL/27/')

        self.assertIn('id="training"', body)
        self.assertIn('data-chart="training-attempts"', body)
        forgetting = self.json_block(body, 'chart-forgetting-data')
        self.assertAlmostEqual(forgetting['due'], 4.0, places=2)
        self.assertIn('overdue by 2 d', body)
        self.assertNotIn('due overdue', body)

    def test_page_unavailable(self) -> None:
        """A truncated training file renders a notice."""
        self.write_step('OLL', '{')

        body = self.page('/academy/CFOP/OLL/27/')

        self.assertIn('Training data unavailable', body)

    def test_debug_page(self) -> None:
        """The debug page groups the algorithms by impact."""
        body = self.page('/academy/CFOP/PLL/Aa/debug/')

        self.assertIn('Impact ', body)
        self.assertIn('>Algorithms<', body)


class TestTrainingPage(AcademyPageTestCase):
    """The training page: today, the forecast and the cases to rework."""

    def test_steps_and_weak(self) -> None:
        """Each trained step has its states; weak cases come first."""
        self.write_step('PLL', {
            'Aa': due_card(NOW - timedelta(hours=2)),
            'Ab': reviewed(200, 3.0),
            'E': reviewed(1, 300.0),
        })

        context = TrainingForecastView().get_context()
        row = context['steps'][0]

        self.assertEqual(row['status']['step'], 'PLL')
        self.assertEqual(row['command'], 'term-timer train -s pll')
        self.assertEqual(row['review_url'], '/training/CFOP/PLL/review/')
        self.assertEqual(
            {state['label'] for state in row['states']},
            {'New', 'Review', 'Stable'},
        )
        weak = [tile['code'] for tile in context['weak']]
        self.assertEqual(weak[0], 'Ab')
        self.assertNotIn('E', weak)
        self.assertTrue(context['weak'][0]['label'].startswith('PLL'))

    def test_forecast_roles_fixed(self) -> None:
        """A step keeps its colour whatever the other steps do."""
        self.write_step('PLL', {'Aa': due_card(NOW + timedelta(days=1))})

        context = TrainingForecastView().get_context()

        self.assertEqual(context['forecast_legend'], [(4, 'PLL')])
        self.assertEqual(
            context['forecast_chart']['series'][0]['role'], 'chart-4',
        )

    def test_page(self) -> None:
        """The page renders its three sections."""
        self.write_step('PLL', {
            'Aa': due_card(NOW - timedelta(hours=2)),
            'Ab': reviewed(200, 3.0),
        })

        body = self.page('/training/')

        self.assertIn('id="today"', body)
        self.assertIn('data-chart="training-forecast"', body)
        self.assertIn('id="weak-cases"', body)

    def test_empty_page(self) -> None:
        """Without training, the page says how to start one."""
        body = self.page('/training/')

        self.assertIn('No case trained yet', body)
        self.assertIn('term-timer train', body)


class TestReviewSheet(AcademyPageTestCase):
    """The review sheet shows the cases to train next, algorithms in."""

    def setUp(self) -> None:
        """Train three PLL cases: two due, one to rework."""
        super().setUp()
        self.write_step('PLL', {
            'Aa': due_card(NOW - timedelta(hours=1)),
            'T': due_card(NOW - timedelta(days=3)),
            'Ab': reviewed(200, 3.0),
        })

    def test_due_pool(self) -> None:
        """The due cases come first, the most overdue first."""
        context = TrainingReviewView('CFOP', 'PLL').get_context()
        pools = {pool['slug']: pool for pool in context['pools']}

        self.assertEqual([tile['code'] for tile in context['tiles']],
                         ['T', 'Aa'])
        self.assertEqual(context['tiles'][0]['note'], 'overdue by 3 d')
        self.assertTrue(pools['due']['active'])
        self.assertEqual(pools['all']['count'], 21)
        self.assertEqual(context['command'], 'term-timer train -s pll')

    def test_weak_pool(self) -> None:
        """The weak cases get a command restricted to them."""
        context = TrainingReviewView(
            'CFOP', 'PLL', pool='weak',
        ).get_context()

        self.assertEqual(context['tiles'][0]['code'], 'Ab')
        self.assertEqual(context['tiles'][0]['note'], '')
        self.assertTrue(context['command'].startswith(
            'term-timer train -s pll -c Ab',
        ))

    def test_unknown_pool(self) -> None:
        """An unknown pool falls back on the due cases."""
        view = TrainingReviewView('CFOP', 'PLL', pool='nope')

        self.assertEqual(view.pool, 'due')

    def test_family(self) -> None:
        """A family restricts every pool, and its links keep the pool."""
        context = TrainingReviewView(
            'CFOP', 'PLL', pool='all', family='Edges only',
        ).get_context()
        pools = {pool['slug']: pool for pool in context['pools']}

        self.assertEqual(len(context['tiles']), 4)
        self.assertEqual(pools['due']['count'], 0)
        self.assertEqual(
            pools['due']['href'],
            '/training/CFOP/PLL/review/?family=Edges+only',
        )
        self.assertEqual(
            context['families_url'], '/training/CFOP/PLL/review/?pool=all',
        )

    def test_page(self) -> None:
        """The sheet shows the algorithms, larger than on the grid."""
        body = self.page('/training/CFOP/PLL/review/')

        self.assertEqual(body.count('class="case-grid-tile"'), 2)
        self.assertIn('data-size="m" data-frame="bare"', body)
        self.assertIn('data-segmented="quiz"', body)
        # Remembered apart from the academy: a quiz left on there does
        # not blur this sheet.
        self.assertIn('data-segmented-scope="review"', body)

    def test_empty_pool_offers_others(self) -> None:
        """An empty pool links to the pools holding cases."""
        body = self.page(
            '/training/CFOP/PLL/review/?family=Edges+only',
        )

        self.assertIn('Nothing due on PLL in Edges only', body)
        self.assertIn('All · 4', body)
