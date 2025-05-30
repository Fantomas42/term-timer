# ruff: noqa: ARG002, ERA001
import unittest
from unittest.mock import patch

from term_timer.constants import SECOND
from term_timer.solve import Solve
from term_timer.stats import Statistics
from term_timer.stats import StatisticsReporter
from term_timer.stats import StatisticsTools


class TestStatisticsTools(unittest.TestCase):
    def setUp(self):
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

    def test_mo_valid(self):
        """Test mean of 3 calculation with sufficient solves."""
        # Mean of last 3: (20 + 30 + 25) / 3 = 25
        mo3 = self.stats_tools.mo(3, self.stats_tools.stack_time)
        self.assertEqual(mo3, 25 * SECOND)

    def test_mo_insufficient_solves(self):
        """Test mean of N calculation with insufficient solves."""
        # Not enough solves for mo6
        mo6 = self.stats_tools.mo(6, self.stats_tools.stack_time)
        self.assertEqual(mo6, -1)

    def test_ao_valid(self):
        """Test average of 5 calculation with sufficient solves."""
        # Ao5: Remove best (10) and worst (30),
        # average remaining: (15 + 20 + 25) / 3 = 20
        ao5 = self.stats_tools.ao(5, self.stats_tools.stack_time)
        self.assertEqual(ao5, 20 * SECOND)

    def test_ao_insufficient_solves(self):
        """Test average of N calculation with insufficient solves."""
        # Not enough solves for ao6
        ao6 = self.stats_tools.ao(6, self.stats_tools.stack_time)
        self.assertEqual(ao6, -1)

    def test_best_mo(self):
        """Test finding the best mean of N in the history."""
        # For mo3, we can have 3 different mo3s:
        # mo3_1: (10 + 15 + 20) / 3 = 15
        # mo3_2: (15 + 20 + 30) / 3 = 21.67
        # mo3_3: (20 + 30 + 25) / 3 = 25
        # Best is mo3_1 = 15

        # Mock mo3 property to test best_mo
        self.stats_tools.mo3 = 25 * SECOND

        best_mo3 = self.stats_tools.best_mo(3)
        self.assertEqual(best_mo3, 15 * SECOND)

    def test_best_ao(self):
        """Test finding the best average of N in the history."""
        # Mock ao5 property to test best_ao
        self.stats_tools.ao5 = 20 * SECOND

        # With only 5 solves, there's only one ao5, so best_ao5 should equal ao5
        best_ao5 = self.stats_tools.best_ao(5)
        self.assertEqual(best_ao5, 20 * SECOND)


@patch('term_timer.stats.np.histogram')
@patch('term_timer.stats.console')
class TestStatistics(unittest.TestCase):
    def setUp(self):
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000000, 10 * SECOND, 'F R U', ''),  # 10 seconds
            Solve(2000000000000, 15 * SECOND, 'R U F', ''),  # 15 seconds
            Solve(3000000000000, 20 * SECOND, 'U F R', ''),  # 20 seconds
            Solve(4000000000000, 30 * SECOND, 'F U R', ''),  # 30 seconds
            Solve(5000000000000, 25 * SECOND, 'R F U', ''),  # 25 seconds
        ]

    def test_mo3_property(self, mock_console, mock_histogram):
        """Test mo3 property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.mo3, 25 * SECOND)

    def test_ao5_property(self, mock_console, mock_histogram):
        """Test ao5 property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.ao5, 20 * SECOND)

    def test_best_property(self, mock_console, mock_histogram):
        """Test best property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.best, 10 * SECOND)

    def test_worst_property(self, mock_console, mock_histogram):
        """Test worst property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.worst, 30 * SECOND)

    def test_bpa_property(self, mock_console, mock_histogram):
        """Test bpa property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.bpa, 15 * SECOND)

    def test_wpa_property(self, mock_console, mock_histogram):
        """Test wpa property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.wpa, 25 * SECOND)

    def test_mean_property(self, mock_console, mock_histogram):
        """Test mean property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.mean, 20 * SECOND)

    def test_median_property(self, mock_console, mock_histogram):
        """Test median property."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.median, 20 * SECOND)

    def test_delta_property(self, mock_console, mock_histogram):
        """Test delta property (difference between last two solves)."""
        stats = Statistics(self.solves)
        # Last solve (25s) - second to last solve (30s) = -5s
        self.assertEqual(stats.delta, -5 * SECOND)

    def test_total_property(self, mock_console, mock_histogram):
        """Test total property (number of solves)."""
        stats = Statistics(self.solves)
        self.assertEqual(stats.total, 5)

    def test_total_time_property(self, mock_console, mock_histogram):
        """Test total_time property (sum of all solve times)."""
        stats = Statistics(self.solves)
        # 10 + 15 + 20 + 30 + 25 = 100s
        self.assertEqual(stats.total_time, 100 * SECOND)


class TestStatisticsResumeReporter(unittest.TestCase):

    def setUp(self):
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000000, 1010000000000, 'F R U', ''),  # 10 seconds
            Solve(2000000000000, 2015000000000, 'R U F', ''),  # 15 seconds
            Solve(3000000000000, 3020000000000, 'U F R', ''),  # 20 seconds
            Solve(4000000000000, 4030000000000, 'F U R', ''),  # 30 seconds
            Solve(5000000000000, 5025000000000, 'R F U', ''),  # 25 seconds
        ]
        self.puzzle = 3

    def test_resume(self):
        """Test the resume method which prints statistics summary."""
        stats = StatisticsReporter(self.puzzle, self.solves)

        with patch('term_timer.interface.console.console.print') as mock_print:
            stats.resume('Test ')

            # Verify that console.print was called multiple times
            self.assertTrue(mock_print.call_count > 5)


class TestStatisticsReporterListing(unittest.TestCase):
    def setUp(self):
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000, 1 * SECOND, 'F R U', ''),
            Solve(3000000000, 1 * SECOND, 'R U F', ''),
            Solve(5000000000, 1 * SECOND, 'U F R', 'DNF'),
            Solve(7000000000, 1 * SECOND, 'F U R', '+2'),
        ]
        self.listing = StatisticsReporter(3, self.solves)

    @patch('term_timer.interface.console.console.print')
    def test_resume_with_limit(self, mock_console):
        """Test that resume respects the limit parameter."""
        self.listing.listing(2, '')

        # Should print 2 solves + title
        self.assertEqual(mock_console.call_count, 3)

    @patch('term_timer.interface.console.console.print')
    def test_resume_limit_larger_than_stack(self, mock_console):
        """Test that resume handles limits larger than the stack size."""
        self.listing.listing(10, '')

        # Should only print 4 solves (the size of our stack) + title
        self.assertEqual(mock_console.call_count, 5)

    @patch('term_timer.interface.console.console.print')
    def test_resume_format(self, mock_console):
        """Test the formatting of the resume output."""
        self.listing.listing(1, '')

        # Check the format of the most recent solve
        call_args = mock_console.call_args[0]

        # The index should be #4 (for the 4th solve)
        self.assertIn('#4', call_args[0])

        # The time should be formatted
        self.assertIn('[success]00:01.000[/success]', call_args[1])

        # The date should be included
        self.assertIn('[date]2191-10-27 14:26[/date]', call_args[2])

        # The scramble should be included
        self.assertIn('[consign]F U R[/consign]', call_args[3])

        # The flag should be included
        self.assertIn('[plus_two]+2[/plus_two]', call_args[4])

    @patch('term_timer.interface.console.console.print')
    def test_resume_reverse_order(self, mock_console):
        """Test that solves are displayed in reverse order (newest first)."""
        self.listing.listing(4, '')

        # Get all the call arguments
        call_args_list = mock_console.call_args_list

        # First call should have #4 (newest)
        self.assertIn('#4', call_args_list[1][0][0])

        # Last call should have #1 (oldest)
        self.assertIn('#1', call_args_list[4][0][0])
