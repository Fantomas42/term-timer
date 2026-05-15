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
