"""Tests for trainer."""
import unittest
from random import Random

from cubing_algs.cases import get_collection

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
    """fsrs_selection and fsrs_update behave correctly across option combinations."""

    def make_trainer(
            self,
            filters: list[str] | None = None,
            case_codes: list[str] | None = None,
            oldest: int = 0,
            slowest: int = 0,
            random: int = 0,
    ) -> Trainer:
        """Build a minimal OLL Trainer for testing."""
        return Trainer(
            step='oll',
            case_codes=case_codes or [],
            oldest=oldest,
            slowest=slowest,
            filters=filters or [],
            free_play=True,
            show_solution=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
            random=random,
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
        """fsrs_selection is False with --cases: FSRS does not drive selection."""
        timer = self.make_trainer(case_codes=['01', '02'])
        self.assertFalse(timer.fsrs_selection)

    def test_fsrs_selection_false_with_random(self) -> None:
        """fsrs_selection is False with --random: FSRS does not drive selection."""
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
