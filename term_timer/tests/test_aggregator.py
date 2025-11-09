"""Tests for aggregator."""
# ruff: noqa: PT019
import unittest
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.aggregator import analyse_solve_worker

if TYPE_CHECKING:
    from term_timer.solve import Solve
    from term_timer.types import StepAnalysis


class TestAnalyseSolveWorker(unittest.TestCase):
    """Tests for analyse_solve_worker function."""

    def test_analyse_solve_worker_not_advanced(self) -> None:
        """Test that worker returns empty results for non-advanced solve."""
        solve = Mock()
        solve.advanced = False

        result = analyse_solve_worker(solve, 'method', full=True)

        self.assertEqual(result, {'steps': {}, 'score': 0.0, 'solve': solve})

    def test_analyse_solve_worker_not_advanced_not_full(self) -> None:
        """Test worker returns empty results without solve when not full."""
        solve = Mock()
        solve.advanced = False

        result = analyse_solve_worker(solve, 'method', full=False)

        self.assertEqual(result, {'steps': {}, 'score': 0.0, 'solve': None})

    def test_analyse_solve_worker_advanced_full(self) -> None:
        """Test that worker processes advanced solve with full analysis."""
        solve = Mock()
        solve.advanced = True
        solve.method_analyser.aggregate = {'step1': 0, 'step2': 1}
        solve.method_applied.summary = [
            {
                'case': 'case_a',
                'total': 10,
                'execution': 8,
                'recognition': 2,
                'qtm': 20,
            },
            {
                'case': 'case_b',
                'total': 15,
                'execution': 12,
                'recognition': 3,
                'qtm': 30,
            },
        ]
        solve.method_applied.score = 85.5
        solve.score = 85.5

        with patch('term_timer.aggregator.Solve.compute_tps') as mock_tps:
            mock_tps.side_effect = [1.9, 2.5, 2.0, 2.5]

            result = analyse_solve_worker(solve, 'method', full=True)

        expected_steps: dict[str, StepAnalysis] = {
            'step1': {
                'case': 'case_a',
                'time': 10,
                'execution': 8,
                'recognition': 2,
                'qtm': 20,
                'tps': 1.9,
                'etps': 2.5,
            },
            'step2': {
                'case': 'case_b',
                'time': 15,
                'execution': 12,
                'recognition': 3,
                'qtm': 30,
                'tps': 2.0,
                'etps': 2.5,
            },
        }

        self.assertEqual(result['steps'], expected_steps)
        self.assertEqual(result['score'], 85.5)
        self.assertEqual(result['solve'], solve)
        self.assertEqual(solve.method_name, 'method')

    def test_analyse_solve_worker_advanced_not_full(self) -> None:
        """Test that worker processes advanced solve without full data."""
        solve = Mock()
        solve.advanced = True
        solve.method_analyser.aggregate = {'step1': 0}
        solve.method_applied.summary = [{
            'case': 'case_a',
            'total': 10.5,
            'execution': 8.0,
            'recognition': 2.5,
            'qtm': 20,
        }]
        solve.method_applied.score = 85.5

        with patch('term_timer.aggregator.Solve.compute_tps', return_value=2.0):
            result = analyse_solve_worker(solve, 'method', full=False)

        self.assertIn('steps', result)
        self.assertEqual(result['score'], 85.5)
        self.assertIsNone(result['solve'])


class TestSolvesMethodAggregator(unittest.TestCase):
    """Tests for SolvesMethodAggregator class."""

    def setUp(self) -> None:
        """Set up test fixtures for aggregator tests."""
        self.mock_solve_advanced = Mock()
        self.mock_solve_advanced.advanced = True

        self.mock_solve_basic = Mock()
        self.mock_solve_basic.advanced = False

        self.stack: list[Mock] = [
            self.mock_solve_advanced,
            self.mock_solve_basic,
        ]

    @patch('term_timer.aggregator.get_method_analyser')
    @patch('term_timer.aggregator.SolvesMethodAggregator.aggregate')
    def test_init(self, mock_aggregate: Mock, mock_get_analyser: Mock) -> None:
        """Test that aggregator initializes correctly with method and stack."""
        mock_analyser = Mock()
        mock_get_analyser.return_value = mock_analyser
        mock_aggregate.return_value = {'test': 'result'}

        aggregator = SolvesMethodAggregator(
            'CFOP', cast('list[Solve]', self.stack), full=False,
        )

        self.assertEqual(aggregator.stack, self.stack)
        self.assertFalse(aggregator.full)
        self.assertEqual(aggregator.method_name, 'CFOP')
        self.assertEqual(aggregator.analyser, mock_analyser)
        self.assertEqual(aggregator.results, {'test': 'result'})
        mock_get_analyser.assert_called_once_with('CFOP')
        mock_aggregate.assert_called_once()

    @patch('term_timer.aggregator.get_method_analyser')
    @patch('term_timer.aggregator.Pool')
    @patch('term_timer.aggregator.cpu_count', return_value=4)
    def test_collect_analyses(self, _mock_cpu_count: Mock,
                              mock_pool_class: Mock,
                              _mock_get_analyser: Mock) -> None:
        """Test that collect_analyses processes solves using multiprocessing."""
        mock_pool = MagicMock()
        mock_pool_class.return_value.__enter__.return_value = mock_pool
        mock_pool.map.return_value = [{'result': 1}, {'result': 2}]

        aggregator = SolvesMethodAggregator.__new__(SolvesMethodAggregator)
        aggregator.stack = cast('list[Solve]', self.stack)
        aggregator.method_name = 'CFOP'
        aggregator.full = True

        result = aggregator.collect_analyses()

        self.assertEqual(result, [{'result': 1}, {'result': 2}])
        mock_pool_class.assert_called_once_with(processes=3)
        mock_pool.map.assert_called_once()

    @patch('term_timer.aggregator.StatisticsTools.ao')
    def test_aggregate_with_advanced_solves(self, mock_ao: Mock) -> None:
        """Test that aggregate computes statistics for advanced solves."""
        mock_ao.side_effect = lambda n, times: \
            sum(times[:n]) / min(n, len(times)) if times else 0

        analyses = [
            {
                'solve': self.mock_solve_advanced,
                'score': 80,
                'steps': {
                    'step1': {
                        'case': 'case_a',
                        'time': 10.0,
                        'execution': 8.0,
                        'recognition': 2.0,
                        'qtm': 20,
                        'tps': 2.0,
                        'etps': 2.5,
                    },
                },
            },
            {
                'solve': self.mock_solve_basic,
                'score': 0.0,
                'steps': {},
            },
        ]

        aggregator = SolvesMethodAggregator.__new__(SolvesMethodAggregator)
        aggregator.stack = cast('list[Solve]', self.stack)

        with patch.object(aggregator, 'collect_analyses',
                          return_value=analyses):
            result = aggregator.aggregate()

        self.assertEqual(result['total'], 1)
        self.assertEqual(result['mean'], 80.0)
        self.assertIn('step1', result['resume'])
        self.assertIn('case_a', result['resume']['step1'])

        case_data = result['resume']['step1']['case_a']
        self.assertEqual(case_data['count'], 1)
        self.assertEqual(case_data['frequency'], 1.0)
        self.assertEqual(case_data['time'], 10.0)
        self.assertEqual(case_data['execution'], 8.0)
        self.assertEqual(case_data['recognition'], 2.0)
        self.assertEqual(case_data['qtm'], 20)
        self.assertEqual(case_data['tps'], 2.0)
        self.assertEqual(case_data['etps'], 2.5)

    @patch('term_timer.aggregator.get_method_analyser')
    def test_aggregate_empty_stack(self, mock_get_analyser: Mock) -> None:
        """Test that aggregate handles empty solve stack correctly."""
        mock_analyser = Mock()
        mock_get_analyser.return_value = mock_analyser

        aggregator = SolvesMethodAggregator.__new__(SolvesMethodAggregator)
        aggregator.stack = []
        aggregator.analyser = mock_analyser

        with patch.object(aggregator, 'collect_analyses', return_value=[]):
            result = aggregator.aggregate()

        self.assertEqual(result['total'], 0)
        self.assertEqual(result['mean'], 0)
        self.assertEqual(result['resume'], {})
        self.assertEqual(result['stack'], [])

    @patch('term_timer.aggregator.get_method_analyser')
    @patch('term_timer.aggregator.StatisticsTools.ao')
    def test_aggregate_multiple_cases_same_step(
            self, mock_ao: Mock,
            mock_get_analyser: Mock) -> None:
        """Test aggregate averages multiple occurrences of same case."""
        mock_analyser = Mock()
        mock_analyser.infos = {}
        mock_get_analyser.return_value = mock_analyser

        mock_ao.return_value = 12.5

        analyses = [
            {
                'solve': Mock(),
                'score': 80,
                'steps': {
                    'step1': {
                        'case': 'case_a',
                        'time': 10.0,
                        'execution': 8.0,
                        'recognition': 2.0,
                        'qtm': 20,
                        'tps': 2.0,
                        'etps': 2.5,
                    },
                },
            },
            {
                'solve': Mock(),
                'score': 90,
                'steps': {
                    'step1': {
                        'case': 'case_a',
                        'time': 12.0,
                        'execution': 9.0,
                        'recognition': 3.0,
                        'qtm': 24,
                        'tps': 2.2,
                        'etps': 2.7,
                    },
                },
            },
        ]

        aggregator = SolvesMethodAggregator.__new__(SolvesMethodAggregator)
        aggregator.stack = []
        aggregator.analyser = mock_analyser

        with patch.object(aggregator, 'collect_analyses',
                          return_value=analyses):
            result = aggregator.aggregate()

        case_data = result['resume']['step1']['case_a']
        self.assertEqual(case_data['count'], 2)
        self.assertEqual(case_data['frequency'], 1.0)
        self.assertEqual(case_data['time'], 11.0)  # (10+12)/2
        self.assertEqual(case_data['execution'], 8.5)  # (8+9)/2
        self.assertEqual(case_data['recognition'], 2.5)  # (2+3)/2
        self.assertEqual(case_data['qtm'], 22)  # (20+24)/2
        self.assertEqual(case_data['tps'], 2.1)  # (2.0+2.2)/2
        self.assertEqual(case_data['etps'], 2.6)  # (2.5+2.7)/2
        self.assertEqual(case_data['probability'], 0)  # default value
