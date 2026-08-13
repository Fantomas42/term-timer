"""Tests for trainer."""
import asyncio
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from random import Random
from typing import ClassVar
from typing import cast
from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

from cubing_algs.cases import get_collection
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from fsrs import Card
from fsrs import Rating
from fsrs import State
from rich.console import Console as RichConsole
from rich.theme import Theme

from term_timer.arguments import get_parser
from term_timer.exceptions import EmptyCasePoolError
from term_timer.exceptions import InvalidCaseError
from term_timer.fsrs.rating import RatingBreakdown
from term_timer.fsrs.scheduler import FSRSScheduler
from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import Trainings
from term_timer.interface.console import theme as console_theme
from term_timer.scripts.commands import trainer as trainer_mod
from term_timer.solve import Solve
from term_timer.stats import Statistics
from term_timer.trainer import MANUAL_RATING_KEYS
from term_timer.trainer import TREND_MIN_TIMINGS
from term_timer.trainer import PendingAttempt
from term_timer.trainer import Trainer


class TestTrainerModule(unittest.TestCase):
    """Tests for Trainer class."""

    def test_initialization(self) -> None:
        """Test that Trainer initializes with all required attributes."""
        timer = Trainer(
            step='oll',
            case_codes=['01', '02'],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=[],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )

        for key in (
                'moves',
                'bluetooth_queue',
                'bluetooth_cube',
                'bluetooth_interface',
                'bluetooth_consumer_ref',
                'bluetooth_hardware',
                'facelets_received_event',
                'hardware_received_event',
                'console',
                'cube_orientation_moves',
                'save_moves',
                'save_gesture',
                'save_gesture_event',
                'countdown',
                'inspection_completed_event',
                'scramble',
                'scrambled',
                'scramble_oriented',
                'counter',
                'facelets_scrambled',
                'scramble_completed_event',
                'state',
                'start_time',
                'end_time',
                'free_play',
                'elapsed_time',
                'metronome',
                'solve_started_event',
                'solve_completed_event',
                'orientation_faces',
                'rng',
        ):
            self.assertTrue(hasattr(timer, key), key)

    def test_filter_by_family(self) -> None:
        """Test that filters restrict cases to matching family."""
        timer = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=['Dot'],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )

        all_cases = get_collection('CFOP/OLL').cases
        dot_codes = {
            v.code for v in all_cases.values()
            if v.setup_algorithms and (v.family or '').lower() == 'dot'
        }
        trained_codes = {tc.case.code for tc in timer.cases}
        self.assertEqual(trained_codes, dot_codes)

    def test_filter_by_group(self) -> None:
        """Test that filters restrict cases to matching group."""
        timer = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=['OCLL'],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )

        all_cases = get_collection('CFOP/OLL').cases
        ocll_codes = {
            v.code for v in all_cases.values()
            if v.setup_algorithms
            and 'ocll' in [g.lower() for g in (v.groups or [])]
        }
        trained_codes = {tc.case.code for tc in timer.cases}
        self.assertEqual(trained_codes, ocll_codes)

    def test_filter_case_insensitive(self) -> None:
        """Test that filter matching is case-insensitive."""
        timer_lower = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=['dot'],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )
        timer_upper = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=['DOT'],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )

        codes_lower = {tc.case.code for tc in timer_lower.cases}
        codes_upper = {tc.case.code for tc in timer_upper.cases}
        self.assertEqual(codes_lower, codes_upper)

    def test_filter_multiple_values(self) -> None:
        """Test that multiple filter values are combined with OR logic."""
        timer_combined = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=['Dot', 'Cross'],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )
        timer_dot = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=['Dot'],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )
        timer_cross = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=['Cross'],
            states=[],
            free_play=True,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )

        codes_combined = {tc.case.code for tc in timer_combined.cases}
        codes_dot = {tc.case.code for tc in timer_dot.cases}
        codes_cross = {tc.case.code for tc in timer_cross.cases}
        self.assertEqual(codes_combined, codes_dot | codes_cross)


class TestFSRSWithFilter(unittest.TestCase):
    """fsrs_selection and fsrs_update behave correctly across combinations."""

    @staticmethod
    def make_trainer(
            filters: list[str] | None = None,
            case_codes: list[str] | None = None,
            oldest: int = 0,
            slowest: int = 0,
            random: int = 0,
    ) -> Trainer:
        """
        Build a minimal OLL Trainer for testing.

        Returns:
            Configured Trainer instance.

        """
        return Trainer(
            step='oll',
            case_codes=case_codes or [],
            oldest=oldest,
            slowest=slowest,
            random=random,
            new_cases_limit=5,
            filters=filters or [],
            states=[],
            free_play=False,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )

    def test_fsrs_selection_with_filter(self) -> None:
        """fsrs_selection is True when only --filter is set."""
        timer = self.make_trainer(filters=['Dot'])
        self.assertTrue(timer.fsrs_selection)

    def test_fsrs_selection_with_oldest(self) -> None:
        """fsrs_selection is True when --oldest restricts the pool."""
        timer = self.make_trainer(oldest=3)
        self.assertTrue(timer.fsrs_selection)

    def test_fsrs_selection_with_slowest(self) -> None:
        """fsrs_selection is True when --slowest restricts the pool."""
        timer = self.make_trainer(slowest=3)
        self.assertTrue(timer.fsrs_selection)

    def test_fsrs_selection_with_filter_and_oldest(self) -> None:
        """fsrs_selection is True when --filter and --oldest are combined."""
        timer = self.make_trainer(filters=['Dot'], oldest=3)
        self.assertTrue(timer.fsrs_selection)

    def test_fsrs_selection_false_with_cases(self) -> None:
        """fsrs_selection is False with --cases: FSRS skips selection."""
        timer = self.make_trainer(case_codes=['01', '02'])
        self.assertFalse(timer.fsrs_selection)

    def test_fsrs_selection_false_with_random(self) -> None:
        """fsrs_selection is False with --random: FSRS skips selection."""
        timer = self.make_trainer(random=5)
        self.assertFalse(timer.fsrs_selection)

    def test_fsrs_update_true_with_cases(self) -> None:
        """fsrs_update is True with --cases: solves still update FSRS cards."""
        timer = self.make_trainer(case_codes=['01', '02'])
        self.assertTrue(timer.fsrs_update)

    def test_fsrs_update_true_with_random(self) -> None:
        """fsrs_update is True with --random: solves still update FSRS cards."""
        timer = self.make_trainer(random=5)
        self.assertTrue(timer.fsrs_update)

    def test_fsrs_scheduler_instantiated_with_cases(self) -> None:
        """fsrs_scheduler is not None with --cases so card updates can run."""
        timer = self.make_trainer(case_codes=['01', '02'])
        self.assertIsNotNone(timer.fsrs_scheduler)

    def test_fsrs_probabilities_restricted_to_filter(self) -> None:
        """fsrs_probabilities contains only cases from the filtered subset."""
        timer = self.make_trainer(filters=['Dot'])
        filtered_codes = {tc.case.code for tc in timer.cases}
        self.assertEqual(set(timer.fsrs_probabilities.keys()), filtered_codes)

    def test_fsrs_probabilities_subset_of_all_cases(self) -> None:
        """Filtered fsrs_probabilities is a strict subset of the full set."""
        timer_filtered = self.make_trainer(filters=['Dot'])
        timer_all = self.make_trainer()
        filtered_keys = set(timer_filtered.fsrs_probabilities.keys())
        all_keys = set(timer_all.fsrs_probabilities.keys())
        self.assertTrue(filtered_keys < all_keys)

    def test_fsrs_probabilities_restricted_to_oldest(self) -> None:
        """fsrs_probabilities contains only the N oldest cases."""
        timer = self.make_trainer(oldest=3)
        self.assertEqual(len(timer.fsrs_probabilities), 3)

    def test_fsrs_probabilities_restricted_to_slowest(self) -> None:
        """fsrs_probabilities contains only the N slowest cases."""
        timer = self.make_trainer(slowest=3)
        self.assertEqual(len(timer.fsrs_probabilities), 3)

    def test_fsrs_disabled_in_free_play(self) -> None:
        """free_play disables fsrs_update and fsrs_selection to avoid loops."""
        timer = Trainer(
            step='oll', case_codes=[], oldest=0, slowest=0, random=0,
            new_cases_limit=5, filters=[], states=[], free_play=True,
            show_solution=False, show_breakdown=False,
            show_cube=False, metronome=0,
            orientation='DF', rng=Random(),  # noqa: S311
        )
        self.assertFalse(timer.fsrs_update)
        self.assertFalse(timer.fsrs_selection)
        self.assertIsNone(timer.fsrs_scheduler)

    def test_fsrs_disabled_in_free_play_with_filter(self) -> None:
        """free_play disables FSRS even when a filter is active."""
        timer = Trainer(
            step='oll', case_codes=[], oldest=0, slowest=0, random=0,
            new_cases_limit=5, filters=['Dot'], states=[], free_play=True,
            show_solution=False, show_breakdown=False,
            show_cube=False, metronome=0,
            orientation='DF', rng=Random(),  # noqa: S311
        )
        self.assertFalse(timer.fsrs_update)
        self.assertFalse(timer.fsrs_selection)


class TestFSRSCardsPool(unittest.TestCase):
    """fsrs_cards restricts FSRS reasoning to the selected case pool."""

    # OLL codes given a recent practice date and a due FSRS card. They
    # sit outside an --oldest pool (which prefers never-practiced cases)
    # so they exercise the in-pool filtering.
    SEEN_CODES: ClassVar[list[str]] = ['01', '02', '03', '04', '05']

    def make_trainer(self, *, oldest: int = 0) -> Trainer:
        """
        Build an OLL trainer whose seen due cards sit outside the pool.

        The seen cases carry a recent last_date, so --oldest selects only
        never-practiced cases, leaving every due card out of the pool.

        Returns:
            Configured Trainer with a patched trainings store.

        """
        recent = int(datetime.now(tz=UTC).timestamp())
        past = datetime.now(tz=UTC) - timedelta(days=1)
        cases = {}
        for code in self.SEEN_CODES:
            card = Card()
            card.due = past
            cases[code] = CaseTraining(
                code=code,
                last_date=recent,
                timings=[2000],
                fsrs_card=card,
            )
        trainings = Trainings(method='CFOP', step='OLL', cases=cases)

        with patch(
            'term_timer.trainer.load_trainings', return_value=trainings,
        ):
            timer = Trainer(
                step='oll',
                case_codes=[],
                oldest=oldest,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.console = MagicMock()
        return timer

    def test_seen_cards_excluded_when_out_of_pool(self) -> None:
        """fsrs_cards drops cards whose case is outside the --oldest pool."""
        timer = self.make_trainer(oldest=3)
        pool = set(timer.fsrs_probabilities)

        self.assertTrue(pool.isdisjoint(self.SEEN_CODES))
        self.assertEqual(timer.fsrs_cards, {})

    def test_cards_kept_when_in_pool(self) -> None:
        """fsrs_cards keeps the seen cards when no pool restriction applies."""
        timer = self.make_trainer()

        self.assertEqual(set(timer.fsrs_cards), set(self.SEEN_CODES))

    def test_cards_are_always_a_subset_of_the_pool(self) -> None:
        """Every fsrs_cards key belongs to the selected pool."""
        timer = self.make_trainer(oldest=10)

        self.assertTrue(
            set(timer.fsrs_cards) <= set(timer.fsrs_probabilities),
        )

    def test_focus_is_exploration_not_review(self) -> None:
        """Out-of-pool due cards never push the focus into Review mode."""
        timer = self.make_trainer(oldest=3)
        timer.fsrs_focus_line()

        console = cast('MagicMock', timer.console)
        printed = ' '.join(
            str(call.args[0]) for call in console.print.call_args_list
        )
        self.assertIn('Exploration', printed)
        self.assertNotIn('Review', printed)

    def test_select_next_case_stays_in_pool(self) -> None:
        """select_next_case never returns a case outside the pool."""
        timer = self.make_trainer(oldest=3)
        scheduler = FSRSScheduler()

        for _ in range(20):
            chosen = scheduler.select_next_case(
                timer.fsrs_cards,
                timer.fsrs_probabilities,
                new_cases_limit=timer.fsrs_new_cases_remaining,
            )
            self.assertIn(chosen, timer.fsrs_probabilities)


class StateFixtureMixin:
    """Trainings fixture holding one OLL case per FSRS card state."""

    # OLL codes given a card, one per state label. 01 to 04 belong to the
    # Dot family, 05 to the Square one, so the state filter can be
    # combined with a family filter. Every other case has no card and is
    # therefore new.
    LEARNING_CODE = '01'
    RELEARNING_CODE = '02'
    REVIEW_CODE = '03'
    STABLE_CODE = '04'
    SQUARE_LEARNING_CODE = '05'
    CARDLESS_CODE = '06'

    def make_trainings(self) -> Trainings:
        """
        Build a trainings store covering every card state.

        Returns:
            Trainings with one case per state, plus a card-less case.

        """
        now = datetime.now(tz=UTC)
        recent = int(now.timestamp())
        states = {
            self.LEARNING_CODE: (State.Learning, now - timedelta(minutes=5)),
            self.RELEARNING_CODE: (
                State.Relearning, now - timedelta(minutes=5),
            ),
            self.REVIEW_CODE: (State.Review, now - timedelta(days=1)),
            self.STABLE_CODE: (State.Review, now + timedelta(days=3)),
            self.SQUARE_LEARNING_CODE: (
                State.Learning, now - timedelta(minutes=5),
            ),
        }

        cases = {}
        for code, (state, due) in states.items():
            card = Card()
            card.state = state
            card.due = due
            cases[code] = CaseTraining(
                code=code,
                last_date=recent,
                timings=[2000],
                fsrs_card=card,
            )

        cases[self.CARDLESS_CODE] = CaseTraining(
            code=self.CARDLESS_CODE,
            last_date=recent,
            timings=[2000],
        )

        return Trainings(method='CFOP', step='OLL', cases=cases)

    def make_trainer(  # noqa: PLR0913
            self,
            states: list[str],
            *,
            case_codes: list[str] | None = None,
            filters: list[str] | None = None,
            oldest: int = 0,
            slowest: int = 0,
            show_breakdown: bool = False,
    ) -> Trainer:
        """
        Build an OLL trainer over the state fixture.

        Returns:
            Configured Trainer with a patched trainings store.

        """
        with patch(
            'term_timer.trainer.load_trainings',
            return_value=self.make_trainings(),
        ):
            return Trainer(
                step='oll',
                case_codes=case_codes or [],
                oldest=oldest,
                slowest=slowest,
                random=0,
                new_cases_limit=5,
                filters=filters or [],
                states=states,
                free_play=False,
                show_solution=False,
                show_breakdown=show_breakdown,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )

    @staticmethod
    def pool(timer: Trainer) -> set[str]:
        """
        Collect the case codes of a trainer pool.

        Returns:
            Set of the case codes selected for training.

        """
        return {tc.case.code for tc in timer.cases}

    @staticmethod
    def move_card(timer: Trainer, code: str, state: State, due: int) -> None:
        """Move the card of a case to another state and due date."""
        card = cast('Card', timer.trainings.cases[code].fsrs_card)
        card.state = state
        card.due = datetime.now(tz=UTC) + timedelta(minutes=due)


class TestStateFilter(StateFixtureMixin, unittest.TestCase):
    """--state restricts the case pool to the wanted FSRS card states."""

    def test_learning_state(self) -> None:
        """--state learning keeps only the cards in Learning."""
        timer = self.make_trainer(['learning'])

        self.assertEqual(
            self.pool(timer),
            {self.LEARNING_CODE, self.SQUARE_LEARNING_CODE},
        )

    def test_relearning_state(self) -> None:
        """--state relearning keeps only the cards in Relearning."""
        timer = self.make_trainer(['relearning'])

        self.assertEqual(self.pool(timer), {self.RELEARNING_CODE})

    def test_review_state_is_due_only(self) -> None:
        """--state review keeps the Review cards whose due date passed."""
        timer = self.make_trainer(['review'])

        self.assertEqual(self.pool(timer), {self.REVIEW_CODE})

    def test_stable_state_is_scheduled_review(self) -> None:
        """--state stable keeps the Review cards still scheduled ahead."""
        timer = self.make_trainer(['stable'])

        self.assertEqual(self.pool(timer), {self.STABLE_CODE})

    def test_new_state_covers_cases_without_card(self) -> None:
        """--state new keeps the cases with no card, card-less ones too."""
        timer = self.make_trainer(['new'])
        pool = self.pool(timer)

        self.assertIn(self.CARDLESS_CODE, pool)
        self.assertTrue(
            pool.isdisjoint(
                {
                    self.LEARNING_CODE, self.RELEARNING_CODE,
                    self.REVIEW_CODE, self.STABLE_CODE,
                    self.SQUARE_LEARNING_CODE,
                },
            ),
        )

    def test_multiple_states_are_combined_with_or(self) -> None:
        """Several states are combined with OR logic."""
        timer = self.make_trainer(['relearning', 'review'])

        self.assertEqual(
            self.pool(timer),
            {self.RELEARNING_CODE, self.REVIEW_CODE},
        )

    def test_state_restricts_fsrs_probabilities(self) -> None:
        """FSRS only reasons on the cases kept by the state filter."""
        timer = self.make_trainer(['learning'])

        self.assertEqual(
            set(timer.fsrs_probabilities),
            {self.LEARNING_CODE, self.SQUARE_LEARNING_CODE},
        )
        self.assertTrue(timer.fsrs_selection)

    def test_state_combined_with_filter(self) -> None:
        """--state and --filter narrow the pool together."""
        timer = self.make_trainer(['learning'], filters=['Dot'])

        self.assertEqual(self.pool(timer), {self.LEARNING_CODE})

    def test_state_combined_with_cases(self) -> None:
        """--state narrows the cases named by --cases."""
        timer = self.make_trainer(
            ['learning'],
            case_codes=[self.LEARNING_CODE, self.REVIEW_CODE],
        )
        console = MagicMock()
        timer.console = console
        timer.trainer_line()

        printed = ' '.join(
            str(call.args[0]) for call in console.print.call_args_list
        )
        self.assertEqual(self.pool(timer), {self.LEARNING_CODE})
        self.assertIn('learning state', printed)

    def test_state_combined_with_oldest(self) -> None:
        """--oldest draws inside the pool restricted by --state."""
        timer = self.make_trainer(['learning'], oldest=1)
        pool = self.pool(timer)

        self.assertEqual(len(pool), 1)
        self.assertTrue(
            pool <= {self.LEARNING_CODE, self.SQUARE_LEARNING_CODE},
        )

    def test_unknown_case_still_reported_as_unknown(self) -> None:
        """A --cases code unknown to the step wins over the state filter."""
        with self.assertRaises(InvalidCaseError) as context:
            self.make_trainer(['learning'], case_codes=['999'])

        self.assertIn('is unknown', str(context.exception))

    def test_empty_state_pool_raises(self) -> None:
        """An empty state selection is reported before the session starts."""
        with self.assertRaises(EmptyCasePoolError) as context:
            self.make_trainer(
                ['stable'],
                case_codes=[self.LEARNING_CODE],
            )

        self.assertIn('No case in state "stable"', str(context.exception))

    def test_empty_filter_pool_raises(self) -> None:
        """An empty family filter is reported before the session starts."""
        with self.assertRaises(EmptyCasePoolError) as context:
            self.make_trainer([], filters=['unknown-family'])

        self.assertIn(
            'No case matching filter "unknown-family"',
            str(context.exception),
        )

    def test_trainer_line_mentions_the_states(self) -> None:
        """The training summary recalls the state restriction."""
        timer = self.make_trainer(['review', 'stable'])
        console = MagicMock()
        timer.console = console
        timer.trainer_line()

        printed = ' '.join(
            str(call.args[0]) for call in console.print.call_args_list
        )
        self.assertIn('review & stable state', printed)
        self.assertIn('2 matching', printed)


class TestStateFilterDrain(StateFixtureMixin, unittest.TestCase):
    """A case leaving the wanted states leaves the session pool."""

    def test_lapsed_card_leaves_the_pool(self) -> None:
        """An Again on a Review card takes it out of the session pool."""
        timer = self.make_trainer(['review'])
        self.assertEqual(self.pool(timer), {self.REVIEW_CODE})

        self.move_card(timer, self.REVIEW_CODE, State.Relearning, 2)

        self.assertFalse(timer.refresh_state_pool())
        self.assertEqual(self.pool(timer), set())

    def test_graduated_card_leaves_the_pool(self) -> None:
        """A reviewed card scheduled ahead is Stable, not Review anymore."""
        timer = self.make_trainer(['review'])

        self.move_card(timer, self.REVIEW_CODE, State.Review, 60 * 24 * 3)

        self.assertFalse(timer.refresh_state_pool())
        self.assertEqual(self.pool(timer), set())

    def test_case_keeping_its_state_stays_in_the_pool(self) -> None:
        """A card still walking its learning steps stays selectable."""
        timer = self.make_trainer(['learning'])

        self.move_card(timer, self.LEARNING_CODE, State.Learning, 5)

        self.assertTrue(timer.refresh_state_pool())
        self.assertEqual(
            self.pool(timer),
            {self.LEARNING_CODE, self.SQUARE_LEARNING_CODE},
        )

    def test_rated_new_case_leaves_the_pool(self) -> None:
        """A new case gaining a card is not new anymore."""
        timer = self.make_trainer(['new'])
        self.assertIn(self.CARDLESS_CODE, self.pool(timer))

        timer.trainings.cases[self.CARDLESS_CODE].fsrs_card = Card()
        self.move_card(timer, self.CARDLESS_CODE, State.Learning, 5)

        self.assertTrue(timer.refresh_state_pool())
        self.assertNotIn(self.CARDLESS_CODE, self.pool(timer))

    def test_pool_only_shrinks(self) -> None:
        """A case that left the pool never comes back in the session."""
        timer = self.make_trainer(['learning'])

        self.move_card(timer, self.LEARNING_CODE, State.Relearning, 2)
        timer.refresh_state_pool()
        self.assertEqual(self.pool(timer), {self.SQUARE_LEARNING_CODE})

        self.move_card(timer, self.LEARNING_CODE, State.Learning, 5)
        timer.refresh_state_pool()

        self.assertEqual(self.pool(timer), {self.SQUARE_LEARNING_CODE})

    def test_refresh_is_a_noop_without_state_filter(self) -> None:
        """Without --state the pool is never drained by a state change."""
        timer = self.make_trainer([])
        before = self.pool(timer)

        self.move_card(timer, self.REVIEW_CODE, State.Relearning, 2)

        self.assertTrue(timer.refresh_state_pool())
        self.assertEqual(self.pool(timer), before)

    def test_probabilities_follow_the_pool(self) -> None:
        """The FSRS pool of a dropped case is dropped with it."""
        timer = self.make_trainer(['review', 'stable'])

        self.move_card(timer, self.REVIEW_CODE, State.Relearning, 2)
        timer.refresh_state_pool()

        self.assertNotIn(self.REVIEW_CODE, timer.fsrs_probabilities)
        self.assertNotIn(self.REVIEW_CODE, timer.fsrs_cards)
        self.assertIn(self.STABLE_CODE, timer.fsrs_probabilities)

    def test_start_stops_on_a_drained_pool(self) -> None:
        """A drained pool ends the session instead of serving a case."""
        timer = self.make_trainer(['review'])
        timer.console = MagicMock()

        self.move_card(timer, self.REVIEW_CODE, State.Relearning, 2)

        with patch.object(
                Trainer, 'init_solve',
                side_effect=AssertionError('drained pool guard bypassed'),
        ):
            self.assertFalse(asyncio.run(timer.start()))

        self.assertTrue(timer.console.print.called)


class TestListCases(StateFixtureMixin, unittest.TestCase):
    """--list displays the pool the session would train on."""

    @staticmethod
    def render(timer: Trainer) -> str:
        """
        Capture the tables printed by the cases listing.

        Returns:
            The rendered listing, whitespace normalized.

        """
        recorder = RichConsole(
            record=True, width=120, theme=Theme(console_theme),
        )
        timer.console = recorder

        timer.list_cases()

        return ' '.join(recorder.export_text().split())

    def test_listing_covers_the_whole_step_by_default(self) -> None:
        """Without any restriction every case of the step is listed."""
        output = self.render(self.make_trainer([]))

        self.assertIn('OLL 01', output)
        self.assertIn('OLL 03', output)
        self.assertIn('OLL 57', output)

    def test_listing_restricted_by_state(self) -> None:
        """--state keeps only the cases sitting in the wanted states."""
        output = self.render(self.make_trainer(['learning']))

        self.assertIn('OLL 01', output)
        self.assertIn('OLL 05', output)
        self.assertNotIn('OLL 03', output)
        self.assertNotIn('OLL 57', output)

    def test_listing_restricted_by_filter(self) -> None:
        """--filter keeps only the cases of the wanted families."""
        output = self.render(self.make_trainer([], filters=['Square']))

        self.assertIn('OLL 05', output)
        self.assertNotIn('OLL 01', output)

    def test_listing_restricted_by_cases(self) -> None:
        """--cases lists the named cases only."""
        output = self.render(
            self.make_trainer([], case_codes=[self.REVIEW_CODE]),
        )

        self.assertIn('OLL 03', output)
        self.assertNotIn('OLL 01', output)

    def test_listing_restricted_by_slowest(self) -> None:
        """--slowest lists as many cases as it would train."""
        timer = self.make_trainer([], slowest=3)

        self.assertEqual(len(timer.cases), 3)

        output = self.render(timer)
        listed = [
            code for code in (f'OLL { n:02d}' for n in range(1, 58))
            if code in output
        ]

        self.assertEqual(len(listed), 3)

    def test_listing_summary_counts_the_listed_cases(self) -> None:
        """The summary recap covers the listed pool, not the whole step."""
        output = self.render(self.make_trainer(['learning']))

        self.assertIn('Learning 2', output)
        self.assertIn('Total 2', output)

    def test_listing_of_a_synthetic_step(self) -> None:
        """A step without a case collection keeps its card-less listing."""
        timer = Trainer(
            step='cross',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=[],
            states=[],
            free_play=False,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )
        output = self.render(timer)

        self.assertIn('Cross', output)
        self.assertNotIn('Due', output)


class TestFsrsResultLine(StateFixtureMixin, unittest.TestCase):
    """--explain gates the rating breakdown, no longer the debug mode."""

    BREAKDOWN = RatingBreakdown(
        rating=Rating.Good,
        time_s=2.4,
        executed_qtm=11,
        missed_qtm=0,
        pauses=1,
        tps=4.5,
        score=0.3,
        tps_ref=4.0,
        time_soft=2.0,
        tps_pen=-0.1,
        pause_pen=0.0,
        missed_pen=0.0,
        time_pen=0.4,
        reference_qtm=11,
    )

    def render(self, *, show_breakdown: bool) -> str:
        """
        Capture the result line printed for a rated attempt.

        Returns:
            The rendered line, whitespace normalized.

        """
        timer = self.make_trainer([], show_breakdown=show_breakdown)
        recorder = RichConsole(
            record=True, width=120, theme=Theme(console_theme),
        )
        timer.console = recorder

        timer.fsrs_result_line(
            timer.cases[0].case,
            Rating.Good,
            None,
            FSRSScheduler().update_card(None, Rating.Good),
            self.BREAKDOWN,
        )

        return ' '.join(recorder.export_text().split())

    def test_breakdown_hidden_by_default(self) -> None:
        """Without --explain the rating stands alone on its line."""
        output = self.render(show_breakdown=False)

        self.assertIn('Good', output)
        self.assertNotIn('TPS', output)
        self.assertNotIn('Pauses', output)
        self.assertNotIn('Missed', output)

    def test_breakdown_shown_with_explain(self) -> None:
        """With --explain every criterion of the score is detailed."""
        output = self.render(show_breakdown=True)

        self.assertIn('Good', output)
        self.assertIn('TPS', output)
        self.assertIn('Pauses', output)
        self.assertIn('Missed', output)


class TestTrainerCommandListing(StateFixtureMixin, unittest.TestCase):
    """An empty pool is an error for a session, not for a listing."""

    def run_command(
            self,
            *args: str,
            trainings: Trainings | None = None,
    ) -> tuple[int, str]:
        """
        Run a train command line over the state fixture.

        Returns:
            The exit code and the rendered output.

        """
        recorder = RichConsole(
            record=True, width=120, theme=Theme(console_theme),
        )
        options = get_parser().parse_args(['train', '-s', 'oll', *args])

        with (
                patch(
                    'term_timer.trainer.load_trainings',
                    return_value=trainings or self.make_trainings(),
                ),
                patch.object(trainer_mod, 'console', recorder),
        ):
            code = asyncio.run(trainer_mod.trainer(options))

        return code, ' '.join(recorder.export_text().split())

    def test_empty_state_pool_only_warns_the_listing(self) -> None:
        """A listing with nothing to show is not a failure."""
        code, output = self.run_command(
            '-e', 'stable', '-l',
            trainings=Trainings(method='CFOP', step='OLL', cases={}),
        )

        self.assertEqual(code, 0)
        self.assertIn('No case in state "stable"', output)
        self.assertNotIn('😱', output)

    def test_empty_state_pool_fails_the_session(self) -> None:
        """Without --list an empty pool still ends the command."""
        code, output = self.run_command(
            '-e', 'stable',
            trainings=Trainings(method='CFOP', step='OLL', cases={}),
        )

        self.assertEqual(code, 1)
        self.assertIn('😱', output)

    def test_empty_filter_pool_only_warns_the_listing(self) -> None:
        """An empty family filter warns the listing the same way."""
        code, output = self.run_command('-i', 'unknown-family', '-l')

        self.assertEqual(code, 0)
        self.assertIn('No case matching filter "unknown-family"', output)

    def test_unknown_case_still_fails_the_listing(self) -> None:
        """A bogus --cases code remains an error, listing or not."""
        code, output = self.run_command('-c', '999', '-l')

        self.assertEqual(code, 1)
        self.assertIn('is unknown', output)


class TestManualRatingKeys(unittest.TestCase):
    """The 1-4 keyboard keys map to the FSRS ratings."""

    def test_keys_map_to_ascending_ratings(self) -> None:
        """1=Again, 2=Hard, 3=Good, 4=Easy (ascending FSRS values)."""
        self.assertEqual(MANUAL_RATING_KEYS['1'], Rating.Again)
        self.assertEqual(MANUAL_RATING_KEYS['2'], Rating.Hard)
        self.assertEqual(MANUAL_RATING_KEYS['3'], Rating.Good)
        self.assertEqual(MANUAL_RATING_KEYS['4'], Rating.Easy)

    def test_only_four_keys(self) -> None:
        """Only the digits 1-4 are bound."""
        self.assertEqual(set(MANUAL_RATING_KEYS), {'1', '2', '3', '4'})


class TestTrainerSaveLine(unittest.TestCase):
    """The training prompt fits one line whatever it has to offer."""

    @staticmethod
    def make_trainer(*, bluetooth: bool = False) -> Trainer:
        """
        Build a minimal OLL trainer for display tests.

        Returns:
            Configured Trainer instance.

        """
        timer = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=[],
            states=[],
            free_play=False,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )
        if bluetooth:
            timer.bluetooth_interface = MagicMock()
        return timer

    def render(self, *, bluetooth: bool = False, **kwargs: bool) -> str:
        """
        Capture the console output of save_line.

        Returns:
            The rendered prompt text.

        """
        timer = self.make_trainer(bluetooth=bluetooth)
        with timer.console.capture() as capture:
            timer.save_line(**kwargs)
        return capture.get()

    def test_dnf_prompt_rates_again(self) -> None:
        """A DNF always rates Again, no rating key is offered."""
        output = self.render(dnf=True)

        self.assertIn('DNF', output)
        self.assertIn('Press any key to save and continue', output)
        self.assertNotIn('[1-4]', output)

    def test_manual_rating_prompt_leads_on_the_ratings(self) -> None:
        """Rating is the point, so no default action is advertised."""
        output = self.render(manual_rating=True)

        self.assertIn('Rating', output)
        self.assertIn('Rate from 1 to 4 to save and continue', output)
        self.assertIn('[1-4]', output)
        self.assertNotIn('Press any key', output)

    def test_auto_rating_prompt_offers_the_override(self) -> None:
        """An automatic rating still takes a 1-4 override."""
        output = self.render()

        self.assertIn('Press any key to save and continue', output)
        self.assertIn('[1-4]', output)

    def test_prompt_holds_on_a_single_line(self) -> None:
        """
        No variant wraps, whatever it offers.

        `clear_line` wipes one physical line: an enrolled prompt would
        leave its first row on screen for the rest of the session.
        """
        for output in (
                self.render(dnf=True),
                self.render(manual_rating=True),
                self.render(),
                self.render(bluetooth=True),
        ):
            self.assertNotIn('\n', output)


class TestSaveTrainingManualRating(unittest.IsolatedAsyncioTestCase):
    """save_training() collects a manual 1-4 rating when there is no BT."""

    CASE_CODE = 'T'

    def make_trainer(self) -> Trainer:
        """
        Build a no-Bluetooth PLL trainer with one rated case.

        Returns:
            A Trainer with fsrs_update on, no BT interface, and a single
            CaseTraining ready to be rated.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.bluetooth_interface = None
        timer.console = MagicMock()
        date = int(datetime.now(tz=UTC).timestamp())
        timer.trainings.add_timing(self.CASE_CODE, 2000, date)
        return timer

    def selected_case(self, timer: Trainer) -> object:
        """
        Return the Case object matching CASE_CODE from the trainer pool.

        Returns:
            The cubing_algs Case for CASE_CODE.

        """
        return next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    async def run_save(
            self, char: str,
    ) -> tuple[Trainer, MagicMock, bool]:
        """
        Run save_training with a fixed key and a captured update_card.

        Returns:
            Tuple of (trainer, update_card mock, quit flag).

        """
        timer = self.make_trainer()
        case = self.selected_case(timer)
        solve = Solve(
            date=datetime.now(tz=UTC).timestamp(),
            time=2_000_000_000,
            scramble="R U R' U'",
            moves=None,
        )
        update_card = MagicMock(return_value=Card())

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return char

        with (
            patch('term_timer.trainer.save_trainings'),
            patch('term_timer.trainer.SOUND_PLAYER'),
            patch.object(timer.fsrs_scheduler, 'update_card', update_card),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            quit_flag = await timer.save_training(case, solve)  # type: ignore[arg-type]
        return timer, update_card, quit_flag

    async def test_rating_key_updates_card(self) -> None:
        """Each 1-4 key updates the card with the mapped rating."""
        for char, rating in MANUAL_RATING_KEYS.items():
            timer, update_card, quit_flag = await self.run_save(char)
            update_card.assert_called_once()
            self.assertEqual(update_card.call_args.args[1], rating)
            self.assertFalse(quit_flag)
            self.assertEqual(
                len(timer.trainings.cases[self.CASE_CODE].timings), 1,
            )

    async def test_discard_key_pops_timing(self) -> None:
        """'z' discards the rep without updating the card and continues."""
        timer, update_card, quit_flag = await self.run_save('z')
        update_card.assert_not_called()
        self.assertFalse(quit_flag)
        # The discarded rep was the only content of the entry: it is
        # pruned entirely instead of being persisted empty.
        self.assertNotIn(self.CASE_CODE, timer.trainings.cases)

    async def test_quit_key_saves_and_quits(self) -> None:
        """'q' saves the timing without FSRS update and quits."""
        timer, update_card, quit_flag = await self.run_save('q')
        update_card.assert_not_called()
        self.assertTrue(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 1,
        )

    async def test_invalid_key_saves_without_fsrs(self) -> None:
        """Any unrecognised key saves the timing but skips FSRS update."""
        timer, update_card, quit_flag = await self.run_save('x')
        update_card.assert_not_called()
        self.assertFalse(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 1,
        )

    async def test_retry_key_pops_timing_and_asks_for_replay(self) -> None:
        """'r' discards the rep like 'z' and flags the replay."""
        timer, update_card, quit_flag = await self.run_save('r')
        update_card.assert_not_called()
        self.assertFalse(quit_flag)
        self.assertNotIn(self.CASE_CODE, timer.trainings.cases)
        self.assertTrue(timer.retry_requested)

    async def test_retry_key_is_not_an_unrated_save(self) -> None:
        """'r' is never swallowed as an unrecognised key keeping the time."""
        timer, _, _ = await self.run_save('r')
        self.assertEqual(timer.session_data, [])

    async def test_discard_key_does_not_ask_for_replay(self) -> None:
        """'z' discards without flagging any replay."""
        timer, _, _ = await self.run_save('z')
        self.assertFalse(timer.retry_requested)


class TestSaveTrainingAutoRatingOverride(unittest.IsolatedAsyncioTestCase):
    """In auto rating mode, the 1-4 keys override the pending rating."""

    CASE_CODE = 'T'

    def make_trainer(self) -> Trainer:
        """
        Build a PLL trainer simulating auto rating mode.

        Returns:
            A Trainer with fsrs_update on, a pending Good auto rating,
            and a single CaseTraining ready to be rated.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.bluetooth_interface = None
        timer.console = MagicMock()
        date = int(datetime.now(tz=UTC).timestamp())
        timer.trainings.add_timing(self.CASE_CODE, 2000, date)
        timer.fsrs_pending_rating = RatingBreakdown(
            rating=Rating.Good,
            time_s=2.0,
            executed_qtm=9,
            missed_qtm=0,
            pauses=0,
            tps=4.5,
            score=1.0,
        )
        return timer

    def selected_case(self, timer: Trainer) -> object:
        """
        Return the Case object matching CASE_CODE from the trainer pool.

        Returns:
            The cubing_algs Case for CASE_CODE.

        """
        return next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    async def run_save(
            self, char: str,
    ) -> tuple[Trainer, MagicMock, bool]:
        """
        Run save_training in auto rating mode with a fixed key.

        The fsrs_manual_rating property is forced to False to emulate a
        Bluetooth trainer in auto rating mode while keeping the simple
        keyboard input path.

        Returns:
            Tuple of (trainer, update_card mock, quit flag).

        """
        timer = self.make_trainer()
        case = self.selected_case(timer)
        solve = Solve(
            date=datetime.now(tz=UTC).timestamp(),
            time=2_000_000_000,
            scramble="R U R' U'",
            moves=None,
        )
        update_card = MagicMock(return_value=Card())

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return char

        with (
            patch('term_timer.trainer.save_trainings'),
            patch('term_timer.trainer.SOUND_PLAYER'),
            patch.object(
                Trainer,
                'fsrs_manual_rating',
                new_callable=PropertyMock,
                return_value=False,
            ),
            patch.object(timer.fsrs_scheduler, 'update_card', update_card),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            quit_flag = await timer.save_training(case, solve)  # type: ignore[arg-type]
        return timer, update_card, quit_flag

    async def test_rating_key_overrides_auto_rating(self) -> None:
        """A 1-4 key replaces the pending auto rating."""
        timer, update_card, quit_flag = await self.run_save('1')
        update_card.assert_called_once()
        self.assertEqual(update_card.call_args.args[1], Rating.Again)
        self.assertFalse(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 1,
        )

    async def test_plain_key_applies_pending_rating(self) -> None:
        """Any non-rating key saves with the pending auto rating."""
        timer, update_card, quit_flag = await self.run_save('x')
        update_card.assert_called_once()
        self.assertEqual(update_card.call_args.args[1], Rating.Good)
        self.assertFalse(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 1,
        )

    async def test_retry_key_skips_the_pending_rating(self) -> None:
        """'r' drops the rep instead of applying the auto rating."""
        timer, update_card, quit_flag = await self.run_save('r')
        update_card.assert_not_called()
        self.assertFalse(quit_flag)
        self.assertNotIn(self.CASE_CODE, timer.trainings.cases)
        self.assertTrue(timer.retry_requested)


class TestSaveTrainingPendingCardReuse(unittest.IsolatedAsyncioTestCase):
    """save_training() reuses the previewed card when ratings match."""

    CASE_CODE = 'T'

    def make_trainer(self) -> Trainer:
        """
        Build a PLL trainer with a pending Good rating and preview card.

        Returns:
            A Trainer with fsrs_update on, a pending Good auto rating,
            a previewed card, and a single CaseTraining ready to be
            rated.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.bluetooth_interface = None
        timer.console = MagicMock()
        date = int(datetime.now(tz=UTC).timestamp())
        timer.trainings.add_timing(self.CASE_CODE, 2000, date)
        timer.fsrs_pending_rating = RatingBreakdown(
            rating=Rating.Good,
            time_s=2.0,
            executed_qtm=9,
            missed_qtm=0,
            pauses=0,
            tps=4.5,
            score=1.0,
        )
        timer.fsrs_pending_card = Card()
        return timer

    def selected_case(self, timer: Trainer) -> object:
        """
        Return the Case object matching CASE_CODE from the trainer pool.

        Returns:
            The cubing_algs Case for CASE_CODE.

        """
        return next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    async def run_save(
            self, char: str, *, dnf: bool = False,
    ) -> tuple[Trainer, MagicMock, Card]:
        """
        Run save_training in auto rating mode with a fixed key.

        Returns:
            Tuple of (trainer, update_card mock, pending card).

        """
        timer = self.make_trainer()
        case = self.selected_case(timer)
        pending_card = cast('Card', timer.fsrs_pending_card)
        solve = Solve(
            date=datetime.now(tz=UTC).timestamp(),
            time=2_000_000_000,
            scramble="R U R' U'",
            moves=None,
        )
        update_card = MagicMock(return_value=Card())

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return char

        with (
            patch('term_timer.trainer.save_trainings'),
            patch('term_timer.trainer.SOUND_PLAYER'),
            patch.object(
                Trainer,
                'fsrs_manual_rating',
                new_callable=PropertyMock,
                return_value=False,
            ),
            patch.object(timer.fsrs_scheduler, 'update_card', update_card),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            await timer.save_training(case, solve, dnf=dnf)  # type: ignore[arg-type]
        return timer, update_card, pending_card

    async def test_plain_key_reuses_previewed_card(self) -> None:
        """Saving with the pending rating stores the previewed card."""
        timer, update_card, pending_card = await self.run_save('x')
        update_card.assert_not_called()
        self.assertIs(
            timer.trainings.cases[self.CASE_CODE].fsrs_card,
            pending_card,
        )

    async def test_matching_override_reuses_previewed_card(self) -> None:
        """An override equal to the pending rating keeps the preview."""
        timer, update_card, pending_card = await self.run_save('3')
        update_card.assert_not_called()
        self.assertIs(
            timer.trainings.cases[self.CASE_CODE].fsrs_card,
            pending_card,
        )

    async def test_diverging_override_recomputes_card(self) -> None:
        """An override different from the preview recomputes the card."""
        timer, update_card, pending_card = await self.run_save('1')
        update_card.assert_called_once()
        self.assertEqual(update_card.call_args.args[1], Rating.Again)
        self.assertIs(
            timer.trainings.cases[self.CASE_CODE].fsrs_card,
            update_card.return_value,
        )
        self.assertIsNot(
            timer.trainings.cases[self.CASE_CODE].fsrs_card,
            pending_card,
        )

    async def test_dnf_reuses_previewed_card(self) -> None:
        """A DNF save reuses the card previewed with Again."""
        timer, update_card, pending_card = await self.run_save(
            'x', dnf=True,
        )
        update_card.assert_not_called()
        self.assertIs(
            timer.trainings.cases[self.CASE_CODE].fsrs_card,
            pending_card,
        )

    async def test_no_pending_card_recomputes(self) -> None:
        """Without a previewed card the scheduler is called."""
        timer = self.make_trainer()
        timer.fsrs_pending_card = None
        case = self.selected_case(timer)
        solve = Solve(
            date=datetime.now(tz=UTC).timestamp(),
            time=2_000_000_000,
            scramble="R U R' U'",
            moves=None,
        )
        update_card = MagicMock(return_value=Card())

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return 'x'

        with (
            patch('term_timer.trainer.save_trainings'),
            patch('term_timer.trainer.SOUND_PLAYER'),
            patch.object(
                Trainer,
                'fsrs_manual_rating',
                new_callable=PropertyMock,
                return_value=False,
            ),
            patch.object(timer.fsrs_scheduler, 'update_card', update_card),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            await timer.save_training(case, solve)  # type: ignore[arg-type]

        update_card.assert_called_once()
        self.assertEqual(update_card.call_args.args[1], Rating.Good)
        self.assertIs(
            timer.trainings.cases[self.CASE_CODE].fsrs_card,
            update_card.return_value,
        )


class TestFSRSNewCaseBudget(unittest.IsolatedAsyncioTestCase):
    """fsrs_track_new_case() only consumes budget when a card was created."""

    CASE_CODE = 'T'

    def make_trainer(self) -> Trainer:
        """
        Build a no-Bluetooth PLL trainer with one new (card-less) case.

        Returns:
            A Trainer with fsrs_update on, no BT interface, and a single
            CaseTraining holding a timing but no FSRS card.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.bluetooth_interface = None
        timer.console = MagicMock()
        date = int(datetime.now(tz=UTC).timestamp())
        timer.trainings.add_timing(self.CASE_CODE, 2000, date)
        return timer

    def selected_case(self, timer: Trainer) -> object:
        """
        Return the Case object matching CASE_CODE from the trainer pool.

        Returns:
            The cubing_algs Case for CASE_CODE.

        """
        return next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    async def run_save_and_track(self, char: str) -> Trainer:
        """
        Run save_training with a fixed key then track the new case.

        Returns:
            The trainer, after fsrs_track_new_case(was_new_case=True).

        """
        timer = self.make_trainer()
        case = self.selected_case(timer)
        solve = Solve(
            date=datetime.now(tz=UTC).timestamp(),
            time=2_000_000_000,
            scramble="R U R' U'",
            moves=None,
        )

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return char

        with (
            patch('term_timer.trainer.save_trainings'),
            patch('term_timer.trainer.SOUND_PLAYER'),
            patch.object(
                timer.fsrs_scheduler,
                'update_card',
                MagicMock(return_value=Card()),
            ),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            await timer.save_training(case, solve)  # type: ignore[arg-type]

        timer.fsrs_track_new_case(self.CASE_CODE, was_new_case=True)
        return timer

    async def test_rated_new_case_consumes_budget(self) -> None:
        """A rated save on a new case increments the introduced count."""
        timer = await self.run_save_and_track('3')
        self.assertEqual(timer.fsrs_new_cases_introduced, 1)

    async def test_unrated_save_leaves_the_case_new(self) -> None:
        """No rating means no card: the case is still new to introduce."""
        timer = await self.run_save_and_track('x')
        self.assertEqual(timer.fsrs_new_cases_introduced, 0)

    async def test_discard_does_not_consume_budget(self) -> None:
        """A discarded rep on a new case leaves the budget intact."""
        timer = await self.run_save_and_track('z')
        self.assertEqual(timer.fsrs_new_cases_introduced, 0)

    async def test_known_case_never_consumes_budget(self) -> None:
        """A rated save on an already-known case is not counted."""
        timer = await self.run_save_and_track('3')
        timer.fsrs_track_new_case(self.CASE_CODE, was_new_case=False)
        self.assertEqual(timer.fsrs_new_cases_introduced, 1)


class TestSaveTrainingDNF(unittest.IsolatedAsyncioTestCase):
    """save_training(dnf=True) rates Again by default, never saves timing."""

    CASE_CODE = 'T'

    def make_trainer(self, *, with_timing: bool = False) -> Trainer:
        """
        Build a no-Bluetooth PLL trainer with FSRS enabled.

        Returns:
            A Trainer with fsrs_update on, no BT interface, and
            optionally one prior timing for CASE_CODE.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.bluetooth_interface = None
        timer.console = MagicMock()
        if with_timing:
            date = int(datetime.now(tz=UTC).timestamp())
            timer.trainings.add_timing(self.CASE_CODE, 2000, date)
        return timer

    def selected_case(self, timer: Trainer) -> object:
        """
        Return the Case object matching CASE_CODE from the trainer pool.

        Returns:
            The cubing_algs Case for CASE_CODE.

        """
        return next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    async def run_save(
            self, char: str, *, with_timing: bool = False,
    ) -> tuple[Trainer, MagicMock, bool]:
        """
        Run save_training(dnf=True) with a fixed key.

        Returns:
            Tuple of (trainer, update_card mock, quit flag).

        """
        timer = self.make_trainer(with_timing=with_timing)
        case = self.selected_case(timer)
        timer.date = datetime.now(tz=UTC).timestamp()
        solve = Solve(
            date=timer.date,
            time=2_000_000_000,
            scramble="R U R' U'",
            flag='DNF',
            moves=None,
        )
        update_card = MagicMock(return_value=Card())

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return char

        with (
            patch('term_timer.trainer.save_trainings'),
            patch('term_timer.trainer.SOUND_PLAYER'),
            patch.object(timer.fsrs_scheduler, 'update_card', update_card),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            quit_flag = await timer.save_training(
                case,  # type: ignore[arg-type]
                solve,
                dnf=True,
            )
        return timer, update_card, quit_flag

    async def test_any_key_rates_again_without_timing(self) -> None:
        """Any key applies an Again rating and records no timing."""
        timer, update_card, quit_flag = await self.run_save('x')
        update_card.assert_called_once()
        self.assertEqual(update_card.call_args.args[1], Rating.Again)
        self.assertFalse(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 0,
        )
        self.assertEqual(timer.session_data, [])

    async def test_creates_case_entry_with_card(self) -> None:
        """A DNF on a never-trained case creates an entry with a card."""
        timer, update_card, _ = await self.run_save('x')
        case_training = timer.trainings.cases[self.CASE_CODE]
        self.assertIsNotNone(case_training.fsrs_card)
        update_card.assert_called_once()

    async def test_rating_key_does_not_override_again(self) -> None:
        """A 1-4 key cannot override the Again rating on a DNF."""
        timer, update_card, quit_flag = await self.run_save('3')
        update_card.assert_called_once()
        self.assertEqual(update_card.call_args.args[1], Rating.Again)
        self.assertFalse(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 0,
        )

    async def test_discard_key_skips_rating(self) -> None:
        """'z' discards without rating or creating a case entry."""
        timer, update_card, quit_flag = await self.run_save('z')
        update_card.assert_not_called()
        self.assertFalse(quit_flag)
        self.assertNotIn(self.CASE_CODE, timer.trainings.cases)

    async def test_discard_keeps_prior_timings(self) -> None:
        """'z' on a trained case never pops an existing timing."""
        timer, update_card, _ = await self.run_save('z', with_timing=True)
        update_card.assert_not_called()
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 1,
        )

    async def test_quit_key_rates_again_and_quits(self) -> None:
        """'q' applies the Again rating and quits."""
        _, update_card, quit_flag = await self.run_save('q')
        update_card.assert_called_once()
        self.assertEqual(update_card.call_args.args[1], Rating.Again)
        self.assertTrue(quit_flag)

    async def test_quit_discard_key_skips_rating_and_quits(self) -> None:
        """'k' discards without rating and quits."""
        timer, update_card, quit_flag = await self.run_save('k')
        update_card.assert_not_called()
        self.assertTrue(quit_flag)
        self.assertNotIn(self.CASE_CODE, timer.trainings.cases)

    async def test_retry_key_skips_the_again_rating(self) -> None:
        """'r' on a DNF replays the case without rating it Again."""
        timer, update_card, quit_flag = await self.run_save('r')
        update_card.assert_not_called()
        self.assertFalse(quit_flag)
        self.assertNotIn(self.CASE_CODE, timer.trainings.cases)
        self.assertTrue(timer.retry_requested)

    async def test_retry_keeps_prior_timings(self) -> None:
        """'r' on a DNF never pops a timing of a previous rep."""
        timer, _, _ = await self.run_save('r', with_timing=True)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 1,
        )


class TestStartRetryLoop(unittest.IsolatedAsyncioTestCase):
    """start() replays the attempt for as long as a retry is asked for."""

    CASE_CODE = 'T'

    def make_trainer(self) -> Trainer:
        """
        Build a no-Bluetooth PLL trainer for the retry loop.

        Returns:
            A Trainer with a mocked console and no training data.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.bluetooth_interface = None
        timer.console = MagicMock()
        return timer

    def make_pending(self, timer: Trainer) -> PendingAttempt:
        """
        Build the attempt a retry would ask start() to replay.

        Returns:
            A PendingAttempt for CASE_CODE with a fixed scramble.

        """
        case = next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )
        return PendingAttempt(
            case,
            parse_moves("R U R' U'"),
            parse_moves("U R U' R'"),
            was_new_case=True,
        )

    async def run_start(
            self, outcomes: list[tuple[bool, PendingAttempt | None]],
    ) -> tuple[bool, list[PendingAttempt | None]]:
        """
        Run start() over a scripted sequence of run_attempt() outcomes.

        Returns:
            Tuple of (start() return value, attempts passed to run_attempt).

        """
        timer = self.make_trainer()
        received: list[PendingAttempt | None] = []
        remaining = list(outcomes)

        async def fake_run_attempt(
                pending: PendingAttempt | None = None,
        ) -> tuple[bool, PendingAttempt | None]:
            await asyncio.sleep(0)
            received.append(pending)
            return remaining.pop(0)

        with patch.object(timer, 'run_attempt', side_effect=fake_run_attempt):
            keep_going = await timer.start()

        return keep_going, received

    async def test_single_attempt_returns_immediately(self) -> None:
        """Without any retry, start() runs a single attempt."""
        keep_going, received = await self.run_start([(True, None)])

        self.assertTrue(keep_going)
        self.assertEqual(received, [None])

    async def test_retry_replays_the_same_attempt(self) -> None:
        """A retry feeds the pending attempt back into run_attempt()."""
        timer = self.make_trainer()
        pending = self.make_pending(timer)

        keep_going, received = await self.run_start(
            [(True, pending), (True, None)],
        )

        self.assertTrue(keep_going)
        self.assertEqual(received, [None, pending])

    async def test_retries_are_not_limited(self) -> None:
        """Consecutive retries all replay before start() returns once."""
        timer = self.make_trainer()
        pending = self.make_pending(timer)

        keep_going, received = await self.run_start(
            [(True, pending), (True, pending), (True, pending), (True, None)],
        )

        self.assertTrue(keep_going)
        self.assertEqual(len(received), 4)
        self.assertEqual(received[1:], [pending, pending, pending])

    async def test_quit_after_retry_is_propagated(self) -> None:
        """Quitting the replayed attempt still quits the session."""
        timer = self.make_trainer()
        pending = self.make_pending(timer)

        keep_going, received = await self.run_start(
            [(True, pending), (False, None)],
        )

        self.assertFalse(keep_going)
        self.assertEqual(len(received), 2)


class TestSolutionDisplayInLearningPhase(unittest.TestCase):
    """The solution is shown for cards in Learning or Relearning state."""

    CASE_CODE = 'T'

    def make_trainer(self, *, free_play: bool = False) -> Trainer:
        """
        Build a no-Bluetooth PLL trainer with one trained case.

        Returns:
            A Trainer with a mocked console and a single CaseTraining.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=free_play,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.bluetooth_interface = None
        timer.console = MagicMock()
        timer.scramble_oriented = parse_moves("R U R' U'")
        timer.cube_orientation_moves = parse_moves('')
        date = int(datetime.now(tz=UTC).timestamp())
        timer.trainings.add_timing(self.CASE_CODE, 2000, date)
        return timer

    def selected_case(self, timer: Trainer) -> object:
        """
        Return the Case object matching CASE_CODE from the trainer pool.

        Returns:
            The cubing_algs Case for CASE_CODE.

        """
        return next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    def set_card_state(self, timer: Trainer, state: State) -> None:
        """Attach an FSRS card with the given state to the trained case."""
        card = Card()
        card.state = state
        timer.trainings.cases[self.CASE_CODE].fsrs_card = card

    @staticmethod
    def printed_text(timer: Trainer) -> str:
        """
        Join every console.print argument into a single string.

        Returns:
            Concatenated text of all printed arguments.

        """
        console = cast('MagicMock', timer.console)
        return ' '.join(
            str(arg)
            for call in console.print.call_args_list
            for arg in call.args
        )

    def test_no_card_is_not_learning(self) -> None:
        """A case without an FSRS card is not in a learning phase."""
        timer = self.make_trainer()
        case = self.selected_case(timer)
        self.assertFalse(timer.case_in_learning_phase(case))  # type: ignore[arg-type]

    def test_learning_card_is_learning(self) -> None:
        """A card in Learning state is in a learning phase."""
        timer = self.make_trainer()
        self.set_card_state(timer, State.Learning)
        case = self.selected_case(timer)
        self.assertTrue(timer.case_in_learning_phase(case))  # type: ignore[arg-type]

    def test_relearning_card_is_learning(self) -> None:
        """A card in Relearning state is in a learning phase."""
        timer = self.make_trainer()
        self.set_card_state(timer, State.Relearning)
        case = self.selected_case(timer)
        self.assertTrue(timer.case_in_learning_phase(case))  # type: ignore[arg-type]

    def test_review_card_is_not_learning(self) -> None:
        """A card in Review state is not in a learning phase."""
        timer = self.make_trainer()
        self.set_card_state(timer, State.Review)
        case = self.selected_case(timer)
        self.assertFalse(timer.case_in_learning_phase(case))  # type: ignore[arg-type]

    def test_fsrs_disabled_is_not_learning(self) -> None:
        """With FSRS off (free play) the learning phase is never active."""
        timer = self.make_trainer(free_play=True)
        timer.trainings.add_timing(
            self.CASE_CODE, 2000, int(datetime.now(tz=UTC).timestamp()),
        )
        self.set_card_state(timer, State.Learning)
        case = self.selected_case(timer)
        self.assertFalse(timer.case_in_learning_phase(case))  # type: ignore[arg-type]

    def test_start_line_shows_solution_when_learning(self) -> None:
        """start_line prints the solution for a Learning card without -v."""
        timer = self.make_trainer()
        self.set_card_state(timer, State.Learning)
        case = self.selected_case(timer)
        solution = parse_moves("R U R' U' R' F R F'")
        timer.start_line(MagicMock(), case, solution)  # type: ignore[arg-type]
        self.assertIn('Solution', self.printed_text(timer))

    def test_start_line_hides_solution_when_review(self) -> None:
        """start_line keeps the solution hidden for a Review card."""
        timer = self.make_trainer()
        self.set_card_state(timer, State.Review)
        case = self.selected_case(timer)
        solution = parse_moves("R U R' U' R' F R F'")
        timer.start_line(MagicMock(), case, solution)  # type: ignore[arg-type]
        self.assertNotIn('Solution', self.printed_text(timer))


class TestBuildReferenceSolution(TestSolutionDisplayInLearningPhase):
    """build_reference_solution prepends the pre-AUF without mutating."""

    def test_empty_solution_returns_empty(self) -> None:
        """No solution yields an empty reference."""
        timer = self.make_trainer()
        reference = timer.build_reference_solution(parse_moves(''))
        self.assertEqual(len(reference), 0)

    def test_no_pre_auf_returns_solution_unchanged(self) -> None:
        """When no pre-AUF is needed the solution is returned as-is."""
        timer = self.make_trainer()
        solution = parse_moves("R U R' U' R' F R F'")
        with patch.object(timer, 'compute_pre_aufs', return_value=None):
            reference = timer.build_reference_solution(solution)
        self.assertEqual(str(reference), str(solution))

    def test_pre_auf_is_prepended(self) -> None:
        """A computed pre-AUF is prepended to the solution."""
        timer = self.make_trainer()
        solution = parse_moves("R U R' U' R' F R F'")
        with patch.object(timer, 'compute_pre_aufs', return_value=Move('U2')):
            reference = timer.build_reference_solution(solution)
        self.assertEqual(str(reference), "U2 R U R' U' R' F R F'")

    def test_original_solution_is_not_mutated(self) -> None:
        """Building the reference leaves the source solution untouched."""
        timer = self.make_trainer()
        solution = parse_moves("R U R' U' R' F R F'")
        original = str(solution)
        with patch.object(timer, 'compute_pre_aufs', return_value=Move('U2')):
            timer.build_reference_solution(solution)
        self.assertEqual(str(solution), original)

    def test_pre_auf_merges_with_leading_u_move(self) -> None:
        """A pre-AUF merges into a solution starting with the same move."""
        timer = self.make_trainer()
        solution = parse_moves("U R U R' U' R' F R F'")
        with patch.object(timer, 'compute_pre_aufs', return_value=Move('U')):
            reference = timer.build_reference_solution(solution)
        self.assertEqual(str(reference), "U2 R U R' U' R' F R F'")

    def test_pre_auf_cancels_leading_reverse_u_move(self) -> None:
        """A pre-AUF cancels out against an opposite leading U move."""
        timer = self.make_trainer()
        solution = parse_moves("U' R U R' U' R' F R F'")
        with patch.object(timer, 'compute_pre_aufs', return_value=Move('U')):
            reference = timer.build_reference_solution(solution)
        self.assertEqual(str(reference), "R U R' U' R' F R F'")

    def test_pre_auf_merges_with_leading_u2_move(self) -> None:
        """A pre-AUF merges into a solution starting with a double move."""
        timer = self.make_trainer()
        solution = parse_moves("U2 R U R' U' R' F R F'")
        with patch.object(timer, 'compute_pre_aufs', return_value=Move('U')):
            reference = timer.build_reference_solution(solution)
        self.assertEqual(str(reference), "U' R U R' U' R' F R F'")

    def test_pre_auf_not_merged_with_unrelated_first_move(self) -> None:
        """A pre-AUF is left as a separate move before an unrelated face."""
        timer = self.make_trainer()
        solution = parse_moves("F R U R' U' R' F R F'")
        with patch.object(timer, 'compute_pre_aufs', return_value=Move('U')):
            reference = timer.build_reference_solution(solution)
        self.assertEqual(str(reference), "U F R U R' U' R' F R F'")

    def test_pre_auf_not_merged_with_opposite_layer_move(self) -> None:
        """A pre-AUF on U is not merged with a same-axis D layer move."""
        timer = self.make_trainer()
        solution = parse_moves("D R U R' U' R' F R F'")
        with patch.object(timer, 'compute_pre_aufs', return_value=Move('U')):
            reference = timer.build_reference_solution(solution)
        self.assertEqual(str(reference), "U D R U R' U' R' F R F'")


class TestResolveSolution(unittest.TestCase):
    """resolve_solution prefers the stored solution over cubing_algs."""

    CASE_CODE = 'T'

    @staticmethod
    def make_trainer(
            cases: 'dict[str, CaseTraining] | None' = None,
    ) -> Trainer:
        """
        Build a no-Bluetooth PLL trainer with optional preloaded trainings.

        Returns:
            A Trainer with a mocked console.

        """
        trainings = Trainings(
            method='CFOP', step='PLL', cases=cases or {},
        )
        with patch(
            'term_timer.trainer.load_trainings', return_value=trainings,
        ):
            timer = Trainer(
                step='pll',
                case_codes=[TestResolveSolution.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        timer.console = MagicMock()
        return timer

    def case_for(self, timer: Trainer) -> object:
        """
        Return the Case object matching CASE_CODE from the trainer pool.

        Returns:
            The cubing_algs Case for CASE_CODE.

        """
        return next(
            tc.case for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    def training_case_for(self, timer: Trainer) -> object:
        """
        Return the TrainingCase matching CASE_CODE from the trainer pool.

        Returns:
            The TrainingCase for CASE_CODE.

        """
        return next(
            tc for tc in timer.cases if tc.case.code == self.CASE_CODE
        )

    def test_resolve_uses_custom_solution_when_defined(self) -> None:
        """A stored custom solution is returned in place of main_algorithm."""
        timer = self.make_trainer(
            {
                self.CASE_CODE: CaseTraining(
                    code=self.CASE_CODE,
                    last_date=0,
                    timings=[],
                    solution="R U R' U'",
                ),
            },
        )
        case = self.case_for(timer)

        resolved = timer.resolve_solution(case)  # type: ignore[arg-type]

        self.assertEqual(str(resolved), "R U R' U'")

    def test_resolve_falls_back_without_custom_solution(self) -> None:
        """Without a stored solution the cubing_algs main algorithm is used."""
        timer = self.make_trainer()
        case = self.case_for(timer)

        resolved = timer.resolve_solution(case)  # type: ignore[arg-type]

        self.assertEqual(str(resolved), str(case.main_algorithm))  # type: ignore[attr-defined]

    def test_resolve_uses_invalid_custom_solution_as_is(self) -> None:
        """An invalid custom solution is used as-is, not validated."""
        timer = self.make_trainer(
            {
                self.CASE_CODE: CaseTraining(
                    code=self.CASE_CODE,
                    last_date=0,
                    timings=[],
                    solution='not a move',
                ),
            },
        )
        case = self.case_for(timer)

        resolved = timer.resolve_solution(case)  # type: ignore[arg-type]

        self.assertEqual(str(resolved), 'not a move')

    def test_training_case_carries_custom_solution(self) -> None:
        """get_cases injects the resolved solution into the TrainingCase."""
        timer = self.make_trainer(
            {
                self.CASE_CODE: CaseTraining(
                    code=self.CASE_CODE,
                    last_date=0,
                    timings=[],
                    solution="R U R' U'",
                ),
            },
        )
        training_case = self.training_case_for(timer)

        self.assertEqual(str(training_case.solution), "R U R' U'")  # type: ignore[attr-defined]

    def test_training_case_defaults_to_main_algorithm(self) -> None:
        """Without a custom solution the TrainingCase carries main_algorithm."""
        timer = self.make_trainer()
        training_case = self.training_case_for(timer)

        self.assertEqual(
            str(training_case.solution),  # type: ignore[attr-defined]
            str(training_case.case.main_algorithm),  # type: ignore[attr-defined]
        )

    def test_fixed_case_step_has_empty_solution(self) -> None:
        """Cross-like steps (fixed training_case) carry an empty solution."""
        empty = Trainings(method='CFOP', step='CROSS', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            timer = Trainer(
                step='cross',
                case_codes=[],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )

        self.assertEqual(str(timer.cases[0].solution), '')


class TestSpeedTrend(unittest.TestCase):
    """speed_trend compares the current Ao5 to the best Ao12 ever."""

    def test_not_enough_history(self) -> None:
        """Fewer than TREND_MIN_TIMINGS timings yields no trend."""
        stats = Statistics([1000] * (TREND_MIN_TIMINGS - 1))
        self.assertEqual(Trainer.speed_trend(stats), '')

    def test_at_peak(self) -> None:
        """A current Ao5 at the peak level is an upward trend."""
        stats = Statistics([1000] * TREND_MIN_TIMINGS)
        self.assertIn('↗', Trainer.speed_trend(stats))

    def test_near_peak_within_tolerance(self) -> None:
        """A current Ao5 within 10% of the peak is still upward."""
        stats = Statistics([1000] * TREND_MIN_TIMINGS + [1080] * 5)
        self.assertIn('↗', Trainer.speed_trend(stats))

    def test_plateau(self) -> None:
        """A current Ao5 between 10% and 30% above peak is a plateau."""
        stats = Statistics([1000] * TREND_MIN_TIMINGS + [1200] * 5)
        self.assertIn('→', Trainer.speed_trend(stats))

    def test_degraded(self) -> None:
        """A current Ao5 over 30% above peak is a downward trend."""
        stats = Statistics([1000] * TREND_MIN_TIMINGS + [1400] * 5)
        trend = Trainer.speed_trend(stats)
        self.assertIn('↘', trend)
        self.assertIn('+40%', trend)

    def test_timing_cells_include_trend(self) -> None:
        """timing_cells merges Ao5 and trend into a single cell."""
        muted = '[muted]N/A[/muted]'
        cells = Trainer.timing_cells(None, muted)
        self.assertEqual(len(cells), 5)
        self.assertEqual(cells[-1], muted)


class TestBestCells(unittest.TestCase):
    """best_cells summarizes the best times of a summary row."""

    def test_no_practiced_case(self) -> None:
        """A state without any practiced case is fully muted."""
        cells = Trainer.best_cells([])
        self.assertEqual(cells, ['[muted]N/A[/muted]'] * 3)

    def test_best_average_worst(self) -> None:
        """The cells hold the minimum, the mean and the maximum."""
        cells = Trainer.best_cells(
            [1_000_000_000, 2_000_000_000, 6_000_000_000],
        )
        self.assertIn('1.00', cells[0])
        self.assertIn('3.00', cells[1])
        self.assertIn('6.00', cells[2])


class TestSummaryCases(unittest.TestCase):
    """summary_cases recaps card states and best times under the table."""

    # OLL codes covering one case per card state, plus an unseen one.
    STABLE_CODE = '01'
    REVIEW_CODE = '02'
    LEARNING_CODE = '03'
    NEW_CODE = '04'

    def make_case_trainings(self) -> dict[str, CaseTraining]:
        """
        Build one training entry per card state, all but one practiced.

        Returns:
            CaseTraining entries keyed by OLL case code.

        """
        now = datetime.now(tz=UTC)
        recent = int(now.timestamp())

        stable = Card()
        stable.state = State.Review
        stable.due = now + timedelta(days=3)

        review = Card()
        review.state = State.Review
        review.due = now - timedelta(days=1)

        learning = Card()
        learning.due = now - timedelta(minutes=5)

        return {
            self.STABLE_CODE: CaseTraining(
                code=self.STABLE_CODE, last_date=recent,
                timings=[1000, 3000], fsrs_card=stable,
            ),
            self.REVIEW_CODE: CaseTraining(
                code=self.REVIEW_CODE, last_date=recent,
                timings=[4000], fsrs_card=review,
            ),
            self.LEARNING_CODE: CaseTraining(
                code=self.LEARNING_CODE, last_date=recent,
                timings=[], fsrs_card=learning,
            ),
        }

    def summarize(self) -> str:
        """
        Render the summary of the four controlled cases.

        Returns:
            The recorded console output.

        """
        trainings = Trainings(
            method='CFOP', step='OLL', cases=self.make_case_trainings(),
        )

        with patch(
            'term_timer.trainer.load_trainings', return_value=trainings,
        ):
            timer = Trainer(
                step='oll',
                case_codes=[],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )

        recorder = RichConsole(
            record=True, width=120, theme=Theme(console_theme),
        )
        timer.console = recorder

        collection = {
            case.code: case
            for case in get_collection('CFOP/OLL').cases.values()
        }
        valid_cases = {
            code: collection[code]
            for code in (
                self.STABLE_CODE, self.REVIEW_CODE,
                self.LEARNING_CODE, self.NEW_CODE,
            )
        }
        timer.summary_cases(valid_cases)

        return ' '.join(recorder.export_text().split())

    def test_one_row_per_populated_state(self) -> None:
        """Each card state holding a case gets its own row."""
        output = self.summarize()

        self.assertIn('New 1 0', output)
        self.assertIn('Review 1 1 4.00 4.00 4.00', output)
        self.assertIn('Stable 1 0 1.00 1.00 1.00', output)

    def test_empty_state_is_skipped(self) -> None:
        """A card state without any case is left out of the table."""
        output = self.summarize()

        self.assertNotIn('Relearning', output)

    def test_total_row_covers_every_case(self) -> None:
        """The total row counts all the cases and their best times."""
        output = self.summarize()

        self.assertIn('Total 4 2 1.00 2.50 4.00', output)

    def test_state_without_timing_is_muted(self) -> None:
        """A state whose cases are never practiced shows no best time."""
        output = self.summarize()

        self.assertIn('Learning 1 1 N/A N/A N/A', output)
