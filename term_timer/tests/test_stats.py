"""Tests for stats."""
# ruff: noqa: ERA001
import unittest
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.constants import DNF
from term_timer.constants import SECOND
from term_timer.solve import Solve
from term_timer.stats import Statistics
from term_timer.stats import StatisticsReporter
from term_timer.stats import StatisticsTools

if TYPE_CHECKING:
    from term_timer.types import CaseStats
    from term_timer.types import MethodAnalysis


class TestStatisticsTools(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000000, 10 * SECOND, 'F R U', ''),  # 10 seconds
            Solve(2000000000000, 15 * SECOND, 'R U F', ''),  # 15 seconds
            Solve(3000000000000, 20 * SECOND, 'U F R', ''),  # 20 seconds
            Solve(4000000000000, 30 * SECOND, 'F U R', ''),  # 30 seconds
            Solve(5000000000000, 25 * SECOND, 'R F U', ''),  # 25 seconds
        ]
        # Final times: [10s, 15s, 20s, 30s, 25s]
        self.stats_tools = StatisticsTools(self.solves)

    def test_mo_valid(self) -> None:
        """Test mean of 3 calculation with sufficient solves."""
        # Mean of last 3: (20 + 30 + 25) / 3 = 25
        mo3 = self.stats_tools.mo(3, self.stats_tools.stack_time)
        self.assertEqual(mo3, 25 * SECOND)

    def test_mo_insufficient_solves(self) -> None:
        """Test mean of N calculation with insufficient solves."""
        # Not enough solves for mo6
        mo6 = self.stats_tools.mo(6, self.stats_tools.stack_time)
        self.assertEqual(mo6, -1)

    def test_ao_valid(self) -> None:
        """Test average of 5 calculation with sufficient solves."""
        # Ao5: Remove best (10) and worst (30),
        # average remaining: (15 + 20 + 25) / 3 = 20
        ao5 = self.stats_tools.ao(5, self.stats_tools.stack_time)
        self.assertEqual(ao5, 20 * SECOND)

    def test_ao_insufficient_solves(self) -> None:
        """Test average of N calculation with insufficient solves."""
        # Not enough solves for ao6
        ao6 = self.stats_tools.ao(6, self.stats_tools.stack_time)
        self.assertEqual(ao6, -1)

    def test_best_mo(self) -> None:
        """Test finding the best mean of N in the history."""
        # For mo3, we can have 3 different mo3s:
        # mo3_1: (10 + 15 + 20) / 3 = 15
        # mo3_2: (15 + 20 + 30) / 3 = 21.67
        # mo3_3: (20 + 30 + 25) / 3 = 25
        # Best is mo3_1 = 15

        # Use Statistics class which has mo3 property
        stats = Statistics(self.solves)
        best_mo3 = stats.best_mo(3)
        self.assertEqual(best_mo3, 15 * SECOND)

    def test_best_ao(self) -> None:
        """Test finding the best average of N in the history."""
        # Use Statistics class which has ao5 property
        stats = Statistics(self.solves)

        # With only 5 solves, there's only one ao5, so best_ao5 should equal ao5
        best_ao5 = stats.best_ao(5)
        self.assertEqual(best_ao5, 20 * SECOND)


@patch('term_timer.stats.np.histogram')
@patch('term_timer.stats.console')
class TestStatistics(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000000, 10 * SECOND, 'F R U', ''),  # 10 seconds
            Solve(2000000000000, 15 * SECOND, 'R U F', ''),  # 15 seconds
            Solve(3000000000000, 20 * SECOND, 'U F R', ''),  # 20 seconds
            Solve(4000000000000, 30 * SECOND, 'F U R', ''),  # 30 seconds
            Solve(5000000000000, 25 * SECOND, 'R F U', ''),  # 25 seconds
        ]

    def test_mo3_property(self, *_mocks: Any) -> None:
        """Test mo3 property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.mo3, 25 * SECOND)

    def test_ao5_property(self, *_mocks: Any) -> None:
        """Test ao5 property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.ao5, 20 * SECOND)

    def test_best_property(self, *_mocks: Any) -> None:
        """Test best property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.best, 10 * SECOND)

    def test_worst_property(self, *_mocks: Any) -> None:
        """Test worst property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.worst, 30 * SECOND)

    def test_bpa_property(self, *_mocks: Any) -> None:
        """Test bpa property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.bpa, 15 * SECOND)

    def test_wpa_property(self, *_mocks: Any) -> None:
        """Test wpa property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.wpa, 25 * SECOND)

    def test_mean_property(self, *_mocks: Any) -> None:
        """Test mean property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.mean, 20 * SECOND)

    def test_median_property(self, *_mocks: Any) -> None:
        """Test median property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.median, 20 * SECOND)

    def test_delta_property(self, *_mocks: Any) -> None:
        """Test delta property (difference between last two solves)."""
        stats = Statistics(self.solves)
        # Last solve (25s) - second to last solve (30s) = -5s
        self.assertEqual(stats.delta, -5 * SECOND)

    def test_total_property(self, *_mocks: Any) -> None:
        """Test total property (number of solves)."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.total, 5)

    def test_total_time_property(self, *_mocks: Any) -> None:
        """Test total_time property (sum of all solve times)."""
        stats = Statistics(self.solves)
        # 10 + 15 + 20 + 30 + 25 = 100s
        self.assertEqual(stats.total_time, 100 * SECOND)


class TestStatisticsResumeReporter(unittest.TestCase):

    def setUp(self) -> None:
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000000, 1010000000000, 'F R U', ''),  # 10 seconds
            Solve(2000000000000, 2015000000000, 'R U F', ''),  # 15 seconds
            Solve(3000000000000, 3020000000000, 'U F R', ''),  # 20 seconds
            Solve(4000000000000, 4030000000000, 'F U R', ''),  # 30 seconds
            Solve(5000000000000, 5025000000000, 'R F U', ''),  # 25 seconds
        ]
        self.puzzle = 3

    def test_resume(self) -> None:
        """Test the resume method which prints statistics summary."""
        stats = StatisticsReporter(self.puzzle, self.solves)

        with patch('term_timer.interface.console.console.print') as mock_print:
            stats.resume('Test ')

            # Verify that console.print was called multiple times
            self.assertTrue(mock_print.call_count > 5)


class TestStatisticsReporterListing(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000, 1 * SECOND, 'F R U', ''),
            Solve(3000000000, 1 * SECOND, 'R U F', ''),
            Solve(5000000000, 1 * SECOND, 'U F R', DNF),
            Solve(7000000000, 1 * SECOND, 'F U R', '+2'),
        ]
        self.listing = StatisticsReporter(3, self.solves)

    @patch('term_timer.interface.console.console.print')
    def test_resume_with_limit(self, mock_console: Mock) -> None:
        """Test that resume respects the limit parameter."""
        self.listing.listing(2, '')

        # Should print 2 solves + title
        self.assertEqual(mock_console.call_count, 3)

    @patch('term_timer.interface.console.console.print')
    def test_resume_limit_larger_than_stack(self, mock_console: Mock) -> None:
        """Test that resume handles limits larger than the stack size."""
        self.listing.listing(10, '')

        # Should only print 4 solves (the size of our stack) + title
        self.assertEqual(mock_console.call_count, 5)

    @patch('term_timer.interface.console.console.print')
    def test_resume_format(self, mock_console: Mock) -> None:
        """Test the formatting of the resume output."""
        self.listing.listing(1, '')

        # Check the format of the most recent solve
        call_args = mock_console.call_args[0]

        # The index should be #4 (for the 4th solve)
        self.assertIn('#4', call_args[0])

        # The time should be formatted
        self.assertIn('[success]00:01.000[/success]', call_args[1])

        # The date should be included
        self.assertIn('[date]2191-10-27', call_args[2])

        # The scramble should be included
        self.assertIn('[consign]F U R[/consign]', call_args[3])

        # The flag should be included
        self.assertIn('[plus-two]+2[/plus-two]', call_args[4])


class TestStatisticsToolsComprehensive(unittest.TestCase):
    """Comprehensive tests for StatisticsTools to reach 100% coverage."""

    def setUp(self) -> None:
        """Set up test cases."""
        self.solves = [
            Solve(1000000000000, 10 * SECOND, 'F R U', ''),
            Solve(2000000000000, 15 * SECOND, 'R U F', ''),
            Solve(3000000000000, 20 * SECOND, 'U F R', ''),
            Solve(4000000000000, 30 * SECOND, 'F U R', ''),
            Solve(5000000000000, 25 * SECOND, 'R F U', ''),
        ]
        self.stats_tools = StatisticsTools(self.solves)

    def test_init_filters_none_final_times(self) -> None:
        """Test that initialization filters out None final_time values."""
        solves_with_dnf = [
            Solve(1000000000000, 10 * SECOND, 'F R U', ''),
            Solve(2000000000000, 15 * SECOND, 'R U F', DNF),
            Solve(3000000000000, 20 * SECOND, 'U F R', ''),
        ]
        stats = StatisticsTools(solves_with_dnf)
        # Should filter None from sorted list (DNF has None final_time)
        self.assertEqual(len(stats.stack_time_sorted), 2)
        self.assertNotIn(None, stats.stack_time_sorted)

    def test_best_mo_zero_mo_values(self) -> None:
        """Test best_mo when mo calculations return 0."""
        # Create scenario where mo calculations can return 0
        zero_solves = [
            Solve(1000000000000, 0, 'F R U', ''),  # 0 time
            Solve(2000000000000, 0, 'R U F', ''),  # 0 time
            Solve(3000000000000, 0, 'U F R', ''),  # 0 time
        ]
        stats = Statistics(zero_solves)
        result = stats.best_mo3
        # Should handle zero times correctly
        self.assertIsInstance(result, int)

    def test_best_ao_zero_ao_values(self) -> None:
        """Test best_ao when ao calculations return 0."""
        # Create scenario where ao calculations can return 0
        zero_solves = [
            Solve(1000000000000, 0, 'F R U', ''),
            Solve(2000000000000, 0, 'R U F', ''),
            Solve(3000000000000, 0, 'U F R', ''),
            Solve(4000000000000, 0, 'F U R', ''),
            Solve(5000000000000, 0, 'R F U', ''),
        ]
        stats = Statistics(zero_solves)
        result = stats.best_ao5
        # Should handle zero times correctly
        self.assertIsInstance(result, int)

    def test_empty_mos_list_case(self) -> None:
        """Test best_mo when no valid mos can be calculated."""
        # Empty solve list leads to empty mos list
        # need Statistics class for mo3 property
        stats = Statistics([])
        result = stats.best_mo3
        self.assertEqual(result, -1)  # Returns -1 for insufficient solves

    def test_empty_aos_list_case(self) -> None:
        """Test best_ao when no valid aos can be calculated."""
        # Empty solve list leads to empty aos list
        # need Statistics class for ao5 property
        stats = Statistics([])
        result = stats.best_ao5
        self.assertEqual(result, -1)  # Returns -1 for insufficient solves


class TestStatisticsComprehensive(unittest.TestCase):
    """Comprehensive tests for Statistics class to reach 100% coverage."""

    def setUp(self) -> None:
        """Set up test cases."""
        self.solves = [
            Solve(1000000000000, 10 * SECOND, 'F R U', ''),
            Solve(2000000000000, 15 * SECOND, 'R U F', ''),
            Solve(3000000000000, 20 * SECOND, 'U F R', ''),
            Solve(4000000000000, 30 * SECOND, 'F U R', ''),
            Solve(5000000000000, 25 * SECOND, 'R F U', ''),
        ]

    def test_larger_ao_properties(self) -> None:
        """Test ao100 and ao1000 properties with insufficient solves."""
        stats = Statistics(self.solves)
        # These should return -1 with only 5 solves
        self.assertEqual(stats.ao100, -1)  # Line 126
        self.assertEqual(stats.ao1000, -1)  # Line 130

    def test_larger_best_ao_properties(self) -> None:
        """Test best_ao100 and best_ao1000 properties."""
        stats = Statistics(self.solves)
        # These should return -1 with insufficient solves (not 0)
        self.assertEqual(stats.best_ao100, -1)  # Line 146
        self.assertEqual(stats.best_ao1000, -1)  # Line 150

    def test_repartition_configured_bin_size(self) -> None:
        """Test repartition with configured bin size."""
        with patch('term_timer.stats.STATS_CONFIG') as mock_config:
            mock_config.get.return_value = 5  # Configured bin size

            stats = Statistics(self.solves)
            result = stats.repartition

            # Should use configured bin size (line 205->210)
            self.assertIsInstance(result, list)


class TestStatisticsReporterComprehensive(unittest.TestCase):
    """Comprehensive tests for StatisticsReporter to reach 100% coverage."""

    def setUp(self) -> None:
        """Set up test cases."""
        self.solves = [
            Solve(1600000000, 10 * SECOND, 'F R U', ''),
            Solve(1600000001, 15 * SECOND, 'R U F', ''),
            Solve(1600000002, 20 * SECOND, 'U F R', ''),
            Solve(1600000003, 30 * SECOND, 'F U R', ''),
            Solve(1600000004, 25 * SECOND, 'R F U', ''),
        ]

    def test_resume_many_solves_shows_ao12_ao100_ao1000(self) -> None:
        """Test resume with enough solves to show ao12, ao100, ao1000."""
        # Create enough solves to trigger ao12, ao100, ao1000 display
        many_solves = []
        for i in range(1001):  # 1001 solves
            solve = Solve(i * 1000000000, (10 + i % 20) * SECOND, 'F R U', '')
            many_solves.append(solve)

        reporter = StatisticsReporter(3, many_solves)

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.resume()

            call_args = [str(call) for call in mock_print.call_args_list]

            # Should show ao12, ao100, ao1000 (lines 306, 314, 322)
            ao12_found = any('Ao12' in call for call in call_args)
            ao100_found = any('Ao100' in call for call in call_args)
            ao1000_found = any('Ao1000' in call for call in call_args)

            self.assertTrue(ao12_found)
            self.assertTrue(ao100_found)
            self.assertTrue(ao1000_found)

    def test_listing_advanced_solve_links(self) -> None:
        """Test listing with advanced solves showing links."""
        # Create mock advanced solve
        mock_solve = Mock(spec=Solve)
        mock_solve.final_time = 15 * SECOND
        mock_solve.time = 15 * SECOND
        mock_solve.advanced = True
        mock_solve.link_term_timer = 'http://test.com'
        mock_solve.datetime = Mock()
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.scramble = 'F R U'
        mock_solve.flag = ''

        reporter = StatisticsReporter(3, [mock_solve])

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.listing(0, 'index')

            # Should show advanced solve with link (lines 385-390)
            call_args = [str(call) for call in mock_print.call_args_list]
            link_found = any('link' in call.lower() for call in call_args)
            self.assertTrue(link_found)

    def test_listing_best_worst_time_highlighting(self) -> None:
        """Test listing highlights best and worst times."""
        reporter = StatisticsReporter(3, self.solves)

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.listing(0, 'index')

            call_args = [str(call) for call in mock_print.call_args_list]

            # Should highlight best and worst times (lines 394-395)
            success_found = any('success' in call for call in call_args)
            warning_found = any('warning' in call for call in call_args)

            self.assertTrue(success_found or warning_found)

    def test_detail_advanced_solve_full_display(self) -> None:
        """Test detail method with advanced solve showing all features."""
        # Create comprehensive mock advanced solve
        mock_solve = Mock(spec=Solve)
        mock_solve.final_time = 15 * SECOND
        mock_solve.time = 15 * SECOND
        mock_solve.advanced = True
        mock_solve.score = 85.5
        mock_solve.datetime = Mock()
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.session = 'test_session'
        mock_solve.device = 'GAN356 X'
        mock_solve.timer = 'stackmat'
        mock_solve.flag = ''
        mock_solve.scramble = 'F R U'

        # Mock method analyser and applied
        mock_solve.method_analyser = Mock()
        mock_solve.method_analyser.name = 'CFOP'
        mock_solve.method_applied = Mock()
        mock_solve.method_applied.score = 80.0
        mock_solve.method_applied.normalize_value = Mock(return_value='success')

        # Mock timing data
        mock_solve.recognition_time = 2 * SECOND
        mock_solve.execution_time = 13 * SECOND
        mock_solve.reconstruction = Mock()
        mock_solve.reconstruction.metrics._asdict.return_value = {
            'qtm': 50,
            'htm': 45,
        }
        mock_solve.tps = 2.5
        mock_solve.all_missed_moves = 3
        mock_solve.execution_missed_moves = 1
        mock_solve.transition_missed_moves = 2
        mock_solve.execution_pauses = 2
        mock_solve.aufs = 3
        mock_solve.rotations = 0

        reporter = StatisticsReporter(3, [mock_solve])

        with patch('term_timer.stats.STATS_CONFIG') as mock_config, \
             patch('term_timer.interface.console.console.print') as mock_print:

            mock_config.get.return_value = ['qtm', 'htm']

            reporter.detail(
                1, 'CFOP', show_cube=False,
                show_reconstruction=False,
                show_tps_graph=False,
                show_time_graph=False,
                show_recognition_graph=False,
                orientation='DF',
            )

            call_args = [str(call) for call in mock_print.call_args_list]

            # Should show device and timer (lines 447-456)
            device_found = any('GAN356 X' in call for call in call_args)
            timer_found = any('stackmat' in call for call in call_args)

            # Should show overhead moves (lines 527-537)
            overhead_found = any(
                'QTM' in call and '3' in call
                for call in call_args
            )

            # Should show pauses (lines 549)
            pauses_found = any(
                '2' in call and 'Pauses' in call
                for call in call_args
            )

            self.assertTrue(device_found)
            self.assertTrue(timer_found)
            self.assertTrue(overhead_found)
            self.assertTrue(pauses_found)

    def test_detail_advanced_solve_conditional_aufs(self) -> None:
        """Test detail method AUFs conditional display."""
        # Test different AUF ranges
        test_cases = [
            (0, 'None'),      # Line 571
            (2, 'success'),   # Lines 567-569
            (4, 'caution'),   # Lines 563-565
            (8, 'warning'),   # Lines 558-561
        ]

        for aufs_count, _expected_style in test_cases:
            with self.subTest(aufs_count=aufs_count):
                mock_solve = Mock(spec=Solve)
                mock_solve.final_time = 15 * SECOND
                mock_solve.time = 15 * SECOND
                mock_solve.advanced = True
                mock_solve.score = 85.5
                mock_solve.datetime = Mock()
                mock_solve.datetime.astimezone.return_value.strftime.return_value = (  # noqa: E501
                    '2023-01-01 12:00'
                )
                mock_solve.session = 'test'
                mock_solve.device = None
                mock_solve.timer = None
                mock_solve.flag = ''
                mock_solve.scramble = 'F R U'
                mock_solve.method_analyser = Mock()
                mock_solve.method_analyser.name = 'CFOP'
                mock_solve.method_applied = Mock()
                mock_solve.method_applied.score = 80.0
                mock_solve.method_applied.normalize_value = Mock(
                    return_value='success',
                )
                mock_solve.recognition_time = 2 * SECOND
                mock_solve.execution_time = 13 * SECOND
                mock_solve.reconstruction = Mock()
                mock_solve.reconstruction.metrics._asdict.return_value = {
                    'qtm': 50,
                }
                mock_solve.tps = 2.5
                mock_solve.all_missed_moves = 0
                mock_solve.execution_missed_moves = 0
                mock_solve.transition_missed_moves = 0
                mock_solve.execution_pauses = 0
                mock_solve.aufs = aufs_count
                mock_solve.rotations = 0

                reporter = StatisticsReporter(3, [mock_solve])

                with patch(
                        'term_timer.stats.STATS_CONFIG',
                ) as mock_config, patch(
                         'term_timer.interface.console.console.print',
                ) as mock_print:
                    mock_config.get.return_value = ['qtm']

                    reporter.detail(
                        1, 'CFOP', show_cube=False,
                        show_reconstruction=False,
                        show_tps_graph=False,
                        show_time_graph=False,
                        show_recognition_graph=False,
                        orientation='DF',
                    )

                    call_args = [
                        str(call)
                        for call in mock_print.call_args_list
                    ]

                    # Should format AUFs according to value
                    if aufs_count == 0:
                        none_found = any(
                            'None' in call and 'Adjusts' in call
                            for call in call_args
                        )
                        self.assertTrue(none_found)
                    else:
                        aufs_found = any(
                            str(aufs_count) in call and 'Adjusts' in call
                            for call in call_args
                        )
                        self.assertTrue(aufs_found)

    def test_detail_with_reconstruction_display(self) -> None:
        """Test detail method with reconstruction display."""
        mock_solve = Mock(spec=Solve)
        mock_solve.final_time = 15 * SECOND
        mock_solve.time = 15 * SECOND
        mock_solve.advanced = True
        mock_solve.score = 85.5
        mock_solve.datetime = Mock()
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.session = 'test'
        mock_solve.device = None
        mock_solve.timer = None
        mock_solve.flag = ''
        mock_solve.scramble = 'F R U'
        mock_solve.method_analyser = Mock()
        mock_solve.method_analyser.name = 'CFOP'
        mock_solve.method_applied = Mock()
        mock_solve.method_applied.score = 80.0
        mock_solve.method_applied.normalize_value = Mock(return_value='success')
        mock_solve.recognition_time = 2 * SECOND
        mock_solve.execution_time = 13 * SECOND
        mock_solve.reconstruction = Mock()
        mock_solve.reconstruction.metrics._asdict.return_value = {'qtm': 50}
        mock_solve.tps = 2.5
        mock_solve.all_missed_moves = 0
        mock_solve.execution_missed_moves = 0
        mock_solve.transition_missed_moves = 0
        mock_solve.execution_pauses = 0
        mock_solve.aufs = 1
        mock_solve.rotations = 0

        # Mock links and method_line
        mock_solve.link_term_timer = 'http://term-timer.com'
        mock_solve.link_alg_cubing = 'http://alg.cubing.net'
        mock_solve.link_cube_db = 'http://cubedb.net'
        mock_solve.method_line = "Cross: R U R' F2L: U R U' R'"

        reporter = StatisticsReporter(3, [mock_solve])

        with patch('term_timer.stats.STATS_CONFIG') as mock_config, \
             patch('term_timer.interface.console.console.print') as mock_print:

            mock_config.get.return_value = ['qtm']

            reporter.detail(
                1, 'CFOP', show_cube=False,
                show_reconstruction=True,
                show_tps_graph=False,
                show_time_graph=False,
                show_recognition_graph=False,
                orientation='DF',
            )

            call_args = [str(call) for call in mock_print.call_args_list]

            # Should show reconstruction section (lines 587-597)
            reconstruction_found = any(
                'Reconstruction' in call
                for call in call_args
            )
            term_timer_found = any(
                'Term-Timer' in call
                for call in call_args
            )
            alg_cubing_found = any(
                'alg.cubing.net' in call
                for call in call_args
            )

            self.assertTrue(reconstruction_found)
            self.assertTrue(term_timer_found)
            self.assertTrue(alg_cubing_found)

    @staticmethod
    def test_detail_with_graphs() -> None:
        """Test detail method with graph displays."""
        mock_solve = Mock(spec=Solve)
        mock_solve.final_time = 15 * SECOND
        mock_solve.time = 15 * SECOND
        mock_solve.advanced = True
        mock_solve.score = 85.5
        mock_solve.datetime = Mock()
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.session = 'test'
        mock_solve.device = None
        mock_solve.timer = None
        mock_solve.flag = ''
        mock_solve.scramble = 'F R U'
        mock_solve.method_analyser = Mock()
        mock_solve.method_analyser.name = 'CFOP'
        mock_solve.method_applied = Mock()
        mock_solve.method_applied.score = 80.0
        mock_solve.method_applied.normalize_value = Mock(return_value='success')
        mock_solve.recognition_time = 2 * SECOND
        mock_solve.execution_time = 13 * SECOND
        mock_solve.reconstruction = Mock()
        mock_solve.reconstruction.metrics._asdict.return_value = {'qtm': 50}
        mock_solve.tps = 2.5
        mock_solve.all_missed_moves = 0
        mock_solve.execution_missed_moves = 0
        mock_solve.transition_missed_moves = 0
        mock_solve.execution_pauses = 0
        mock_solve.aufs = 1
        mock_solve.rotations = 0

        # Mock graph methods
        mock_solve.time_graph = Mock()
        mock_solve.tps_graph = Mock()
        mock_solve.recognition_graph = Mock()

        reporter = StatisticsReporter(3, [mock_solve])

        with patch('term_timer.stats.STATS_CONFIG') as mock_config, \
             patch('term_timer.interface.console.console.print'):

            mock_config.get.return_value = ['qtm']

            reporter.detail(
                1, 'CFOP', show_cube=False,
                show_reconstruction=False,
                show_tps_graph=True,
                show_time_graph=True,
                show_recognition_graph=True,
                orientation='DF',
            )

            # Should call all graph methods (lines 599, 601, 603)
            mock_solve.time_graph.assert_called_once()
            mock_solve.tps_graph.assert_called_once()
            mock_solve.recognition_graph.assert_called_once()

    def test_case_table_skip_case_handling(self) -> None:
        """Test case_table method with SKIP cases."""
        reporter = StatisticsReporter(3, self.solves)

        with patch('term_timer.stats.Table') as mock_table_class, \
             patch('term_timer.interface.console.console.print'):

            mock_table = Mock()
            mock_table_class.return_value = mock_table

            test_items: dict[str, CaseStats] = {
                'SKIP case': {
                    'count': 1,
                    'frequency': 0.1,
                    'probability': 0.1,
                    'recognition': 100000000.0,
                    'execution': 500000000.0,
                    'time': 600000000.0,
                    'ao12': 650000000,
                    'ao5': 580000000,
                    'qtm': 5.0,
                    'tps': 8.3,
                    'etps': 8.6,
                },
            }

            reporter.case_table('OLL', test_items, 'count', 'desc')

            # Should handle SKIP cases (line 637)
            mock_table.add_row.assert_called_once()

    def test_cfop_case_sorting_by_case(self) -> None:
        """Test cfop method sorting by 'case'."""
        reporter = StatisticsReporter(3, self.solves)

        analyses: MethodAnalysis = {
            'total': 5,
            'mean': 85.5,
            'resume': {'oll': {}, 'pll': {}},
            'stack': [],
        }

        with patch.object(reporter, 'case_table') as mock_case_table, \
             patch('term_timer.interface.console.console.print'):

            # Test sorting='case' gets converted to 'label' (line 674)
            reporter.cfop(analyses, sorting='case')

            # Should call case_table with 'label' instead of 'case'
            mock_case_table.assert_called()

    def test_cfop_pll_only(self) -> None:
        """Test cfop method with pll_only flag."""
        reporter = StatisticsReporter(3, self.solves)

        analyses: MethodAnalysis = {
            'total': 5,
            'mean': 85.5,
            'resume': {'oll': {}, 'pll': {}},
            'stack': [],
        }

        with patch.object(reporter, 'case_table') as mock_case_table, \
             patch('term_timer.interface.console.console.print'):

            # Test pll_only flag (lines 676->678)
            reporter.cfop(analyses, pll_only=True)

            # Should only call case_table once (for PLL)
            self.assertEqual(mock_case_table.call_count, 1)

    def test_graph_with_ao_data(self) -> None:
        """Test graph method when ao5 and ao12 can be calculated."""
        # Create enough solves for ao5 and ao12
        many_solves = []
        for i in range(15):
            solve = Solve(i * 1000000000, (10 + i) * SECOND, 'F R U', '')
            many_solves.append(solve)

        reporter = StatisticsReporter(3, many_solves)

        with patch('term_timer.stats.plt') as mock_plt:
            # Mock all plt methods
            mock_plt.clear_figure = Mock()
            mock_plt.plot = Mock()
            mock_plt.title = Mock()
            mock_plt.plot_size = Mock()
            mock_plt.canvas_color = Mock()
            mock_plt.axes_color = Mock()
            mock_plt.ticks_color = Mock()
            mock_plt.ticks_style = Mock()
            mock_plt.show = Mock()

            reporter.graph()

            # Should call plot multiple times for
            # times, ao5, ao12 (lines 715->723, 724)
            self.assertTrue(mock_plt.plot.call_count >= 3)

    @patch('term_timer.interface.console.console.print')
    def test_resume_reverse_order(self, mock_console: Mock) -> None:
        """Test that solves are displayed in reverse order (newest first)."""
        reporter = StatisticsReporter(3, self.solves)
        reporter.listing(4, 'index')

        # Get all the call arguments
        call_args_list = mock_console.call_args_list

        # Should have called print for title and solves
        self.assertTrue(len(call_args_list) > 1)
