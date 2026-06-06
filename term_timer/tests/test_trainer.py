"""Tests for trainer."""
import asyncio
import unittest
from datetime import UTC
from datetime import datetime
from random import Random
from unittest.mock import MagicMock
from unittest.mock import patch

from cubing_algs.cases import get_collection
from fsrs import Card
from fsrs import Rating

from term_timer.fsrs.storage import Trainings
from term_timer.solve import Solve
from term_timer.trainer import MANUAL_RATING_KEYS
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
            free_play=True,
            show_solution=False,
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
            free_play=True,
            show_solution=False,
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
            free_play=True,
            show_solution=False,
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
            free_play=True,
            show_solution=False,
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
            free_play=True,
            show_solution=False,
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
            free_play=True,
            show_solution=False,
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
            free_play=True,
            show_solution=False,
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
            free_play=True,
            show_solution=False,
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
            Configured Trainer instance with free_play enabled.

        """
        return Trainer(
            step='oll',
            case_codes=case_codes or [],
            oldest=oldest,
            slowest=slowest,
            random=random,
            new_cases_limit=5,
            filters=filters or [],
            free_play=True,
            show_solution=False,
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
                case_codes=[],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                free_play=False,
                show_solution=False,
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
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 0,
        )

    async def test_quit_key_discards_and_quits(self) -> None:
        """'q' discards the unrated rep and quits."""
        timer, update_card, quit_flag = await self.run_save('q')
        update_card.assert_not_called()
        self.assertTrue(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 0,
        )

    async def test_invalid_key_discards_and_continues(self) -> None:
        """Any unrecognised key discards the unrated rep and continues."""
        timer, update_card, quit_flag = await self.run_save('x')
        update_card.assert_not_called()
        self.assertFalse(quit_flag)
        self.assertEqual(
            len(timer.trainings.cases[self.CASE_CODE].timings), 0,
        )
