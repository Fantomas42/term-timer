"""Tests for cheers generation."""
# ruff: noqa: PLR6301, PLR0913, PLR0917, DOC201, FBT001, FBT002
import unittest
from typing import TYPE_CHECKING
from typing import Literal
from unittest.mock import Mock
from unittest.mock import patch

from cubing_algs.algorithm import Algorithm

from term_timer.cheers import generate_solve_cheers
from term_timer.cheers import get_auf_cheer
from term_timer.cheers import get_cross_cheer
from term_timer.cheers import get_fluency_cheer
from term_timer.cheers import get_missed_moves_cheer
from term_timer.cheers import get_no_pauses_cheer
from term_timer.cheers import get_optimal_f2l_cheer
from term_timer.cheers import get_optimal_ll_cheer
from term_timer.cheers import get_recognition_cheer
from term_timer.cheers import get_score_cheer
from term_timer.cheers import get_skip_cheer
from term_timer.cheers import get_step_recognition_cheer
from term_timer.cheers import get_time_cheer
from term_timer.cheers import get_tps_cheer
from term_timer.cheers import get_xcross_cheer
from term_timer.cheers import is_optimal_ll_step
from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.methods.types import StepSummary


class TestGetCrossCheer(unittest.TestCase):
    """Tests for get_cross_cheer function."""

    def create_step_summary(
        self,
        name: str,
        htm: int,
    ) -> 'StepSummary':
        """Create a mock StepSummary with specified name and HTM."""
        moves_mock = Mock()
        moves_mock.metrics.htm = htm
        return {
            'type': 'step',
            'name': name,
            'moves': Mock(spec=Algorithm),
            'moves_reoriented': Mock(spec=Algorithm),
            'moves_humanized': Mock(spec=Algorithm),
            'moves_prettified': moves_mock,
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [None, None],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': '',
            'case_infos': [],
            'facelets': '',
        }

    def test_optimal_cross_4_htm(self) -> None:
        """Test optimal cross cheer for exactly 4 HTM."""
        summary = [self.create_step_summary('Cross', 4)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, 'Optimal cross in 4 HTM!')

    def test_optimal_cross_3_htm(self) -> None:
        """Test optimal cross cheer for less than 4 HTM."""
        summary = [self.create_step_summary('Cross', 3)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, 'Optimal cross in 3 HTM!')

    def test_optimal_cross_1_htm(self) -> None:
        """Test optimal cross cheer for 1 HTM."""
        summary = [self.create_step_summary('Cross', 1)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, 'Optimal cross in 1 HTM!')

    def test_efficient_cross_5_htm(self) -> None:
        """Test efficient cross cheer for 5 HTM."""
        summary = [self.create_step_summary('Cross', 5)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, 'Efficient cross in 5 HTM.')

    def test_efficient_cross_6_htm(self) -> None:
        """Test efficient cross cheer for exactly 6 HTM."""
        summary = [self.create_step_summary('Cross', 6)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, 'Efficient cross in 6 HTM.')

    def test_no_cheer_for_7_htm(self) -> None:
        """Test no cheer returned for cross with more than 6 HTM."""
        summary = [self.create_step_summary('Cross', 7)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, '')

    def test_no_cheer_for_10_htm(self) -> None:
        """Test no cheer returned for inefficient cross."""
        summary = [self.create_step_summary('Cross', 10)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, '')

    def test_no_cross_in_summary(self) -> None:
        """Test no cheer when Cross step is not in summary."""
        summary = [self.create_step_summary('F2L 1', 5)]
        result = get_cross_cheer(summary)
        self.assertEqual(result, '')

    def test_empty_summary(self) -> None:
        """Test no cheer for empty summary list."""
        summary: list[StepSummary] = []
        result = get_cross_cheer(summary)
        self.assertEqual(result, '')


class TestGetXcrossCheer(unittest.TestCase):
    """Tests for get_xcross_cheer function."""

    def create_step_summary(self, name: str) -> 'StepSummary':
        """Create a mock StepSummary with specified name."""
        return {
            'type': 'step',
            'name': name,
            'moves': Mock(spec=Algorithm),
            'moves_reoriented': Mock(spec=Algorithm),
            'moves_humanized': Mock(spec=Algorithm),
            'moves_prettified': Mock(spec=Algorithm),
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [None, None],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': '',
            'case_infos': [],
            'facelets': '',
        }

    def test_xcross_present(self) -> None:
        """Test cheer when XCross is present in summary."""
        summary = [self.create_step_summary('XCross')]
        result = get_xcross_cheer(summary)
        self.assertEqual(result, 'Solved with XCross.')

    def test_xcross_with_number(self) -> None:
        """Test cheer when XCross step has a number."""
        summary = [self.create_step_summary('XCross 1')]
        result = get_xcross_cheer(summary)
        self.assertEqual(result, 'Solved with XCross 1.')

    def test_xcross_in_middle(self) -> None:
        """Test XCross cheer when step contains XCross in name."""
        summary = [self.create_step_summary('Some XCross Step')]
        result = get_xcross_cheer(summary)
        self.assertEqual(result, 'Solved with Some XCross Step.')

    def test_no_xcross(self) -> None:
        """Test no cheer when XCross is not in summary."""
        summary = [
            self.create_step_summary('Cross'),
            self.create_step_summary('F2L 1'),
        ]
        result = get_xcross_cheer(summary)
        self.assertEqual(result, '')

    def test_empty_summary(self) -> None:
        """Test no cheer for empty summary."""
        summary: list[StepSummary] = []
        result = get_xcross_cheer(summary)
        self.assertEqual(result, '')

    def test_case_sensitive_xcross(self) -> None:
        """Test that lowercase xcross does not trigger cheer."""
        summary = [self.create_step_summary('xcross')]
        result = get_xcross_cheer(summary)
        self.assertEqual(result, '')


class TestGetMissedMovesCheer(unittest.TestCase):
    """Tests for get_missed_moves_cheer function."""

    def test_no_missed_moves(self) -> None:
        """Test cheer when there are no missed moves."""
        solve = Mock()
        solve.all_missed_moves = 0
        result = get_missed_moves_cheer(solve)
        self.assertEqual(result, 'Perfect execution - no wasted moves!')

    def test_with_missed_moves(self) -> None:
        """Test no cheer when there are missed moves."""
        solve = Mock()
        solve.all_missed_moves = 5
        result = get_missed_moves_cheer(solve)
        self.assertEqual(result, '')

    def test_with_one_missed_move(self) -> None:
        """Test no cheer for single missed move."""
        solve = Mock()
        solve.all_missed_moves = 1
        result = get_missed_moves_cheer(solve)
        self.assertEqual(result, '')

    def test_with_many_missed_moves(self) -> None:
        """Test no cheer for many missed moves."""
        solve = Mock()
        solve.all_missed_moves = 100
        result = get_missed_moves_cheer(solve)
        self.assertEqual(result, '')


class TestGetScoreCheer(unittest.TestCase):
    """Tests for get_score_cheer function."""

    def test_score_exactly_16(self) -> None:
        """Test cheer when score is exactly 16."""
        solve = Mock()
        solve.score = 16.0
        result = get_score_cheer(solve)
        self.assertEqual(result, 'Excellent solve score of 16.00.')

    def test_score_above_16(self) -> None:
        """Test cheer when score is above 16."""
        solve = Mock()
        solve.score = 18.5
        result = get_score_cheer(solve)
        self.assertEqual(result, 'Excellent solve score of 18.50.')

    def test_score_maximum(self) -> None:
        """Test cheer with maximum score."""
        solve = Mock()
        solve.score = 20.0
        result = get_score_cheer(solve)
        self.assertEqual(result, 'Excellent solve score of 20.00.')

    def test_score_below_16(self) -> None:
        """Test no cheer when score is below 16."""
        solve = Mock()
        solve.score = 15.99
        result = get_score_cheer(solve)
        self.assertEqual(result, '')

    def test_score_zero(self) -> None:
        """Test no cheer for zero score."""
        solve = Mock()
        solve.score = 0.0
        result = get_score_cheer(solve)
        self.assertEqual(result, '')

    def test_score_negative(self) -> None:
        """Test no cheer for negative score."""
        solve = Mock()
        solve.score = -5.0
        result = get_score_cheer(solve)
        self.assertEqual(result, '')

    def test_score_formatting(self) -> None:
        """Test score formatting with decimals."""
        solve = Mock()
        solve.score = 16.123456
        result = get_score_cheer(solve)
        self.assertEqual(result, 'Excellent solve score of 16.12.')


class TestGetTimeCheer(unittest.TestCase):
    """Tests for get_time_cheer function."""

    def test_time_10_seconds(self) -> None:
        """Test time cheer for 10 second solve."""
        solve = Mock()
        solve.time = 10 * SECOND
        result = get_time_cheer(solve)
        self.assertEqual(result, 'Keep pushing for sub-9.5.')

    def test_time_20_seconds(self) -> None:
        """Test time cheer for 20 second solve."""
        solve = Mock()
        solve.time = 20 * SECOND
        result = get_time_cheer(solve)
        self.assertEqual(result, 'Keep pushing for sub-19.0.')

    def test_time_one_second(self) -> None:
        """Test time cheer for 1 second solve."""
        solve = Mock()
        solve.time = 1 * SECOND
        result = get_time_cheer(solve)
        self.assertEqual(result, 'Keep pushing for sub-0.9.')

    def test_time_with_decimals(self) -> None:
        """Test time cheer with decimal seconds."""
        solve = Mock()
        solve.time = 12345678900
        result = get_time_cheer(solve)
        expected_target = 12345678900 * 0.95 / SECOND
        self.assertEqual(result, f'Keep pushing for sub-{expected_target:.1f}.')

    def test_time_very_fast(self) -> None:
        """Test time cheer for very fast solve."""
        solve = Mock()
        solve.time = int(5.5 * SECOND)
        result = get_time_cheer(solve)
        expected_target = 5.5 * 0.95
        self.assertEqual(result, f'Keep pushing for sub-{expected_target:.1f}.')

    def test_time_always_returns_message(self) -> None:
        """Test that time cheer always returns a message."""
        solve = Mock()
        solve.time = 100 * SECOND
        result = get_time_cheer(solve)
        self.assertNotEqual(result, '')
        self.assertIn('Keep pushing for sub-', result)


class TestGetFluencyCheer(unittest.TestCase):
    """Tests for get_fluency_cheer function."""

    def test_fluency_exactly_90(self) -> None:
        """Test cheer for fluency of exactly 90."""
        solve = Mock()
        solve.fluency = 90
        result = get_fluency_cheer(solve)
        self.assertEqual(result, 'Buttery smooth! 90/100 fluency.')

    def test_fluency_above_90(self) -> None:
        """Test cheer for fluency above 90."""
        solve = Mock()
        solve.fluency = 95
        result = get_fluency_cheer(solve)
        self.assertEqual(result, 'Buttery smooth! 95/100 fluency.')

    def test_fluency_100(self) -> None:
        """Test cheer for perfect fluency."""
        solve = Mock()
        solve.fluency = 100
        result = get_fluency_cheer(solve)
        self.assertEqual(result, 'Buttery smooth! 100/100 fluency.')

    def test_fluency_exactly_80(self) -> None:
        """Test cheer for fluency of exactly 80."""
        solve = Mock()
        solve.fluency = 80
        result = get_fluency_cheer(solve)
        self.assertEqual(result, 'Great flow - 80/100 fluency.')

    def test_fluency_between_80_and_90(self) -> None:
        """Test cheer for fluency between 80 and 90."""
        solve = Mock()
        solve.fluency = 85
        result = get_fluency_cheer(solve)
        self.assertEqual(result, 'Great flow - 85/100 fluency.')

    def test_fluency_89(self) -> None:
        """Test cheer for fluency just below 90."""
        solve = Mock()
        solve.fluency = 89
        result = get_fluency_cheer(solve)
        self.assertEqual(result, 'Great flow - 89/100 fluency.')

    def test_fluency_below_80(self) -> None:
        """Test no cheer for fluency below 80."""
        solve = Mock()
        solve.fluency = 79
        result = get_fluency_cheer(solve)
        self.assertEqual(result, '')

    def test_fluency_zero(self) -> None:
        """Test no cheer for zero fluency."""
        solve = Mock()
        solve.fluency = 0
        result = get_fluency_cheer(solve)
        self.assertEqual(result, '')

    def test_fluency_low(self) -> None:
        """Test no cheer for low fluency."""
        solve = Mock()
        solve.fluency = 50
        result = get_fluency_cheer(solve)
        self.assertEqual(result, '')


class TestGetTpsCheer(unittest.TestCase):
    """Tests for get_tps_cheer function."""

    def test_tps_exactly_5(self) -> None:
        """Test cheer for TPS of exactly 5.0."""
        solve = Mock()
        solve.tps = 5.0
        result = get_tps_cheer(solve)
        self.assertEqual(result, 'Lightning fingers! 5.0 TPS.')

    def test_tps_above_5(self) -> None:
        """Test cheer for TPS above 5.0."""
        solve = Mock()
        solve.tps = 6.5
        result = get_tps_cheer(solve)
        self.assertEqual(result, 'Lightning fingers! 6.5 TPS.')

    def test_tps_very_high(self) -> None:
        """Test cheer for very high TPS."""
        solve = Mock()
        solve.tps = 10.0
        result = get_tps_cheer(solve)
        self.assertEqual(result, 'Lightning fingers! 10.0 TPS.')

    def test_tps_exactly_4_5(self) -> None:
        """Test cheer for TPS of exactly 4.5."""
        solve = Mock()
        solve.tps = 4.5
        result = get_tps_cheer(solve)
        self.assertEqual(result, 'Fast turning at 4.5 TPS.')

    def test_tps_between_4_5_and_5(self) -> None:
        """Test cheer for TPS between 4.5 and 5.0."""
        solve = Mock()
        solve.tps = 4.8
        result = get_tps_cheer(solve)
        self.assertEqual(result, 'Fast turning at 4.8 TPS.')

    def test_tps_below_4_5(self) -> None:
        """Test no cheer for TPS below 4.5."""
        solve = Mock()
        solve.tps = 4.4
        result = get_tps_cheer(solve)
        self.assertEqual(result, '')

    def test_tps_zero(self) -> None:
        """Test no cheer for zero TPS."""
        solve = Mock()
        solve.tps = 0.0
        result = get_tps_cheer(solve)
        self.assertEqual(result, '')

    def test_tps_low(self) -> None:
        """Test no cheer for low TPS."""
        solve = Mock()
        solve.tps = 2.0
        result = get_tps_cheer(solve)
        self.assertEqual(result, '')


class TestGetNoPausesCheer(unittest.TestCase):
    """Tests for get_no_pauses_cheer function."""

    def test_zero_pauses(self) -> None:
        """Test cheer for zero pauses."""
        solve = Mock()
        solve.execution_pauses = 0
        result = get_no_pauses_cheer(solve)
        self.assertEqual(result, 'Flawless lookahead - zero pauses!')

    def test_one_pause(self) -> None:
        """Test cheer for one pause."""
        solve = Mock()
        solve.execution_pauses = 1
        result = get_no_pauses_cheer(solve)
        self.assertEqual(result, 'Excellent lookahead throughout.')

    def test_two_pauses(self) -> None:
        """Test cheer for exactly two pauses."""
        solve = Mock()
        solve.execution_pauses = 2
        result = get_no_pauses_cheer(solve)
        self.assertEqual(result, 'Excellent lookahead throughout.')

    def test_three_pauses(self) -> None:
        """Test no cheer for three pauses."""
        solve = Mock()
        solve.execution_pauses = 3
        result = get_no_pauses_cheer(solve)
        self.assertEqual(result, '')

    def test_many_pauses(self) -> None:
        """Test no cheer for many pauses."""
        solve = Mock()
        solve.execution_pauses = 10
        result = get_no_pauses_cheer(solve)
        self.assertEqual(result, '')


class TestGetSkipCheer(unittest.TestCase):
    """Tests for get_skip_cheer function."""

    def create_step_summary(
        self,
        name: str,
        step_type: Literal['step', 'skipped', 'substep', 'virtual'] = 'step',
    ) -> 'StepSummary':
        """Create a mock StepSummary with specified name and type."""
        return {
            'type': step_type,
            'name': name,
            'moves': Mock(spec=Algorithm),
            'moves_reoriented': Mock(spec=Algorithm),
            'moves_humanized': Mock(spec=Algorithm),
            'moves_prettified': Mock(spec=Algorithm),
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [None, None],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': '',
            'case_infos': [],
            'facelets': '',
        }

    def test_full_last_layer_skip(self) -> None:
        """Test cheer for both OLL and PLL skipped."""
        summary = [
            self.create_step_summary('OLL', 'skipped'),
            self.create_step_summary('PLL', 'skipped'),
        ]
        result = get_skip_cheer(summary)
        self.assertEqual(result, 'Full last layer skip!')

    def test_oll_skip_only(self) -> None:
        """Test cheer for OLL skip only."""
        summary = [
            self.create_step_summary('OLL', 'skipped'),
            self.create_step_summary('PLL', 'step'),
        ]
        result = get_skip_cheer(summary)
        self.assertEqual(result, 'OLL skip!')

    def test_pll_skip_only(self) -> None:
        """Test cheer for PLL skip only."""
        summary = [
            self.create_step_summary('OLL', 'step'),
            self.create_step_summary('PLL', 'skipped'),
        ]
        result = get_skip_cheer(summary)
        self.assertEqual(result, 'PLL skip!')

    def test_no_skips(self) -> None:
        """Test no cheer when there are no skips."""
        summary = [
            self.create_step_summary('OLL', 'step'),
            self.create_step_summary('PLL', 'step'),
        ]
        result = get_skip_cheer(summary)
        self.assertEqual(result, '')

    def test_empty_summary(self) -> None:
        """Test no cheer for empty summary."""
        summary: list[StepSummary] = []
        result = get_skip_cheer(summary)
        self.assertEqual(result, '')

    def test_virtual_type_not_counted(self) -> None:
        """Test that virtual type steps are not counted as skips."""
        summary = [
            self.create_step_summary('OLL', 'virtual'),
            self.create_step_summary('PLL', 'virtual'),
        ]
        result = get_skip_cheer(summary)
        self.assertEqual(result, '')

    def test_substep_type_not_counted(self) -> None:
        """Test that substep type steps are not counted as skips."""
        summary = [
            self.create_step_summary('OLL', 'substep'),
            self.create_step_summary('PLL', 'substep'),
        ]
        result = get_skip_cheer(summary)
        self.assertEqual(result, '')


class TestGetRecognitionCheer(unittest.TestCase):
    """Tests for get_recognition_cheer function."""

    def test_recognition_exactly_20_percent(self) -> None:
        """Test cheer for recognition of exactly 20%."""
        solve = Mock()
        solve.time = 10 * SECOND
        solve.recognition_time = 2 * SECOND
        result = get_recognition_cheer(solve)
        self.assertEqual(result, 'Sharp recognition throughout!')

    def test_recognition_below_20_percent(self) -> None:
        """Test cheer for recognition below 20%."""
        solve = Mock()
        solve.time = 10 * SECOND
        solve.recognition_time = int(1.5 * SECOND)
        result = get_recognition_cheer(solve)
        self.assertEqual(result, 'Sharp recognition throughout!')

    def test_recognition_zero_percent(self) -> None:
        """Test cheer for zero recognition time."""
        solve = Mock()
        solve.time = 10 * SECOND
        solve.recognition_time = 0
        result = get_recognition_cheer(solve)
        self.assertEqual(result, 'Sharp recognition throughout!')

    def test_recognition_above_20_percent(self) -> None:
        """Test no cheer for recognition above 20%."""
        solve = Mock()
        solve.time = 10 * SECOND
        solve.recognition_time = int(2.1 * SECOND)
        result = get_recognition_cheer(solve)
        self.assertEqual(result, '')

    def test_recognition_50_percent(self) -> None:
        """Test no cheer for high recognition time."""
        solve = Mock()
        solve.time = 10 * SECOND
        solve.recognition_time = 5 * SECOND
        result = get_recognition_cheer(solve)
        self.assertEqual(result, '')

    def test_recognition_zero_time_solve(self) -> None:
        """Test no cheer when solve time is zero."""
        solve = Mock()
        solve.time = 0
        solve.recognition_time = 0
        result = get_recognition_cheer(solve)
        self.assertEqual(result, '')

    def test_recognition_negative_time_solve(self) -> None:
        """Test no cheer when solve time is negative."""
        solve = Mock()
        solve.time = -10 * SECOND
        solve.recognition_time = 1 * SECOND
        result = get_recognition_cheer(solve)
        self.assertEqual(result, '')


class TestGetAufCheer(unittest.TestCase):
    """Tests for get_auf_cheer function."""

    def test_zero_aufs(self) -> None:
        """Test cheer for zero AUFs."""
        solve = Mock()
        solve.aufs = 0
        result = get_auf_cheer(solve)
        self.assertEqual(result, 'No AUFs - great case mastery.')

    def test_one_auf(self) -> None:
        """Test cheer for one AUF."""
        solve = Mock()
        solve.aufs = 1
        result = get_auf_cheer(solve)
        self.assertEqual(result, 'Minimal AUFs - great prediction.')

    def test_two_aufs(self) -> None:
        """Test cheer for exactly two AUFs."""
        solve = Mock()
        solve.aufs = 2
        result = get_auf_cheer(solve)
        self.assertEqual(result, 'Minimal AUFs - great prediction.')

    def test_three_aufs(self) -> None:
        """Test no cheer for three AUFs."""
        solve = Mock()
        solve.aufs = 3
        result = get_auf_cheer(solve)
        self.assertEqual(result, '')

    def test_many_aufs(self) -> None:
        """Test no cheer for many AUFs."""
        solve = Mock()
        solve.aufs = 10
        result = get_auf_cheer(solve)
        self.assertEqual(result, '')


class TestIsOptimalLlStep(unittest.TestCase):
    """Tests for is_optimal_ll_step function."""

    def create_step_summary(
        self,
        name: str = 'OLL',
        step_type: Literal['step', 'skipped', 'substep', 'virtual'] = 'step',
        case: str = 'Case1',
        pre_auf: int | None = None,
        post_auf: int | None = None,
        htm: int = 10,
    ) -> 'StepSummary':
        """Create a mock StepSummary."""
        moves_mock = Mock()
        moves_mock.metrics.htm = htm
        moves_mock.transform = Mock(return_value=moves_mock)
        return {
            'type': step_type,
            'name': name,
            'moves': Mock(spec=Algorithm),
            'moves_reoriented': Mock(spec=Algorithm),
            'moves_humanized': Mock(spec=Algorithm),
            'moves_prettified': moves_mock,
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [pre_auf, post_auf],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': case,
            'case_infos': [],
            'facelets': '',
        }

    @patch('term_timer.cheers.get_case')
    def test_optimal_step_no_aufs(self, mock_get_case: Mock) -> None:
        """Test optimal step with no AUFs."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        step = self.create_step_summary(htm=10)
        result = is_optimal_ll_step(step)

        self.assertTrue(result)
        mock_get_case.assert_called_once_with('OLL', 'Case1')

    @patch('term_timer.cheers.get_case')
    def test_not_optimal_wrong_htm(self, mock_get_case: Mock) -> None:
        """Test step is not optimal when HTM does not match."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        step = self.create_step_summary(htm=11)
        result = is_optimal_ll_step(step)

        self.assertFalse(result)

    def test_skipped_type_returns_false(self) -> None:
        """Test that skipped type steps return False."""
        step = self.create_step_summary(step_type='skipped')
        result = is_optimal_ll_step(step)
        self.assertFalse(result)

    def test_virtual_type_returns_false(self) -> None:
        """Test that virtual type steps return False."""
        step = self.create_step_summary(step_type='virtual')
        result = is_optimal_ll_step(step)
        self.assertFalse(result)

    def test_no_case_returns_false(self) -> None:
        """Test that steps without a case return False."""
        step = self.create_step_summary(case='')
        result = is_optimal_ll_step(step)
        self.assertFalse(result)

    def test_with_pre_auf_returns_false(self) -> None:
        """Test that steps with pre-AUF return False."""
        step = self.create_step_summary(pre_auf=1)
        result = is_optimal_ll_step(step)
        self.assertFalse(result)

    def test_with_post_auf_returns_false(self) -> None:
        """Test that steps with post-AUF return False."""
        step = self.create_step_summary(post_auf=1)
        result = is_optimal_ll_step(step)
        self.assertFalse(result)

    def test_with_both_aufs_returns_false(self) -> None:
        """Test that steps with both AUFs return False."""
        step = self.create_step_summary(pre_auf=1, post_auf=2)
        result = is_optimal_ll_step(step)
        self.assertFalse(result)

    @patch('term_timer.cheers.get_case')
    def test_no_optimal_htm_returns_false(self, mock_get_case: Mock) -> None:
        """Test that steps without optimal HTM return False."""
        mock_case = Mock()
        mock_case.optimal_htm = None
        mock_get_case.return_value = mock_case

        step = self.create_step_summary()
        result = is_optimal_ll_step(step)

        self.assertFalse(result)

    @patch('term_timer.cheers.get_case')
    def test_zero_optimal_htm_returns_false(
        self, mock_get_case: Mock,
    ) -> None:
        """Test that steps with zero optimal HTM return False."""
        mock_case = Mock()
        mock_case.optimal_htm = 0
        mock_get_case.return_value = mock_case

        step = self.create_step_summary(htm=0)
        result = is_optimal_ll_step(step)

        self.assertFalse(result)


class TestGetOptimalLlCheer(unittest.TestCase):
    """Tests for get_optimal_ll_cheer function."""

    def create_step_summary(
        self,
        name: str = 'OLL',
        step_type: Literal['step', 'skipped', 'substep', 'virtual'] = 'step',
        case: str = 'Case1',
    ) -> 'StepSummary':
        """Create a mock StepSummary."""
        moves_mock = Mock()
        moves_mock.metrics.htm = 10
        moves_mock.transform = Mock(return_value=moves_mock)
        return {
            'type': step_type,
            'name': name,
            'moves': Mock(spec=Algorithm),
            'moves_reoriented': Mock(spec=Algorithm),
            'moves_humanized': Mock(spec=Algorithm),
            'moves_prettified': moves_mock,
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [None, None],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': case,
            'case_infos': [],
            'facelets': '',
        }

    @patch('term_timer.cheers.is_optimal_ll_step')
    def test_both_oll_and_pll_optimal(
        self, mock_is_optimal: Mock,
    ) -> None:
        """Test cheer for both OLL and PLL optimal."""
        mock_is_optimal.return_value = True
        summary = [
            self.create_step_summary('OLL'),
            self.create_step_summary('PLL'),
        ]
        result = get_optimal_ll_cheer(summary)
        self.assertEqual(result, 'Perfect last layer - optimal OLL and PLL!')

    @patch('term_timer.cheers.is_optimal_ll_step')
    def test_only_oll_optimal(self, mock_is_optimal: Mock) -> None:
        """Test cheer for only OLL optimal."""
        def is_optimal_side_effect(step: 'StepSummary') -> bool:
            return step['name'] == 'OLL'

        mock_is_optimal.side_effect = is_optimal_side_effect
        summary = [
            self.create_step_summary('OLL'),
            self.create_step_summary('PLL'),
        ]
        result = get_optimal_ll_cheer(summary)
        self.assertEqual(result, 'Optimal OLL execution!')

    @patch('term_timer.cheers.is_optimal_ll_step')
    def test_only_pll_optimal(self, mock_is_optimal: Mock) -> None:
        """Test cheer for only PLL optimal."""
        def is_optimal_side_effect(step: 'StepSummary') -> bool:
            return step['name'] == 'PLL'

        mock_is_optimal.side_effect = is_optimal_side_effect
        summary = [
            self.create_step_summary('OLL'),
            self.create_step_summary('PLL'),
        ]
        result = get_optimal_ll_cheer(summary)
        self.assertEqual(result, 'Optimal PLL execution!')

    @patch('term_timer.cheers.is_optimal_ll_step')
    def test_neither_optimal(self, mock_is_optimal: Mock) -> None:
        """Test no cheer when neither OLL nor PLL is optimal."""
        mock_is_optimal.return_value = False
        summary = [
            self.create_step_summary('OLL'),
            self.create_step_summary('PLL'),
        ]
        result = get_optimal_ll_cheer(summary)
        self.assertEqual(result, '')

    @patch('term_timer.cheers.is_optimal_ll_step')
    def test_empty_summary(self, mock_is_optimal: Mock) -> None:
        """Test no cheer for empty summary."""
        summary: list[StepSummary] = []
        result = get_optimal_ll_cheer(summary)
        self.assertEqual(result, '')
        mock_is_optimal.assert_not_called()

    @patch('term_timer.cheers.is_optimal_ll_step')
    def test_only_f2l_steps(self, mock_is_optimal: Mock) -> None:
        """Test no cheer when only F2L steps are present."""
        summary = [
            self.create_step_summary('F2L 1'),
            self.create_step_summary('F2L 2'),
        ]
        result = get_optimal_ll_cheer(summary)
        self.assertEqual(result, '')
        mock_is_optimal.assert_not_called()


class TestGetOptimalF2lCheer(unittest.TestCase):
    """Tests for get_optimal_f2l_cheer function."""

    def create_step_summary(
        self,
        name: str = 'F2L 1',
        step_type: Literal['step', 'skipped', 'substep', 'virtual'] = 'step',
        case: str = 'Case1',
        htm: int = 10,
    ) -> 'StepSummary':
        """Create a mock StepSummary."""
        moves_mock = Mock()
        moves_mock.metrics.htm = htm
        return {
            'type': step_type,
            'name': name,
            'moves': Mock(spec=Algorithm),
            'moves_reoriented': Mock(spec=Algorithm),
            'moves_humanized': Mock(spec=Algorithm),
            'moves_prettified': moves_mock,
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [None, None],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': case,
            'case_infos': [],
            'facelets': '',
        }

    @patch('term_timer.cheers.get_case')
    def test_all_four_f2l_pairs_optimal(self, mock_get_case: Mock) -> None:
        """Test cheer when all 4 F2L pairs are optimal."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', htm=10),
            self.create_step_summary('F2L 2', htm=10),
            self.create_step_summary('F2L 3', htm=10),
            self.create_step_summary('F2L 4', htm=10),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, 'All F2L pairs solved optimally!')

    @patch('term_timer.cheers.get_case')
    def test_three_f2l_pairs_optimal(self, mock_get_case: Mock) -> None:
        """Test cheer when 3 F2L pairs are optimal."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', htm=10),
            self.create_step_summary('F2L 2', htm=10),
            self.create_step_summary('F2L 3', htm=10),
            self.create_step_summary('F2L 4', htm=15),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '3 F2L pairs solved optimally.')

    @patch('term_timer.cheers.get_case')
    def test_two_f2l_pairs_optimal(self, mock_get_case: Mock) -> None:
        """Test cheer when 2 F2L pairs are optimal."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', htm=10),
            self.create_step_summary('F2L 2', htm=10),
            self.create_step_summary('F2L 3', htm=15),
            self.create_step_summary('F2L 4', htm=15),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '2 F2L pairs solved optimally.')

    @patch('term_timer.cheers.get_case')
    def test_one_f2l_pair_optimal(self, mock_get_case: Mock) -> None:
        """Test no cheer when only 1 F2L pair is optimal."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', htm=10),
            self.create_step_summary('F2L 2', htm=15),
            self.create_step_summary('F2L 3', htm=15),
            self.create_step_summary('F2L 4', htm=15),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '')

    @patch('term_timer.cheers.get_case')
    def test_no_f2l_pairs_optimal(self, mock_get_case: Mock) -> None:
        """Test no cheer when no F2L pairs are optimal."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', htm=15),
            self.create_step_summary('F2L 2', htm=15),
            self.create_step_summary('F2L 3', htm=15),
            self.create_step_summary('F2L 4', htm=15),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '')

    @patch('term_timer.cheers.get_case')
    def test_skipped_f2l_not_counted(self, mock_get_case: Mock) -> None:
        """Test that skipped F2L steps are not counted."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', step_type='skipped', htm=10),
            self.create_step_summary('F2L 2', htm=10),
            self.create_step_summary('F2L 3', htm=10),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '2 F2L pairs solved optimally.')

    @patch('term_timer.cheers.get_case')
    def test_virtual_f2l_not_counted(self, mock_get_case: Mock) -> None:
        """Test that virtual F2L steps are not counted."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', step_type='virtual', htm=10),
            self.create_step_summary('F2L 2', htm=10),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '')

    @patch('term_timer.cheers.get_case')
    def test_f2l_without_case_not_counted(
        self, mock_get_case: Mock,
    ) -> None:
        """Test that F2L steps without case are not counted."""
        summary = [
            self.create_step_summary('F2L 1', case='', htm=10),
            self.create_step_summary('F2L 2', case='Case1', htm=10),
            self.create_step_summary('F2L 3', case='Case1', htm=10),
        ]
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '2 F2L pairs solved optimally.')

    @patch('term_timer.cheers.get_case')
    def test_no_optimal_htm_not_counted(self, mock_get_case: Mock) -> None:
        """Test that F2L steps without optimal HTM are not counted."""
        mock_case = Mock()
        mock_case.optimal_htm = None
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('F2L 1', htm=10),
            self.create_step_summary('F2L 2', htm=10),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '')

    def test_empty_summary(self) -> None:
        """Test no cheer for empty summary."""
        summary: list[StepSummary] = []
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '')

    @patch('term_timer.cheers.get_case')
    def test_non_f2l_steps_ignored(self, mock_get_case: Mock) -> None:
        """Test that non-F2L steps are ignored."""
        mock_case = Mock()
        mock_case.optimal_htm = 10
        mock_get_case.return_value = mock_case

        summary = [
            self.create_step_summary('Cross', htm=10),
            self.create_step_summary('OLL', htm=10),
            self.create_step_summary('F2L 1', htm=10),
            self.create_step_summary('F2L 2', htm=10),
        ]
        result = get_optimal_f2l_cheer(summary)
        self.assertEqual(result, '2 F2L pairs solved optimally.')


class TestGetStepRecognitionCheer(unittest.TestCase):
    """Tests for get_step_recognition_cheer function."""

    def create_step_summary(
        self,
        name: str = 'OLL',
        step_type: Literal['step', 'skipped', 'substep', 'virtual'] = 'step',
        step_recognition_percent: float = 5.0,
    ) -> 'StepSummary':
        """Create a mock StepSummary."""
        return {
            'type': step_type,
            'name': name,
            'moves': Mock(spec=Algorithm),
            'moves_reoriented': Mock(spec=Algorithm),
            'moves_humanized': Mock(spec=Algorithm),
            'moves_prettified': Mock(spec=Algorithm),
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [None, None],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': step_recognition_percent,
            'increment': 0,
            'case': '',
            'case_infos': [],
            'facelets': '',
        }

    def test_instant_oll_recognition(self) -> None:
        """Test cheer for instant OLL recognition."""
        summary = [self.create_step_summary('OLL', step_recognition_percent=5)]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, 'Instant OLL recognition!')

    def test_instant_pll_recognition(self) -> None:
        """Test cheer for instant PLL recognition."""
        summary = [self.create_step_summary('PLL', step_recognition_percent=8)]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, 'Instant PLL recognition!')

    def test_recognition_exactly_10_percent(self) -> None:
        """Test no cheer for recognition of exactly 10%."""
        summary = [
            self.create_step_summary('OLL', step_recognition_percent=10),
        ]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, '')

    def test_recognition_above_10_percent(self) -> None:
        """Test no cheer for recognition above 10%."""
        summary = [
            self.create_step_summary('OLL', step_recognition_percent=15),
        ]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, '')

    def test_recognition_zero_percent(self) -> None:
        """Test cheer for zero percent recognition."""
        summary = [self.create_step_summary('OLL', step_recognition_percent=0)]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, 'Instant OLL recognition!')

    def test_skipped_step_ignored(self) -> None:
        """Test that skipped steps are ignored."""
        summary = [
            self.create_step_summary(
                'OLL', step_type='skipped', step_recognition_percent=5,
            ),
        ]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, '')

    def test_virtual_step_ignored(self) -> None:
        """Test that virtual steps are ignored."""
        summary = [
            self.create_step_summary(
                'OLL', step_type='virtual', step_recognition_percent=5,
            ),
        ]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, '')

    def test_non_ll_step_ignored(self) -> None:
        """Test that non-OLL/PLL steps are ignored."""
        summary = [
            self.create_step_summary(
                'F2L 1', step_recognition_percent=5,
            ),
        ]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, '')

    def test_first_matching_step_wins(self) -> None:
        """Test that only first matching step generates cheer."""
        summary = [
            self.create_step_summary('OLL', step_recognition_percent=5),
            self.create_step_summary('PLL', step_recognition_percent=3),
        ]
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, 'Instant OLL recognition!')

    def test_empty_summary(self) -> None:
        """Test no cheer for empty summary."""
        summary: list[StepSummary] = []
        result = get_step_recognition_cheer(summary)
        self.assertEqual(result, '')


class TestGenerateSolveCheers(unittest.TestCase):
    """Tests for generate_solve_cheers function."""

    def create_mock_solve(
        self,
        has_method: bool = True,
    ) -> Mock:
        """Create a mock Solve object."""
        solve = Mock()
        solve.all_missed_moves = 0
        solve.score = 16.0
        solve.time = 10 * SECOND
        solve.fluency = 90
        solve.tps = 5.0
        solve.execution_pauses = 0
        solve.recognition_time = int(1.5 * SECOND)
        solve.aufs = 2

        if has_method:
            solve.method_applied = Mock()
            solve.method_applied.summary = []
        else:
            solve.method_applied = None

        return solve

    def test_no_method_applied_returns_empty(self) -> None:
        """Test that empty list is returned when no method is applied."""
        solve = self.create_mock_solve(has_method=False)
        result = generate_solve_cheers(solve)
        self.assertEqual(result, [])

    @patch('term_timer.cheers.get_cross_cheer')
    @patch('term_timer.cheers.get_xcross_cheer')
    @patch('term_timer.cheers.get_skip_cheer')
    @patch('term_timer.cheers.get_optimal_f2l_cheer')
    @patch('term_timer.cheers.get_optimal_ll_cheer')
    @patch('term_timer.cheers.get_missed_moves_cheer')
    @patch('term_timer.cheers.get_fluency_cheer')
    @patch('term_timer.cheers.get_tps_cheer')
    @patch('term_timer.cheers.get_no_pauses_cheer')
    @patch('term_timer.cheers.get_recognition_cheer')
    @patch('term_timer.cheers.get_step_recognition_cheer')
    @patch('term_timer.cheers.get_auf_cheer')
    @patch('term_timer.cheers.get_score_cheer')
    @patch('term_timer.cheers.get_time_cheer')
    def test_all_cheers_called(
        self,
        mock_time: Mock,
        mock_score: Mock,
        mock_auf: Mock,
        mock_step_rec: Mock,
        mock_rec: Mock,
        mock_pauses: Mock,
        mock_tps: Mock,
        mock_fluency: Mock,
        mock_missed: Mock,
        mock_opt_ll: Mock,
        mock_opt_f2l: Mock,
        mock_skip: Mock,
        mock_xcross: Mock,
        mock_cross: Mock,
    ) -> None:
        """Test that all cheer functions are called."""
        solve = self.create_mock_solve()
        mock_time.return_value = 'time cheer'

        generate_solve_cheers(solve)

        mock_cross.assert_called_once()
        mock_xcross.assert_called_once()
        mock_skip.assert_called_once()
        mock_opt_f2l.assert_called_once()
        mock_opt_ll.assert_called_once()
        mock_missed.assert_called_once_with(solve)
        mock_fluency.assert_called_once_with(solve)
        mock_tps.assert_called_once_with(solve)
        mock_pauses.assert_called_once_with(solve)
        mock_rec.assert_called_once_with(solve)
        mock_step_rec.assert_called_once()
        mock_auf.assert_called_once_with(solve)
        mock_score.assert_called_once_with(solve)
        mock_time.assert_called_once_with(solve)

    @patch('term_timer.cheers.get_cross_cheer')
    @patch('term_timer.cheers.get_xcross_cheer')
    @patch('term_timer.cheers.get_skip_cheer')
    @patch('term_timer.cheers.get_optimal_f2l_cheer')
    @patch('term_timer.cheers.get_optimal_ll_cheer')
    @patch('term_timer.cheers.get_missed_moves_cheer')
    @patch('term_timer.cheers.get_fluency_cheer')
    @patch('term_timer.cheers.get_tps_cheer')
    @patch('term_timer.cheers.get_no_pauses_cheer')
    @patch('term_timer.cheers.get_recognition_cheer')
    @patch('term_timer.cheers.get_step_recognition_cheer')
    @patch('term_timer.cheers.get_auf_cheer')
    @patch('term_timer.cheers.get_score_cheer')
    @patch('term_timer.cheers.get_time_cheer')
    def test_filters_empty_cheers(
        self,
        mock_time: Mock,
        mock_score: Mock,
        mock_auf: Mock,
        mock_step_rec: Mock,
        mock_rec: Mock,
        mock_pauses: Mock,
        mock_tps: Mock,
        mock_fluency: Mock,
        mock_missed: Mock,
        mock_opt_ll: Mock,
        mock_opt_f2l: Mock,
        mock_skip: Mock,
        mock_xcross: Mock,
        mock_cross: Mock,
    ) -> None:
        """Test that empty strings are filtered from results."""
        solve = self.create_mock_solve()

        mock_cross.return_value = 'Cross cheer'
        mock_xcross.return_value = ''
        mock_skip.return_value = 'Skip cheer'
        mock_opt_f2l.return_value = ''
        mock_opt_ll.return_value = ''
        mock_missed.return_value = 'Missed cheer'
        mock_fluency.return_value = ''
        mock_tps.return_value = 'TPS cheer'
        mock_pauses.return_value = ''
        mock_rec.return_value = ''
        mock_step_rec.return_value = ''
        mock_auf.return_value = ''
        mock_score.return_value = ''
        mock_time.return_value = 'Time cheer'

        result = generate_solve_cheers(solve)

        self.assertEqual(result, [
            'Cross cheer',
            'Skip cheer',
            'Missed cheer',
            'TPS cheer',
            'Time cheer',
        ])

    @patch('term_timer.cheers.get_cross_cheer')
    @patch('term_timer.cheers.get_xcross_cheer')
    @patch('term_timer.cheers.get_skip_cheer')
    @patch('term_timer.cheers.get_optimal_f2l_cheer')
    @patch('term_timer.cheers.get_optimal_ll_cheer')
    @patch('term_timer.cheers.get_missed_moves_cheer')
    @patch('term_timer.cheers.get_fluency_cheer')
    @patch('term_timer.cheers.get_tps_cheer')
    @patch('term_timer.cheers.get_no_pauses_cheer')
    @patch('term_timer.cheers.get_recognition_cheer')
    @patch('term_timer.cheers.get_step_recognition_cheer')
    @patch('term_timer.cheers.get_auf_cheer')
    @patch('term_timer.cheers.get_score_cheer')
    @patch('term_timer.cheers.get_time_cheer')
    def test_returns_only_time_when_all_else_empty(
        self,
        mock_time: Mock,
        mock_score: Mock,
        mock_auf: Mock,
        mock_step_rec: Mock,
        mock_rec: Mock,
        mock_pauses: Mock,
        mock_tps: Mock,
        mock_fluency: Mock,
        mock_missed: Mock,
        mock_opt_ll: Mock,
        mock_opt_f2l: Mock,
        mock_skip: Mock,
        mock_xcross: Mock,
        mock_cross: Mock,
    ) -> None:
        """Test that at least time cheer is returned."""
        solve = self.create_mock_solve()

        for mock_func in [
            mock_cross, mock_xcross, mock_skip, mock_opt_f2l,
            mock_opt_ll, mock_missed, mock_fluency, mock_tps,
            mock_pauses, mock_rec, mock_step_rec, mock_auf,
            mock_score,
        ]:
            mock_func.return_value = ''

        mock_time.return_value = 'Keep pushing for sub-9.5.'

        result = generate_solve_cheers(solve)

        self.assertEqual(result, ['Keep pushing for sub-9.5.'])
