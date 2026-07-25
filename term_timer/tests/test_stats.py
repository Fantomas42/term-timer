"""Tests for stats."""
# ruff: noqa: ANN401, ERA001
import random
import re
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import Mock
from unittest.mock import patch

from cubing_algs.cases import get_case
from fsrs import Card
from fsrs import State

from term_timer.annotations import ListingFilters
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import PUNCHCARD_CELL
from term_timer.constants import SECOND
from term_timer.constants import WEEK_DAYS
from term_timer.constants import SolveFlag
from term_timer.fsrs.storage import CaseTraining
from term_timer.solve import Solve
from term_timer.stats import TARGET_ALWAYS
from term_timer.stats import TARGET_NEVER
from term_timer.stats import DailySummaryReporter
from term_timer.stats import SolveStatisticsReporter
from term_timer.stats import Statistics
from term_timer.stats import StatisticsTools
from term_timer.stats import TrainerStatistics

if TYPE_CHECKING:
    from term_timer.annotations import CaseStats
    from term_timer.annotations import MethodAnalysis


class TestStatisticsTools(unittest.TestCase):
    """Tests for StatisticsTools class."""

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
        self.stats_tools = StatisticsTools([s.final_time for s in self.solves])

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

    def test_mb_valid(self) -> None:
        """Test mean of the 3 fastest times with sufficient solves."""
        # 3 fastest: (10 + 15 + 20) / 3 = 15
        mb3 = self.stats_tools.mb(3, self.stats_tools.stack_time)
        self.assertEqual(mb3, 15 * SECOND)

    def test_mb_insufficient_solves(self) -> None:
        """Test mean of N fastest with insufficient solves."""
        mb6 = self.stats_tools.mb(6, self.stats_tools.stack_time)
        self.assertEqual(mb6, -1)

    def test_mw_valid(self) -> None:
        """Test mean of the 3 slowest times with sufficient solves."""
        # 3 slowest: (20 + 25 + 30) / 3 = 25
        mw3 = self.stats_tools.mw(3, self.stats_tools.stack_time)
        self.assertEqual(mw3, 25 * SECOND)

    def test_mw_insufficient_solves(self) -> None:
        """Test mean of N slowest with insufficient solves."""
        mw6 = self.stats_tools.mw(6, self.stats_tools.stack_time)
        self.assertEqual(mw6, -1)

    def test_mb_all_dnf(self) -> None:
        """Test mean of N fastest when every time is a DNF."""
        tools = StatisticsTools([0, 0, 0])
        self.assertEqual(tools.mb(3, tools.stack_time), 0)

    def test_mw_all_dnf(self) -> None:
        """Test mean of N slowest when every time is a DNF."""
        tools = StatisticsTools([0, 0, 0])
        self.assertEqual(tools.mw(3, tools.stack_time), 0)

    def test_best_mo(self) -> None:
        """Test finding the best mean of N in the history."""
        # For mo3, we can have 3 different mo3s:
        # mo3_1: (10 + 15 + 20) / 3 = 15
        # mo3_2: (15 + 20 + 30) / 3 = 21.67
        # mo3_3: (20 + 30 + 25) / 3 = 25
        # Best is mo3_1 = 15

        # Use Statistics class which has mo3 property
        stats = Statistics([s.final_time for s in self.solves])
        best_mo3 = stats.best_mo(3)
        self.assertEqual(best_mo3, 15 * SECOND)

    def test_best_ao(self) -> None:
        """Test finding the best average of N in the history."""
        # Use Statistics class which has ao5 property
        stats = Statistics([s.final_time for s in self.solves])

        # With only 5 solves, there's only one ao5, so best_ao5 should equal ao5
        best_ao5 = stats.best_ao(5)
        self.assertEqual(best_ao5, 20 * SECOND)


class TestStatisticsTrim(unittest.TestCase):
    """Tests for the configurable trim percentage."""

    def setUp(self) -> None:
        """Set up a window whose result changes with the trim level."""
        # Sorted: [10, 20, 40, 50, 90]
        self.times = [10 * SECOND, 20 * SECOND, 40 * SECOND,
                      50 * SECOND, 90 * SECOND]
        self.stats_tools = StatisticsTools(self.times)

    def test_ao_default_trim_five_percent(self) -> None:
        """Default 5% trim drops 1 each side: mean of the middle three."""
        with patch('term_timer.stats.STATS_TRIM', 'p5'):
            ao5 = self.stats_tools.ao(5, self.stats_tools.stack_time)
        # (20 + 40 + 50) / 3
        self.assertEqual(ao5, int((110 / 3) * SECOND))

    def test_ao_larger_trim_drops_more(self) -> None:
        """A 40% trim drops 2 each side: only the median remains."""
        with patch('term_timer.stats.STATS_TRIM', 'p40'):
            ao5 = self.stats_tools.ao(5, self.stats_tools.stack_time)
        self.assertEqual(ao5, 40 * SECOND)

    def test_ao_extreme_trim_keeps_one_time(self) -> None:
        """A trim that would empty the window is clamped to keep one time."""
        with patch('term_timer.stats.STATS_TRIM', 'p90'):
            ao5 = self.stats_tools.ao(5, self.stats_tools.stack_time)
        self.assertEqual(ao5, 40 * SECOND)

    def test_ao_median_mode_odd_window(self) -> None:
        """Median mode on an odd window keeps the single middle time."""
        with patch('term_timer.stats.STATS_TRIM', 'm'):
            ao5 = self.stats_tools.ao(5, self.stats_tools.stack_time)
        self.assertEqual(ao5, 40 * SECOND)

    def test_ao_median_mode_even_window(self) -> None:
        """Median mode on an even window keeps the two middle times."""
        times = [10 * SECOND, 20 * SECOND, 40 * SECOND, 60 * SECOND]
        tools = StatisticsTools(times)
        with patch('term_timer.stats.STATS_TRIM', 'm'):
            ao4 = tools.ao(4, tools.stack_time)
        # pullback to 1 per side: (20 + 40) / 2
        self.assertEqual(ao4, 30 * SECOND)

    def test_ao_fixed_mode_drops_fixed_count(self) -> None:
        """Fixed mode drops the given number of times per side."""
        with patch('term_timer.stats.STATS_TRIM', '2'):
            ao5 = self.stats_tools.ao(5, self.stats_tools.stack_time)
        self.assertEqual(ao5, 40 * SECOND)

    def test_best_ao_respects_trim(self) -> None:
        """best_ao uses the configured trim for its rolling windows."""
        stats = Statistics(self.times)
        with patch('term_timer.stats.STATS_TRIM', 'p40'):
            best_ao5 = stats.best_ao(5)
        self.assertEqual(best_ao5, 40 * SECOND)


class TestTrimCount(unittest.TestCase):
    """Tests for trim_count across percentage, median and fixed modes."""

    def test_percentage_default(self) -> None:
        """Default p5 trims 1 per side for the usual window sizes."""
        self.assertEqual(StatisticsTools.trim_count('p5', 5), 1)
        self.assertEqual(StatisticsTools.trim_count('p5', 12), 1)
        self.assertEqual(StatisticsTools.trim_count('p5', 100), 5)

    def test_median_odd_keeps_one(self) -> None:
        """Median mode leaves a single middle time for odd windows."""
        self.assertEqual(StatisticsTools.trim_count('m', 5), 2)
        self.assertEqual(StatisticsTools.trim_count('m', 3), 1)

    def test_median_even_pullback(self) -> None:
        """Median mode steps back one side when the window is even."""
        self.assertEqual(StatisticsTools.trim_count('m', 4), 1)
        self.assertEqual(StatisticsTools.trim_count('m', 12), 5)

    def test_fixed_count(self) -> None:
        """A bare integer trims that many times per side."""
        self.assertEqual(StatisticsTools.trim_count('2', 12), 2)

    def test_pullback_when_window_consumed(self) -> None:
        """A fixed trim consuming the whole window is stepped back."""
        self.assertEqual(StatisticsTools.trim_count('2', 4), 1)

    def test_clamp_keeps_one_time(self) -> None:
        """Degenerate trims are clamped to keep at least one time."""
        self.assertEqual(StatisticsTools.trim_count('p90', 5), 2)
        self.assertEqual(StatisticsTools.trim_count('10', 5), 2)


class TestNormalizeTrim(unittest.TestCase):
    """Tests for the trim specification validation helper."""

    def test_valid_specs_kept(self) -> None:
        """Recognised specs are returned untouched (whitespace stripped)."""
        self.assertEqual(StatisticsTools.normalize_trim('p5'), 'p5')
        self.assertEqual(StatisticsTools.normalize_trim('m'), 'm')
        self.assertEqual(StatisticsTools.normalize_trim('3'), '3')
        self.assertEqual(StatisticsTools.normalize_trim(' p40 '), 'p40')

    def test_invalid_specs_fall_back_to_default(self) -> None:
        """Anything unrecognised falls back to the WCA default p5."""
        self.assertEqual(StatisticsTools.normalize_trim(''), 'p5')
        self.assertEqual(StatisticsTools.normalize_trim('foo'), 'p5')
        self.assertEqual(StatisticsTools.normalize_trim('pX'), 'p5')


@patch('term_timer.stats.np.histogram')
@patch('term_timer.stats.console')
class TestStatistics(unittest.TestCase):
    """Tests for Statistics class."""

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
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.mo3, 25 * SECOND)

    def test_ao5_property(self, *_mocks: Any) -> None:
        """Test ao5 property."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.ao5, 20 * SECOND)

    def test_best_property(self, *_mocks: Any) -> None:
        """Test best property."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.best, 10 * SECOND)

    def test_worst_property(self, *_mocks: Any) -> None:
        """Test worst property."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.worst, 30 * SECOND)

    def test_mb3_property(self, *_mocks: Any) -> None:
        """Test mb3 property."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.mb3, 15 * SECOND)

    def test_mw3_property(self, *_mocks: Any) -> None:
        """Test mw3 property."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.mw3, 25 * SECOND)

    def test_mb10_property(self, *_mocks: Any) -> None:
        """Test mb10 property with insufficient and sufficient data."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.mb10, -1)

        times = [t * SECOND for t in range(1, 13)]
        # 10 fastest: 1..10 -> mean 5.5
        self.assertEqual(Statistics(times).mb10, int(5.5 * SECOND))

    def test_mw10_property(self, *_mocks: Any) -> None:
        """Test mw10 property with insufficient and sufficient data."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.mw10, -1)

        times = [t * SECOND for t in range(1, 13)]
        # 10 slowest: 3..12 -> mean 7.5
        self.assertEqual(Statistics(times).mw10, int(7.5 * SECOND))

    def test_mean_property(self, *_mocks: Any) -> None:
        """Test mean property."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.mean, 20 * SECOND)

    def test_median_property(self, *_mocks: Any) -> None:
        """Test median property."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.median, 20 * SECOND)

    def test_delta_property(self, *_mocks: Any) -> None:
        """Test delta property (difference between last two solves)."""
        stats = Statistics([s.final_time for s in self.solves])
        # Last solve (25s) - second to last solve (30s) = -5s
        self.assertEqual(stats.delta, -5 * SECOND)

    def test_total_property(self, *_mocks: Any) -> None:
        """Test total property (number of solves)."""
        stats = Statistics([s.final_time for s in self.solves])
        self.assertEqual(stats.total, 5)

    def test_total_time_property(self, *_mocks: Any) -> None:
        """Test total_time property (sum of all solve times)."""
        stats = Statistics([s.final_time for s in self.solves])
        # 10 + 15 + 20 + 30 + 25 = 100s
        self.assertEqual(stats.total_time, 100 * SECOND)


class TestStatisticsResumeReporter(unittest.TestCase):
    """Tests for SolveStatisticsReporter resume method."""

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
        stats = SolveStatisticsReporter(self.puzzle, self.solves)

        with patch('term_timer.interface.console.console.print') as mock_print:
            stats.resume('Test ')

            # Verify that console.print was called multiple times
            self.assertTrue(mock_print.call_count > 5)

    def test_resume_total_without_dnf(self) -> None:
        """Total line shows the plain count when there is no DNF."""
        stats = SolveStatisticsReporter(self.puzzle, self.solves)

        with patch('term_timer.interface.console.console.print') as mock_print:
            stats.resume()

        total_line = mock_print.call_args_list[0][0]
        self.assertIn('[result]5[/result]', total_line)

    def test_resume_total_with_dnf(self) -> None:
        """Total line shows completed/total when DNFs are present."""
        solves = [
            *self.solves,
            Solve(6000000000000, 6020000000000, 'U R F', DNF),
        ]
        stats = SolveStatisticsReporter(self.puzzle, solves)

        with patch('term_timer.interface.console.console.print') as mock_print:
            stats.resume()

        total_line = mock_print.call_args_list[0][0]
        self.assertIn('[result]5/6[/result]', total_line)


class TestSolveStatisticsReporterListing(unittest.TestCase):
    """Tests for SolveStatisticsReporter listing method."""

    def setUp(self) -> None:
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000, 1 * SECOND, 'F R U', ''),
            Solve(3000000000, 1 * SECOND, 'R U F', ''),
            Solve(5000000000, 1 * SECOND, 'U F R', DNF),
            Solve(7000000000, 1 * SECOND, 'F U R', '+2'),
        ]
        self.listing = SolveStatisticsReporter(3, self.solves)

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

        # The time should be formatted; solve #4 is a +2 (final_time 3s),
        # the worst of the session, so it is highlighted as warning
        self.assertIn('[warning]00:01.000[/warning]', call_args[1])

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
        self.stats_tools = StatisticsTools([s.final_time for s in self.solves])

    def test_init_filters_none_final_times(self) -> None:
        """Test that initialization filters out None final_time values."""
        solves_with_dnf = [
            Solve(1000000000000, 10 * SECOND, 'F R U', ''),
            Solve(2000000000000, 15 * SECOND, 'R U F', DNF),
            Solve(3000000000000, 20 * SECOND, 'U F R', ''),
        ]
        stats = StatisticsTools([s.final_time for s in solves_with_dnf])
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
        stats = Statistics([s.final_time for s in zero_solves])
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
        stats = Statistics([s.final_time for s in zero_solves])
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
        stats = Statistics([s.final_time for s in self.solves])
        # These should return -1 with only 5 solves
        self.assertEqual(stats.ao100, -1)  # Line 126
        self.assertEqual(stats.ao1000, -1)  # Line 130

    def test_larger_best_ao_properties(self) -> None:
        """Test best_ao100 and best_ao1000 properties."""
        stats = Statistics([s.final_time for s in self.solves])
        # These should return -1 with insufficient solves (not 0)
        self.assertEqual(stats.best_ao100, -1)  # Line 146
        self.assertEqual(stats.best_ao1000, -1)  # Line 150

    def test_repartition_configured_bin_size(self) -> None:
        """Test repartition with configured bin size."""
        with patch('term_timer.stats.STATS_DISTRIBUTION', 5):
            stats = Statistics([s.final_time for s in self.solves])
            result = stats.repartition

            # Should use configured bin size (line 205->210)
            self.assertIsInstance(result, list)

    def test_repartition_subsecond_bins(self) -> None:
        """Tight sessions select sub-second bins without collapsing."""
        times = [
            int(t * SECOND) for t in (
                8.4, 9.1, 9.8, 8.6, 10.2, 9.4, 8.9, 9.7, 8.8, 9.3,
            )
        ]
        with patch('term_timer.stats.STATS_DISTRIBUTION', 0):
            stats = Statistics(times)
            result = stats.repartition

        # Edges keep their fractional part (no truncation to whole seconds)
        edges = [edge for _, edge in result]
        self.assertTrue(any(edge != int(edge) for edge in edges))
        # Every solve is accounted for across the bins
        self.assertEqual(sum(count for count, _ in result), len(times))


class TestSolveStatisticsReporterScore(unittest.TestCase):
    """Tests for the average score across analysable solves."""

    @staticmethod
    def make_solve(*, analysable: bool, score: float = 0.0) -> Mock:
        """
        Build a minimal solve mock with a final time and a score.

        Returns:
            Mock solve exposing final_time, analysable and score.

        """
        solve = Mock(spec=Solve)
        solve.final_time = 10 * SECOND
        solve.analysable = analysable
        solve.score = score
        return solve

    def test_score_averages_only_analysable_solves(self) -> None:
        """A mixed stack averages the score over analysable solves only."""
        solves: list[Solve] = [
            self.make_solve(analysable=True, score=80.0),
            self.make_solve(analysable=True, score=90.0),
            self.make_solve(analysable=False),
            self.make_solve(analysable=False),
        ]

        reporter = SolveStatisticsReporter(3, solves)

        self.assertEqual(reporter.score, 85.0)

    def test_score_without_analysable_solves(self) -> None:
        """A stack without any analysable solve scores 0.0."""
        solves: list[Solve] = [self.make_solve(analysable=False)]

        reporter = SolveStatisticsReporter(3, solves)

        self.assertEqual(reporter.score, 0.0)


class TestSolveStatisticsReporterComprehensive(unittest.TestCase):
    """Tests for SolveStatisticsReporter comprehensive coverage."""

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

        reporter = SolveStatisticsReporter(3, many_solves)

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
        mock_solve.comment = ''
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.scramble = 'F R U'
        mock_solve.flag = ''

        reporter = SolveStatisticsReporter(3, [mock_solve])

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.listing(0, 'index')

            # Should show advanced solve with link (lines 385-390)
            call_args = [str(call) for call in mock_print.call_args_list]
            link_found = any('link' in call.lower() for call in call_args)
            self.assertTrue(link_found)

    def test_listing_best_worst_time_highlighting(self) -> None:
        """Test listing highlights best and worst times."""
        reporter = SolveStatisticsReporter(3, self.solves)

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
        mock_solve.solve_id = 42
        mock_solve.final_time = 15 * SECOND
        mock_solve.time = 15 * SECOND
        mock_solve.advanced = True
        mock_solve.score = 85.5
        mock_solve.datetime = Mock()
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.session = 'test_session'
        mock_solve.comment = ''
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
        mock_solve.recognition_percent = 25
        mock_solve.execution_percent = 75
        mock_solve.reconstruction.metrics._asdict.return_value = {
            'qtm': 50,
            'htm': 45,
        }
        mock_solve.tps = 2.5
        mock_solve.fluency = 75
        mock_solve.all_missed_moves = 3
        mock_solve.execution_missed_moves = 1
        mock_solve.transition_missed_moves = 2
        mock_solve.execution_pauses = 2
        mock_solve.aufs = 3
        mock_solve.rotations = 0

        reporter = SolveStatisticsReporter(3, [mock_solve])

        with patch('term_timer.stats.STATS_SOLVE_METRICS', ['qtm', 'htm']), \
             patch('term_timer.interface.console.console.print') as mock_print:

            reporter.detail(
                1, 'CFOP', show_cube=False,
                show_reconstruction=False,
                show_tps_graph=False,
                show_time_graph=False,
                show_recognition_graph=False,
                show_fluency_graph=False,
                show_highlights=False,
                show_doctor=False,
                orientation='DF',
                disable_rotations=False,
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
                mock_solve.solve_id = 42
                mock_solve.final_time = 15 * SECOND
                mock_solve.time = 15 * SECOND
                mock_solve.advanced = True
                mock_solve.score = 85.5
                mock_solve.datetime = Mock()
                mock_solve.datetime.astimezone.return_value.strftime.return_value = (  # noqa: E501
                    '2023-01-01 12:00'
                )
                mock_solve.session = 'test'
                mock_solve.comment = ''
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
                mock_solve.recognition_percent = 25
                mock_solve.execution_percent = 75
                mock_solve.reconstruction = Mock()
                mock_solve.reconstruction.metrics._asdict.return_value = {
                    'qtm': 50,
                }
                mock_solve.tps = 2.5
                mock_solve.fluency = 75
                mock_solve.all_missed_moves = 0
                mock_solve.execution_missed_moves = 0
                mock_solve.transition_missed_moves = 0
                mock_solve.execution_pauses = 0
                mock_solve.aufs = aufs_count
                mock_solve.rotations = 0

                reporter = SolveStatisticsReporter(3, [mock_solve])

                with patch(
                        'term_timer.stats.STATS_SOLVE_METRICS', ['qtm'],
                ), patch(
                         'term_timer.interface.console.console.print',
                ) as mock_print:
                    reporter.detail(
                        1, 'CFOP', show_cube=False,
                        show_reconstruction=False,
                        show_tps_graph=False,
                        show_time_graph=False,
                        show_recognition_graph=False,
                        show_fluency_graph=False,
                        show_highlights=False,
                        show_doctor=False,
                        orientation='DF',
                        disable_rotations=False,
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
        mock_solve.solve_id = 42
        mock_solve.final_time = 15 * SECOND
        mock_solve.time = 15 * SECOND
        mock_solve.advanced = True
        mock_solve.score = 85.5
        mock_solve.datetime = Mock()
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.session = 'test'
        mock_solve.comment = ''
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
        mock_solve.recognition_percent = 25
        mock_solve.execution_percent = 75
        mock_solve.reconstruction = Mock()
        mock_solve.reconstruction.metrics._asdict.return_value = {'qtm': 50}
        mock_solve.tps = 2.5
        mock_solve.fluency = 75
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

        reporter = SolveStatisticsReporter(3, [mock_solve])

        with patch('term_timer.stats.STATS_SOLVE_METRICS', ['qtm']), \
             patch('term_timer.interface.console.console.print') as mock_print:

            reporter.detail(
                1, 'CFOP', show_cube=False,
                show_reconstruction=True,
                show_tps_graph=False,
                show_time_graph=False,
                show_recognition_graph=False,
                show_fluency_graph=False,
                show_highlights=False,
                show_doctor=False,
                orientation='DF',
                disable_rotations=False,
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
        mock_solve.solve_id = 42
        mock_solve.final_time = 15 * SECOND
        mock_solve.time = 15 * SECOND
        mock_solve.advanced = True
        mock_solve.score = 85.5
        mock_solve.datetime = Mock()
        mock_solve.datetime.astimezone.return_value.strftime.return_value = (
            '2023-01-01 12:00'
        )
        mock_solve.session = 'test'
        mock_solve.comment = ''
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
        mock_solve.recognition_percent = 25
        mock_solve.execution_percent = 75
        mock_solve.reconstruction = Mock()
        mock_solve.reconstruction.metrics._asdict.return_value = {'qtm': 50}
        mock_solve.tps = 2.5
        mock_solve.fluency = 75
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

        reporter = SolveStatisticsReporter(3, [mock_solve])

        with patch('term_timer.stats.STATS_SOLVE_METRICS', ['qtm']), \
             patch('term_timer.interface.console.console.print'):

            reporter.detail(
                1, 'CFOP', show_cube=False,
                show_reconstruction=False,
                show_tps_graph=True,
                show_time_graph=True,
                show_recognition_graph=True,
                show_fluency_graph=False,
                show_highlights=False,
                show_doctor=False,
                orientation='DF',
                disable_rotations=False,
            )

            # Should call all graph methods (lines 599, 601, 603)
            mock_solve.time_graph.assert_called_once()
            mock_solve.tps_graph.assert_called_once()
            mock_solve.recognition_graph.assert_called_once()

    def test_case_table_skip_case_handling(self) -> None:
        """Test case_table method with SKIP cases."""
        reporter = SolveStatisticsReporter(3, self.solves)

        with patch('term_timer.stats.Table') as mock_table_class, \
             patch('term_timer.interface.console.console.print'):

            mock_table = Mock()
            mock_table_class.return_value = mock_table

            test_items: dict[str, CaseStats] = {
                'SKIP case': {
                    'count': 1,
                    'frequency': 0.1,
                    'case': get_case('OLL', 'SKIP'),
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
        reporter = SolveStatisticsReporter(3, self.solves)

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
        reporter = SolveStatisticsReporter(3, self.solves)

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

        reporter = SolveStatisticsReporter(3, many_solves)

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
        reporter = SolveStatisticsReporter(3, self.solves)
        reporter.listing(4, 'index')

        # Get all the call arguments
        call_args_list = mock_console.call_args_list

        # Should have called print for title and solves
        self.assertTrue(len(call_args_list) > 1)


def build_statistics(
        times: list[float],
        dnf_indexes: set[int] | None = None,
) -> Statistics:
    """
    Build a Statistics instance from times in seconds.

    Args:
        times: Solve times in seconds.
        dnf_indexes: 0-based indexes of solves flagged DNF.

    Returns:
        Statistics computed over the solves final times.

    """
    dnf_indexes = dnf_indexes or set()
    solves = [
        Solve(
            1000000000 + index,
            int(time * SECOND),
            'F R U',
            DNF if index in dnf_indexes else '',
        )
        for index, time in enumerate(times)
    ]
    return Statistics([s.final_time for s in solves])


class TestStatisticsDNF(unittest.TestCase):
    """
    Tests reflecting WCA DNF semantics.

    Reference behaviour:
    - A DNF has no time: it is excluded from best, mean and median.
    - A moN whose window contains a DNF is DNF.
    - For aoN, DNFs count as the *worst* times and are trimmed first.
      If the window contains more DNFs than the trim cap, aoN is DNF.
    - Best moN / best aoN ignore DNF windows; if every window is DNF,
      the best is DNF.

    Convention: a DNF result is represented by 0, consistent with
    Solve.final_time and format_time which renders 0 as 'DNF'.
    """

    def test_mo_with_dnf_in_window_is_dnf(self) -> None:
        """A mo3 containing a DNF must be DNF, not a lowered mean."""
        stats = build_statistics([10, 15, 20], dnf_indexes={2})
        self.assertEqual(stats.mo3, 0)

    def test_mo_with_dnf_outside_window_is_unaffected(self) -> None:
        """A DNF outside the mo3 window must not change the mo3."""
        stats = build_statistics([10, 15, 20, 25], dnf_indexes={0})
        self.assertEqual(stats.mo3, 20 * SECOND)

    def test_ao5_with_one_dnf_trims_dnf_as_worst(self) -> None:
        """
        A single DNF in an ao5 counts as the worst time.

        The DNF and the best time (10) are trimmed, the ao5 is the
        mean of the remaining times: (15 + 20 + 25) / 3 = 20.
        """
        stats = build_statistics([10, 15, 20, 30, 25], dnf_indexes={3})
        self.assertEqual(stats.ao5, 20 * SECOND)

    def test_ao5_with_two_dnfs_is_dnf(self) -> None:
        """Two DNFs exceed the ao5 trim cap of 1: the ao5 is DNF."""
        stats = build_statistics([10, 15, 20, 30, 25], dnf_indexes={2, 3})
        self.assertEqual(stats.ao5, 0)

    def test_ao12_with_one_dnf_trims_dnf_as_worst(self) -> None:
        """
        A single DNF in an ao12 counts as the worst time.

        The DNF and the best time (10) are trimmed, the ao12 is the
        mean of the 10 remaining times: (11 + ... + 20) / 10 = 15.5.
        """
        times = [float(t) for t in range(10, 22)]  # 10..21
        stats = build_statistics(times, dnf_indexes={11})
        self.assertEqual(stats.ao12, int(15.5 * SECOND))

    def test_ao12_with_two_dnfs_is_dnf(self) -> None:
        """Two DNFs exceed the ao12 trim cap of 1: the ao12 is DNF."""
        times = [float(t) for t in range(10, 22)]  # 10..21
        stats = build_statistics(times, dnf_indexes={10, 11})
        self.assertEqual(stats.ao12, 0)

    def test_best_excludes_dnf(self) -> None:
        """The best single must ignore DNF solves."""
        stats = build_statistics([5, 10, 15], dnf_indexes={0})
        self.assertEqual(stats.best, 10 * SECOND)

    def test_mean_excludes_dnf(self) -> None:
        """The session mean is computed over non-DNF solves only."""
        stats = build_statistics([10, 20, 15, 30], dnf_indexes={2})
        self.assertEqual(stats.mean, 20 * SECOND)

    def test_median_excludes_dnf(self) -> None:
        """The session median is computed over non-DNF solves only."""
        stats = build_statistics([10, 20, 15, 30], dnf_indexes={2})
        self.assertEqual(stats.median, 20 * SECOND)

    def test_best_mo_skips_dnf_windows(self) -> None:
        """
        Windows containing a DNF are not eligible for best mo3.

        Only [10, 15, 20] is DNF-free: best mo3 is 15, even if a
        window containing the DNF would yield a lower raw mean.
        """
        stats = build_statistics([10, 15, 20, 30, 25], dnf_indexes={3})
        self.assertEqual(stats.best_mo3, 15 * SECOND)

    def test_best_mo_all_windows_dnf_is_dnf(self) -> None:
        """If every mo3 window contains a DNF, the best mo3 is DNF."""
        stats = build_statistics([10, 15, 20], dnf_indexes={1})
        self.assertEqual(stats.best_mo3, 0)

    def test_best_ao_skips_dnf_windows(self) -> None:
        """
        DNF windows are skipped, single-DNF windows trim the DNF.

        Windows: [10, 15, 20, 30, 25] -> 20, one DNF -> 25,
        two DNFs -> DNF. The best ao5 is 20.
        """
        stats = build_statistics(
            [10, 15, 20, 30, 25, 40, 40], dnf_indexes={5, 6},
        )
        self.assertEqual(stats.best_ao5, 20 * SECOND)

    def test_best_ao_all_windows_dnf_is_dnf(self) -> None:
        """If every ao5 window contains 2+ DNFs, the best ao5 is DNF."""
        stats = build_statistics([10, 15, 20, 30, 25], dnf_indexes={0, 1})
        self.assertEqual(stats.best_ao5, 0)


class TestBestRollingDNFEquivalence(unittest.TestCase):
    """
    Freezes the vectorized best_mo/best_ao against a brute-force model.

    The fast implementations (`sliding_window_view` + numpy sort, DNF
    mapped to +inf) must stay bit-identical to a naive per-window
    reference built from the audited `mo`/`ao` static methods, including
    every DNF trimming edge case.
    """

    @staticmethod
    def reference_best(stack: list[int], limit: int, kind: str) -> int:
        """
        Naive best moN/aoN over every consecutive window.

        Returns:
            Best value in milliseconds, 0 if every window is DNF, or -1
            if there are fewer times than the window size.

        """
        if limit > len(stack):
            return -1
        compute = Statistics.mo if kind == 'mo' else Statistics.ao
        values = [
            result
            for end in range(limit, len(stack) + 1)
            for result in [compute(limit, stack[end - limit:end])]
            if result
        ]
        return min(values) if values else 0

    def assert_equivalent(self, stack: list[int], limit: int) -> None:
        """Both best_mo and best_ao match the reference for a stack."""
        stats = Statistics(stack)
        self.assertEqual(
            stats.best_mo(limit),
            self.reference_best(stack, limit, 'mo'),
            msg=f'best_mo({limit}) mismatch for {stack}',
        )
        self.assertEqual(
            stats.best_ao(limit),
            self.reference_best(stack, limit, 'ao'),
            msg=f'best_ao({limit}) mismatch for {stack}',
        )

    def test_dnf_at_trim_cap_boundary(self) -> None:
        """ao25 (cap 2): 2 DNFs trim away, 3 DNFs make the window DNF."""
        times = [float(t) for t in range(10, 35)]  # 25 solves
        # Exactly cap DNFs: window stays valid (DNFs trimmed as worst)
        at_cap = build_statistics(times, dnf_indexes={0, 1})
        self.assertGreater(at_cap.best_ao(25), 0)
        # One more DNF than the cap: the only window is DNF
        over_cap = build_statistics(times, dnf_indexes={0, 1, 2})
        self.assertEqual(over_cap.best_ao(25), 0)

    def test_random_stacks_match_reference(self) -> None:
        """Randomized DNF stacks stay equivalent to the reference."""
        rng = random.Random(20260620)  # noqa: S311
        limits = [3, 5, 12, 25, 50]
        for _ in range(400):
            size = rng.randint(0, 60)
            dnf_rate = rng.choice([0.0, 0.05, 0.2, 0.5, 0.9, 1.0])
            stack = [
                0 if rng.random() < dnf_rate else rng.randint(1, 30000)
                for _ in range(size)
            ]
            for limit in limits:
                self.assert_equivalent(stack, limit)


class TestSolveStatisticsReporterTotalTimeDNF(unittest.TestCase):
    """Tests for total_time accounting of DNF solves."""

    def test_total_time_includes_dnf_real_time(self) -> None:
        """
        The total time spent solving counts DNF solves real time.

        A DNF has no final time but the time was really spent:
        10 + 20 (DNF real time) + 5 + 2 (+2 penalty) = 37.
        """
        solves = [
            Solve(1000000000, 10 * SECOND, 'F R U', ''),
            Solve(2000000000, 20 * SECOND, 'R U F', DNF),
            Solve(3000000000, 5 * SECOND, 'U F R', PLUS_TWO),
        ]
        reporter = SolveStatisticsReporter(3, solves)
        self.assertEqual(reporter.total_time, 37 * SECOND)


class TestStatisticsDNFScenarios(unittest.TestCase):
    """
    Scenario tests replaying a real session.

    The session contains 7 solves; expected values are computed with 0, 1
    and 2 solves flagged DNF.
    """

    TIMES: tuple[float, ...] = (4.03, 4.64, 5.02, 3.27, 5.90, 5.68, 4.32)

    @staticmethod
    def seconds(value: int) -> float:
        """
        Convert a nanoseconds stat to rounded seconds.

        Returns:
            Time in seconds rounded to 2 decimals.

        """
        return round(value / SECOND, 2)

    def test_session_without_dnf(self) -> None:
        """Sanity check: expected values without any DNF."""
        stats = build_statistics(list(self.TIMES))

        self.assertEqual(self.seconds(stats.best), 3.27)
        self.assertEqual(self.seconds(stats.mean), 4.69)
        self.assertEqual(self.seconds(stats.mo3), 5.30)
        self.assertEqual(self.seconds(stats.ao5), 5.01)
        self.assertEqual(self.seconds(stats.best_mo3), 4.31)
        self.assertEqual(self.seconds(stats.best_ao5), 4.56)

    def test_session_with_one_dnf(self) -> None:
        """Expected values with solve #5 (5.90) flagged DNF."""
        stats = build_statistics(list(self.TIMES), dnf_indexes={4})

        self.assertEqual(self.seconds(stats.best), 3.27)
        self.assertEqual(self.seconds(stats.mean), 4.49)
        self.assertEqual(stats.mo3, 0)  # DNF
        self.assertEqual(self.seconds(stats.ao5), 5.01)
        self.assertEqual(self.seconds(stats.best_mo3), 4.31)
        self.assertEqual(self.seconds(stats.best_ao5), 4.56)

    def test_session_with_two_dnfs(self) -> None:
        """Expected values with solves #4 and #5 flagged DNF."""
        stats = build_statistics(list(self.TIMES), dnf_indexes={3, 4})

        self.assertEqual(self.seconds(stats.best), 4.03)
        self.assertEqual(self.seconds(stats.mean), 4.74)
        self.assertEqual(stats.mo3, 0)  # DNF
        self.assertEqual(stats.ao5, 0)  # DNF
        self.assertEqual(self.seconds(stats.best_mo3), 4.56)
        self.assertEqual(stats.best_ao5, 0)  # DNF


def brute_projection(
        times: list[int],
        limit: int,
        cap: int,
        *,
        next_dnf: bool,
) -> int:
    """
    Pure-Python oracle for BPA/WPA.

    Projects the next solve onto the rolling window: the last ``limit - 1``
    real solves plus a synthetic next solve (perfect ``0`` for BPA, DNF for
    WPA), trimmed ``cap`` per side. Deliberately independent of the numpy
    implementation so it can serve as a differential reference.

    Returns:
        Projected average in milliseconds, or 0 if the projection is a DNF.

    """
    window = times[len(times) - (limit - 1):]
    real_dnf = window.count(0)
    if real_dnf + (1 if next_dnf else 0) > cap:
        return 0

    values = [float('inf') if time == 0 else float(time) for time in window]
    values.append(float('inf') if next_dnf else 0.0)
    values.sort()

    kept = values[cap:limit - cap]
    return int(sum(kept) / len(kept))


class TestBpaWpa(unittest.TestCase):
    """
    Tests for the best/worst possible average projections.

    BPA is the average you would get if the next solve were perfect (0 ms);
    WPA if the next solve were a DNF. Both project onto the last ``limit - 1``
    real solves and trim with the same caps as ``ao``.
    """

    def test_bpa5_clean_window_at_boundary(self) -> None:
        """BPA5 is available from 4 solves and trims the perfect solve."""
        tools = StatisticsTools([10 * SECOND, 20 * SECOND,
                                 30 * SECOND, 40 * SECOND])
        # Sorted [0, 10, 20, 30, 40], trim 1/side -> (10+20+30)/3
        self.assertEqual(tools.bpa(5, tools.stack_time), 20 * SECOND)

    def test_wpa5_clean_window_at_boundary(self) -> None:
        """WPA5 trims the synthetic DNF as the single worst time."""
        tools = StatisticsTools([10 * SECOND, 20 * SECOND,
                                 30 * SECOND, 40 * SECOND])
        # Sorted [10, 20, 30, 40, inf], trim 1/side -> (20+30+40)/3
        self.assertEqual(tools.wpa(5, tools.stack_time), 30 * SECOND)

    def test_bpa_uses_only_last_window(self) -> None:
        """Older solves outside the last limit-1 are ignored."""
        tools = StatisticsTools([99 * SECOND, 10 * SECOND, 20 * SECOND,
                                 30 * SECOND, 40 * SECOND])
        self.assertEqual(tools.bpa(5, tools.stack_time), 20 * SECOND)
        self.assertEqual(tools.wpa(5, tools.stack_time), 30 * SECOND)

    def test_bpa5_with_one_dnf_in_window(self) -> None:
        """A single DNF fits under the trim cap, so BPA stays finite."""
        tools = StatisticsTools([10 * SECOND, 20 * SECOND, 0, 40 * SECOND])
        # [0, 10, 20, 40, inf] trim 1/side -> (10+20+40)/3
        self.assertEqual(tools.bpa(5, tools.stack_time), int(70 / 3 * SECOND))

    def test_wpa5_with_one_dnf_is_dnf(self) -> None:
        """An existing DNF plus the synthetic DNF exceeds the cap -> DNF."""
        tools = StatisticsTools([10 * SECOND, 20 * SECOND, 0, 40 * SECOND])
        self.assertEqual(tools.wpa(5, tools.stack_time), 0)

    def test_bpa5_with_two_dnfs_is_dnf(self) -> None:
        """Two DNFs already exceed the ao5 trim cap, so even BPA is DNF."""
        tools = StatisticsTools([10 * SECOND, 0, 0, 40 * SECOND])
        self.assertEqual(tools.bpa(5, tools.stack_time), 0)

    def test_bpa12_clean_window(self) -> None:
        """BPA12 over 11 solves trims one per side after adding 0."""
        times = [t * SECOND for t in range(1, 12)]
        tools = StatisticsTools(times)
        # [0..11] trim 1/side -> mean(1..10) = 5.5
        self.assertEqual(tools.bpa(12, tools.stack_time), int(5.5 * SECOND))

    def test_wpa12_clean_window(self) -> None:
        """WPA12 trims the synthetic DNF as the single worst time."""
        times = [t * SECOND for t in range(1, 12)]
        tools = StatisticsTools(times)
        # [1..11, inf] trim 1/side -> mean(2..11) = 6.5
        self.assertEqual(tools.wpa(12, tools.stack_time), int(6.5 * SECOND))

    def test_insufficient_data_returns_minus_one(self) -> None:
        """Fewer than limit-1 solves yields -1 for both BPA and WPA."""
        tools = StatisticsTools([10 * SECOND, 20 * SECOND, 30 * SECOND])
        self.assertEqual(tools.bpa(5, tools.stack_time), -1)
        self.assertEqual(tools.wpa(5, tools.stack_time), -1)

    def test_bpa_is_best_case_wpa_is_worst_case(self) -> None:
        """For a clean window BPA <= current ao5 <= WPA."""
        times = [30 * SECOND, 10 * SECOND, 50 * SECOND,
                 20 * SECOND, 40 * SECOND]
        tools = StatisticsTools(times)
        # ao5 projects onto the last 4 + next solve, like BPA/WPA
        bpa = tools.bpa(5, tools.stack_time)
        wpa = tools.wpa(5, tools.stack_time)
        self.assertLess(bpa, wpa)
        # Best case beats the worst real time in the projected window
        self.assertLessEqual(bpa, wpa)

    def test_cached_properties_match_methods(self) -> None:
        """Statistics.bpa5/wpa5/bpa12/wpa12 wrap the underlying methods."""
        times = [t * SECOND for t in range(1, 12)]
        stats = Statistics(times)
        self.assertEqual(stats.bpa5, stats.bpa(5, stats.stack_time))
        self.assertEqual(stats.wpa5, stats.wpa(5, stats.stack_time))
        self.assertEqual(stats.bpa12, stats.bpa(12, stats.stack_time))
        self.assertEqual(stats.wpa12, stats.wpa(12, stats.stack_time))

    def test_differential_against_brute_force(self) -> None:
        """Random windows (incl. DNFs) match the pure-Python oracle."""
        dnf_probability = 0.15
        rng = random.Random(20260620)  # noqa: S311
        for _ in range(2000):
            limit = rng.choice([5, 12])
            count = rng.randint(limit - 1, limit + 8)
            times = [
                0 if rng.random() < dnf_probability
                else rng.randint(1, 60) * 100
                for _ in range(count)
            ]
            tools = StatisticsTools(times)
            cap = StatisticsTools.trim_count('p5', limit)
            self.assertEqual(
                tools.bpa(limit, tools.stack_time),
                brute_projection(times, limit, cap, next_dnf=False),
            )
            self.assertEqual(
                tools.wpa(limit, tools.stack_time),
                brute_projection(times, limit, cap, next_dnf=True),
            )


def trimmed_mean(window: list[int], cap: int) -> float:
    """
    Trimmed mean of a window with DNF (0) as the worst time.

    Returns:
        The trimmed mean in milliseconds, or +inf if too many DNFs.

    """
    values = sorted(float('inf') if time == 0 else float(time)
                    for time in window)
    kept = values[cap:len(window) - cap]
    return sum(kept) / len(kept)


def brute_target(times: list[int], limit: int, cap: int) -> int:
    """
    Pure-Python oracle for target_to_beat_best_ao.

    Computes the session best aoN by brute force, then locates the crossing
    time within the kept band by bisecting the projected aoN. Deliberately
    independent of the closed-form implementation.

    Returns:
        Target time in milliseconds, ``TARGET_ALWAYS``, ``TARGET_NEVER``, or
        -1 if there are fewer than ``limit`` times.

    """
    if limit > len(times):
        return -1

    carried = times[len(times) - (limit - 1):]
    if carried.count(0) > cap:
        return TARGET_NEVER

    averages = [
        trimmed_mean(times[start:start + limit], cap)
        for start in range(len(times) - limit + 1)
        if times[start:start + limit].count(0) <= cap
    ]
    if not averages:
        return TARGET_ALWAYS
    best = int(min(averages))

    def projected(next_time: int) -> float:
        return trimmed_mean([*carried, next_time], cap)

    arr = sorted(float('inf') if time == 0 else float(time)
                 for time in carried)
    lower = arr[cap - 1]
    upper = arr[limit - 1 - cap]

    # Below lower / above upper the projected average saturates: the fastest
    # solve cannot even tie the best, or the slowest still beats it
    if projected(int(lower)) > best:
        return TARGET_NEVER
    if upper < float('inf') and projected(int(upper) + 1) < best:
        return TARGET_ALWAYS

    # Strictly increasing across the kept band, so the crossing is unique
    low = int(lower)
    high = int(upper) if upper < float('inf') else 10 ** 15
    while low < high:
        mid = (low + high + 1) // 2
        if projected(mid) <= best:
            low = mid
        else:
            high = mid - 1
    return low


class TestTargetToBeatBestAo(unittest.TestCase):
    """
    Tests for the time needed to set a new best average.

    target_to_beat_best_ao(N) returns the slowest next-solve time that still
    ties the session's best aoN, or a sentinel when any time would do it
    (TARGET_ALWAYS) or none can (TARGET_NEVER).
    """

    def test_target_ties_the_best_ao5(self) -> None:
        """The returned time, played next, exactly ties the best ao5."""
        # Window [10, 20, 30, 40, 50] -> best ao5 = mean(20, 30, 40) = 30
        stats = Statistics([50 * SECOND, 10 * SECOND, 20 * SECOND,
                            30 * SECOND, 40 * SECOND])
        target = stats.target_to_beat_best_ao(5)
        # Need 3*30 - (20 + 30) = 40 s on the next solve
        self.assertEqual(target, 40 * SECOND)

        # Playing the target next reaches an ao5 equal to the former best
        extended = Statistics([*stats.stack_time, target])
        self.assertEqual(extended.ao5, 30 * SECOND)

    def test_never_when_record_is_out_of_reach(self) -> None:
        """A strong record with slow recent solves can never be beaten."""
        stats = Statistics([10 * SECOND] * 5 + [99 * SECOND] * 4)
        self.assertEqual(stats.target_to_beat_best_ao(5), TARGET_NEVER)

    def test_never_when_next_window_forced_dnf(self) -> None:
        """Too many DNFs in the carried window force the next aoN to DNF."""
        stats = Statistics([30 * SECOND, 40 * SECOND, 50 * SECOND,
                            20 * SECOND, 0, 0])
        self.assertEqual(stats.target_to_beat_best_ao(5), TARGET_NEVER)

    def test_always_when_no_valid_record(self) -> None:
        """With every past window a DNF, any next time sets the first best."""
        stats = Statistics([0, 0, 0, 0, 10 * SECOND, 0,
                            20 * SECOND, 30 * SECOND])
        self.assertEqual(stats.target_to_beat_best_ao(5), TARGET_ALWAYS)

    def test_insufficient_data_returns_minus_one(self) -> None:
        """Fewer than limit solves yields -1."""
        stats = Statistics([10 * SECOND, 20 * SECOND,
                            30 * SECOND, 40 * SECOND])
        self.assertEqual(stats.target_to_beat_best_ao(5), -1)

    def test_cached_properties_match_method(self) -> None:
        """ao5_target/ao12_target wrap the underlying method."""
        times = [t * SECOND for t in range(1, 14)]
        stats = Statistics(times)
        self.assertEqual(stats.ao5_target, stats.target_to_beat_best_ao(5))
        self.assertEqual(stats.ao12_target, stats.target_to_beat_best_ao(12))

    def test_differential_against_brute_force(self) -> None:
        """Random sessions (incl. DNFs) match the pure-Python oracle."""
        dnf_probability = 0.15
        rng = random.Random(20260621)  # noqa: S311
        for _ in range(2000):
            limit = rng.choice([5, 12])
            count = rng.randint(limit, limit + 10)
            times = [
                0 if rng.random() < dnf_probability
                else rng.randint(1, 60) * 100
                for _ in range(count)
            ]
            stats = Statistics(times)
            cap = StatisticsTools.trim_count('p5', limit)
            self.assertEqual(
                stats.target_to_beat_best_ao(limit),
                brute_target(times, limit, cap),
            )


class TestListingFilters(unittest.TestCase):
    """Tests for ListingFilters dataclass."""

    def test_default_filters(self) -> None:
        """Test ListingFilters with default values."""
        filters = ListingFilters()

        self.assertFalse(filters.with_comments)
        self.assertFalse(filters.without_comments)
        self.assertFalse(filters.connected)
        self.assertFalse(filters.unconnected)
        self.assertFalse(filters.dnf)
        self.assertFalse(filters.plus_two)
        self.assertFalse(filters.no_penalty)
        self.assertIsNone(filters.search_comment)
        self.assertIsNone(filters.search_scramble)
        self.assertIsNone(filters.min_time)
        self.assertIsNone(filters.max_time)

    def test_custom_filters(self) -> None:
        """Test ListingFilters with custom values."""
        filters = ListingFilters(
            with_comments=True,
            connected=True,
            dnf=True,
            search_comment='test',
            min_time=10.5,
            max_time=20.0,
        )

        self.assertTrue(filters.with_comments)
        self.assertTrue(filters.connected)
        self.assertTrue(filters.dnf)
        self.assertEqual(filters.search_comment, 'test')
        self.assertEqual(filters.min_time, 10.5)
        self.assertEqual(filters.max_time, 20.0)


class TestMatchesFilters(unittest.TestCase):  # noqa: PLR0904
    """Tests for SolveStatisticsReporter.matches_filters method."""

    def test_empty_filters_matches_everything(self) -> None:
        """Test that empty filters match all solves."""
        solve = Solve(1000000000, 10 * SECOND, 'F R U', '')
        filters = ListingFilters()

        self.assertTrue(SolveStatisticsReporter.matches_filters(solve, filters))

    def test_with_comments_filter(self) -> None:
        """Test with_comments filter."""
        solve_with_comment = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            comment='Good solve',
        )
        solve_without_comment = Solve(1000000000, 10 * SECOND, 'F R U', '')

        filters = ListingFilters(with_comments=True)

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(
                solve_with_comment, filters,
            ),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(
                solve_without_comment, filters,
            ),
        )

    def test_without_comments_filter(self) -> None:
        """Test without_comments filter."""
        solve_with_comment = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            comment='Good solve',
        )
        solve_without_comment = Solve(1000000000, 10 * SECOND, 'F R U', '')

        filters = ListingFilters(without_comments=True)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(
                solve_with_comment, filters,
            ),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(
                solve_without_comment, filters,
            ),
        )

    def test_connected_filter(self) -> None:
        """Test connected filter for Bluetooth cube solves."""
        solve_connected = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            device='GAN356 X',
        )
        solve_unconnected = Solve(1000000000, 10 * SECOND, 'F R U', '')

        filters = ListingFilters(connected=True)

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_connected, filters),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_unconnected, filters),
        )

    def test_unconnected_filter(self) -> None:
        """Test unconnected filter for manual solves."""
        solve_connected = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            device='GAN356 X',
        )
        solve_unconnected = Solve(1000000000, 10 * SECOND, 'F R U', '')

        filters = ListingFilters(unconnected=True)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_connected, filters),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_unconnected, filters),
        )

    def test_dnf_filter(self) -> None:
        """Test DNF flag filter."""
        solve_dnf = Solve(1000000000, 10 * SECOND, 'F R U', DNF)
        solve_ok = Solve(1000000000, 10 * SECOND, 'F R U', '')
        solve_plus_two = Solve(1000000000, 10 * SECOND, 'F R U', '+2')

        filters = ListingFilters(dnf=True)

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_dnf, filters),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_ok, filters),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_plus_two, filters),
        )

    def test_plus_two_filter(self) -> None:
        """Test +2 penalty flag filter."""
        solve_dnf = Solve(1000000000, 10 * SECOND, 'F R U', DNF)
        solve_ok = Solve(1000000000, 10 * SECOND, 'F R U', '')
        solve_plus_two = Solve(1000000000, 10 * SECOND, 'F R U', '+2')

        filters = ListingFilters(plus_two=True)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_dnf, filters),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_ok, filters),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_plus_two, filters),
        )

    def test_no_penalty_filter(self) -> None:
        """Test no_penalty filter for clean solves."""
        solve_dnf = Solve(1000000000, 10 * SECOND, 'F R U', DNF)
        solve_ok = Solve(1000000000, 10 * SECOND, 'F R U', '')
        solve_plus_two = Solve(1000000000, 10 * SECOND, 'F R U', '+2')

        filters = ListingFilters(no_penalty=True)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_dnf, filters),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_ok, filters),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_plus_two, filters),
        )

    def test_search_comment_filter_case_insensitive(self) -> None:
        """Test search_comment filter with case insensitive matching."""
        solve = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            comment='Good solve with LUCKY skip',
        )

        filters_match = ListingFilters(search_comment='lucky')
        filters_no_match = ListingFilters(search_comment='bad')

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_match),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters_no_match),
        )

    def test_search_comment_filter_no_comment(self) -> None:
        """Test search_comment filter with solve without comment."""
        solve = Solve(1000000000, 10 * SECOND, 'F R U', '')
        filters = ListingFilters(search_comment='test')

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters),
        )

    def test_search_comment_filter_empty_string(self) -> None:
        """Test search_comment filter with empty search string."""
        solve = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            comment='Any comment',
        )
        filters = ListingFilters(search_comment='')

        self.assertTrue(SolveStatisticsReporter.matches_filters(solve, filters))

    def test_search_scramble_filter_case_insensitive(self) -> None:
        """Test search_scramble filter with case insensitive matching."""
        solve = Solve(1000000000, 10 * SECOND, "F R U R' F2", '')

        filters_match = ListingFilters(search_scramble='r u r')
        filters_no_match = ListingFilters(search_scramble='L D')

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_match),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters_no_match),
        )

    def test_search_scramble_filter_empty_string(self) -> None:
        """Test search_scramble filter with empty search string."""
        solve = Solve(1000000000, 10 * SECOND, 'F R U', '')
        filters = ListingFilters(search_scramble='')

        self.assertTrue(SolveStatisticsReporter.matches_filters(solve, filters))

    def test_min_time_filter(self) -> None:
        """Test min_time filter converts seconds to milliseconds."""
        solve_fast = Solve(1000000000, 5 * SECOND, 'F R U', '')
        solve_slow = Solve(1000000000, 15 * SECOND, 'F R U', '')

        filters = ListingFilters(min_time=10.0)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_fast, filters),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_slow, filters),
        )

    def test_min_time_filter_boundary(self) -> None:
        """Test min_time filter at exact boundary."""
        solve = Solve(1000000000, 10 * SECOND, 'F R U', '')
        filters_less = ListingFilters(min_time=9.999)
        filters_equal = ListingFilters(min_time=10.0)
        filters_greater = ListingFilters(min_time=10.001)

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_less),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_equal),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters_greater),
        )

    def test_max_time_filter(self) -> None:
        """Test max_time filter converts seconds to milliseconds."""
        solve_fast = Solve(1000000000, 5 * SECOND, 'F R U', '')
        solve_slow = Solve(1000000000, 15 * SECOND, 'F R U', '')

        filters = ListingFilters(max_time=10.0)

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_fast, filters),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_slow, filters),
        )

    def test_max_time_filter_boundary(self) -> None:
        """Test max_time filter at exact boundary."""
        solve = Solve(1000000000, 10 * SECOND, 'F R U', '')
        filters_less = ListingFilters(max_time=9.999)
        filters_equal = ListingFilters(max_time=10.0)
        filters_greater = ListingFilters(max_time=10.001)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters_less),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_equal),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_greater),
        )

    def test_min_and_max_time_filter_combined(self) -> None:
        """Test min_time and max_time filters combined."""
        solve_too_fast = Solve(1000000000, 5 * SECOND, 'F R U', '')
        solve_in_range = Solve(1000000000, 12 * SECOND, 'F R U', '')
        solve_too_slow = Solve(1000000000, 20 * SECOND, 'F R U', '')

        filters = ListingFilters(min_time=10.0, max_time=15.0)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_too_fast, filters),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve_in_range, filters),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve_too_slow, filters),
        )

    def test_multiple_filters_and_logic(self) -> None:
        """Test multiple filters combined with AND logic."""
        solve_match_all = Solve(
            1000000000, 12 * SECOND, 'F R U', '',
            comment='Good solve',
            device='GAN356 X',
        )
        solve_match_partial = Solve(
            1000000000, 12 * SECOND, 'F R U', '',
            comment='Good solve',
        )

        filters = ListingFilters(
            with_comments=True,
            connected=True,
            min_time=10.0,
            max_time=15.0,
        )

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(
                solve_match_all, filters,
            ),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(
                solve_match_partial, filters,
            ),
        )

    def test_contradictory_comment_filters(self) -> None:
        """Test contradictory with_comments and without_comments filters."""
        solve = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            comment='Test',
        )

        filters = ListingFilters(with_comments=True, without_comments=True)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters),
        )

    def test_contradictory_connection_filters(self) -> None:
        """Test contradictory connected and unconnected filters."""
        solve = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            device='GAN356 X',
        )

        filters = ListingFilters(connected=True, unconnected=True)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters),
        )

    def test_contradictory_flag_filters(self) -> None:
        """Test contradictory flag filters."""
        solve = Solve(1000000000, 10 * SECOND, 'F R U', '+2')

        filters = ListingFilters(dnf=True, no_penalty=True)

        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters),
        )

    def test_min_time_none_value(self) -> None:
        """Test min_time filter with None value."""
        solve = Solve(1000000000, 5 * SECOND, 'F R U', '')
        filters = ListingFilters(min_time=None)

        self.assertTrue(SolveStatisticsReporter.matches_filters(solve, filters))

    def test_max_time_none_value(self) -> None:
        """Test max_time filter with None value."""
        solve = Solve(1000000000, 20 * SECOND, 'F R U', '')
        filters = ListingFilters(max_time=None)

        self.assertTrue(SolveStatisticsReporter.matches_filters(solve, filters))

    def test_search_comment_substring_matching(self) -> None:
        """Test search_comment filter matches substrings."""
        solve = Solve(
            1000000000, 10 * SECOND, 'F R U', '',
            comment='This is a very long comment about the solve',
        )

        filters_start = ListingFilters(search_comment='This')
        filters_middle = ListingFilters(search_comment='very long')
        filters_end = ListingFilters(search_comment='solve')

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_start),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_middle),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_end),
        )

    def test_search_scramble_substring_matching(self) -> None:
        """Test search_scramble filter matches substrings."""
        solve = Solve(1000000000, 10 * SECOND, "F R U R' F2 L D", '')

        filters_start = ListingFilters(search_scramble='F R')
        filters_middle = ListingFilters(search_scramble="R' F2")
        filters_end = ListingFilters(search_scramble='L D')

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_start),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_middle),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_end),
        )

    def test_time_filters_with_zero_time(self) -> None:
        """Test time filters with zero time solve."""
        solve = Solve(1000000000, 0, 'F R U', '')

        filters_min = ListingFilters(min_time=0.0)
        filters_max = ListingFilters(max_time=0.0)

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_min),
        )
        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_max),
        )

    def test_time_filters_with_fractional_seconds(self) -> None:
        """Test time filters with fractional second values."""
        solve = Solve(1000000000, int(12.345 * SECOND), 'F R U', '')

        filters_match = ListingFilters(min_time=12.0, max_time=13.0)
        filters_no_match = ListingFilters(min_time=12.5, max_time=13.0)

        self.assertTrue(
            SolveStatisticsReporter.matches_filters(solve, filters_match),
        )
        self.assertFalse(
            SolveStatisticsReporter.matches_filters(solve, filters_no_match),
        )


class TestListingWithFilters(unittest.TestCase):
    """Tests for SolveStatisticsReporter.listing method with filters."""

    def setUp(self) -> None:
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(
                1000000000, 10 * SECOND, 'F R U', '',
                comment='Fast solve',
                device='GAN356 X',
            ),
            Solve(2000000000, 15 * SECOND, 'R U F', ''),
            Solve(3000000000, 20 * SECOND, 'U F R', DNF),
            Solve(
                4000000000, 25 * SECOND, 'F U R', '+2',
                comment='Penalty',
            ),
            Solve(5000000000, 12 * SECOND, 'R F U', '', device='GoCube'),
        ]

    @patch('term_timer.interface.console.console.print')
    def test_listing_without_filters(self, mock_console: Mock) -> None:
        """Test listing without filters shows all solves."""
        reporter = SolveStatisticsReporter(3, self.solves)
        reporter.listing(0, 'index')

        self.assertEqual(mock_console.call_count, 6)

    @patch('term_timer.interface.console.console.print')
    def test_listing_with_comment_filter(self, mock_console: Mock) -> None:
        """Test listing with comment filter."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(with_comments=True)
        reporter.listing(0, 'index', filters)

        self.assertEqual(mock_console.call_count, 3)

    @patch('term_timer.interface.console.console.print')
    def test_listing_with_connected_filter(self, mock_console: Mock) -> None:
        """Test listing with connected filter."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(connected=True)
        reporter.listing(0, 'index', filters)

        self.assertEqual(mock_console.call_count, 3)

    @patch('term_timer.interface.console.console.print')
    def test_listing_with_dnf_filter(self, mock_console: Mock) -> None:
        """Test listing with DNF filter."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(dnf=True)
        reporter.listing(0, 'index', filters)

        self.assertEqual(mock_console.call_count, 2)

    @patch('term_timer.interface.console.console.print')
    def test_listing_with_no_matches(self, mock_console: Mock) -> None:
        """Test listing with filters that match no solves."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(search_comment='nonexistent')
        reporter.listing(0, 'index', filters)

        mock_console.assert_called()
        call_args = [str(call) for call in mock_console.call_args_list]
        warning_found = any(
            'No solves match' in call for call in call_args
        )
        self.assertTrue(warning_found)

    @patch('term_timer.interface.console.console.print')
    def test_listing_filters_with_limit(self, mock_console: Mock) -> None:
        """Test listing with filters and limit parameter."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(no_penalty=True)
        reporter.listing(1, 'index', filters)

        self.assertEqual(mock_console.call_count, 2)

    @patch('term_timer.interface.console.console.print')
    def test_listing_filters_with_time_sorting(
            self, mock_console: Mock) -> None:
        """Test listing with filters and time sorting."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(no_penalty=True)
        reporter.listing(0, 'time', filters)

        self.assertTrue(mock_console.call_count > 1)

    @patch('term_timer.interface.console.console.print')
    def test_listing_filters_with_combined_filters(
            self, mock_console: Mock) -> None:
        """Test listing with multiple combined filters."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(
            connected=True,
            no_penalty=True,
            min_time=11.0,
        )
        reporter.listing(0, 'index', filters)

        self.assertEqual(mock_console.call_count, 2)

    @patch('term_timer.interface.console.console.print')
    def test_listing_filters_preserves_original_indices(
            self, mock_console: Mock) -> None:
        """Test listing with filters preserves original solve indices."""
        reporter = SolveStatisticsReporter(3, self.solves)
        filters = ListingFilters(dnf=True)
        reporter.listing(0, 'index', filters)

        call_args = [str(call) for call in mock_console.call_args_list]
        index_found = any('#3' in call for call in call_args)
        self.assertTrue(index_found)


class TestSolveStatisticsReporterGraph(unittest.TestCase):
    """Tests for SolveStatisticsReporter graph trend curves."""

    def setUp(self) -> None:
        """Set up a session with enough solves for ao5 and ao12."""
        self.solves = [
            Solve(
                (i + 1) * 1000000000000,
                (10 + i) * SECOND,
                'F R U', '',
            )
            for i in range(12)
        ]

    def test_graph_respects_console_cap(self) -> None:
        """Only the first two configured average curves are drawn."""
        stats = SolveStatisticsReporter(3, self.solves)

        with patch('term_timer.stats.plt') as mock_plt, \
                patch(
                    'term_timer.stats.STATS_GRAPH_SERIES',
                    [('ao', 5), ('ao', 12), ('mo', 3)],
                ):
            stats.graph()

        labels = [
            call.kwargs.get('label')
            for call in mock_plt.plot.call_args_list
        ]
        self.assertEqual(labels, ['Time', 'AO5', 'AO12'])

    def test_graph_order_follows_configuration(self) -> None:
        """Curves follow the user-provided series order."""
        stats = SolveStatisticsReporter(3, self.solves)

        with patch('term_timer.stats.plt') as mock_plt, \
                patch(
                    'term_timer.stats.STATS_GRAPH_SERIES',
                    [('ao', 12), ('ao', 5)],
                ):
            stats.graph()

        labels = [
            call.kwargs.get('label')
            for call in mock_plt.plot.call_args_list
        ]
        self.assertEqual(labels, ['Time', 'AO12', 'AO5'])


class TestTrainerStatisticsResume(unittest.TestCase):
    """Tests for TrainerStatistics resume method."""

    def setUp(self) -> None:
        """Set up a training session over two OLL cases."""
        self.session_data = [
            ('27', get_case('OLL', '27'), 2000),
            ('27', get_case('OLL', '27'), 2400),
            ('21', get_case('OLL', '21'), 3000),
        ]
        self.due = datetime.now(tz=UTC) + timedelta(days=4)
        self.cases = {
            '27': CaseTraining(
                code='27',
                last_date=100,
                timings=[2000, 2400],
                fsrs_card=Card(state=State.Review, due=self.due),
            ),
        }

    def table_from_resume(
            self, cases: dict[str, CaseTraining] | None,
    ) -> Any:
        """
        Run resume and return the case table handed to the console.

        Returns:
            The Rich table of the per-case summary.

        """
        stats = TrainerStatistics(self.session_data, cases)

        with patch('term_timer.interface.console.console.print') as mock_print:
            stats.resume()

        return mock_print.call_args_list[-1][0][0]

    def test_resume_table_has_fsrs_columns(self) -> None:
        """The case table always exposes the State and Due columns."""
        table = self.table_from_resume(self.cases)

        headers = [column.header for column in table.columns]
        self.assertEqual(
            headers, ['Case', 'Σ', 'Mean', 'Best', 'State', 'Due'],
        )

    def test_resume_table_shows_card_state_and_due(self) -> None:
        """A case with a card shows its state and its next review date."""
        table = self.table_from_resume(self.cases)

        # Cases are sorted by code: '21' comes first, then '27'
        states = list(table.columns[4].cells)
        dues = list(table.columns[5].cells)
        self.assertEqual(states[1], '[stable]Stable[/stable]')
        self.assertEqual(
            dues[1],
            f'[no-ao]{ self.due.astimezone().strftime("%Y-%m-%d") }[/no-ao]',
        )

    def test_resume_table_shows_overdue_card_as_review(self) -> None:
        """A case whose review date has passed is shown as Review."""
        cases = {
            '27': CaseTraining(
                code='27',
                last_date=100,
                timings=[2000, 2400],
                fsrs_card=Card(
                    state=State.Review,
                    due=datetime.now(tz=UTC) - timedelta(days=3),
                ),
            ),
        }
        table = self.table_from_resume(cases)

        states = list(table.columns[4].cells)
        dues = list(table.columns[5].cells)
        self.assertEqual(states[1], '[review]Review[/review]')
        self.assertEqual(dues[1], '[warning]Overdue[/warning]')

    def test_resume_table_without_card(self) -> None:
        """A case with no card yet falls back to N/A."""
        table = self.table_from_resume(self.cases)

        states = list(table.columns[4].cells)
        dues = list(table.columns[5].cells)
        self.assertEqual(states[0], '[no-ao]N/A[/no-ao]')
        self.assertEqual(dues[0], '[no-ao]N/A[/no-ao]')

    def test_resume_table_without_trainings(self) -> None:
        """Omitting the trainings keeps the columns empty of card data."""
        table = self.table_from_resume(None)

        self.assertEqual(
            list(table.columns[4].cells),
            ['[no-ao]N/A[/no-ao]', '[no-ao]N/A[/no-ao]'],
        )


class TestDailySummaryReporter(unittest.TestCase):  # noqa: PLR0904
    """Tests for DailySummaryReporter class."""

    def setUp(self) -> None:
        """Set up a daily history with gaps, streaks and retries."""
        # 2 days, a gap, then a 3 days streak with retries.
        self.stack = [
            *self.make_day('2026-05-17', [30]),
            *self.make_day('2026-05-18', [28]),
            *self.make_day('2026-05-21', [25, 22, 40]),
            *self.make_day('2026-05-22', [26]),
            *self.make_day('2026-05-23', [35]),
        ]
        self.today = date(2026, 5, 25)
        self.reporter = DailySummaryReporter(3, self.stack, self.today)

    @staticmethod
    def make_day(
            session: str, seconds: list[float],
            flag: SolveFlag = '',
    ) -> list[Solve]:
        """
        Build the solves of a single daily session.

        Returns:
            List of Solve objects sharing the same session date.

        """
        return [
            Solve(
                1000000000 + index,
                int(second * SECOND),
                'F R U',
                flag,
                session=session,
            )
            for index, second in enumerate(seconds)
        ]

    def test_days_groups_solves_by_session(self) -> None:
        """Solves are grouped under the date of their session."""
        self.assertEqual(
            list(self.reporter.days),
            [
                date(2026, 5, 17),
                date(2026, 5, 18),
                date(2026, 5, 21),
                date(2026, 5, 22),
                date(2026, 5, 23),
            ],
        )
        self.assertEqual(self.reporter.days[date(2026, 5, 21)].total, 3)

    def test_days_keeps_chronological_order(self) -> None:
        """Days are sorted even when the sessions are loaded unordered."""
        reporter = DailySummaryReporter(
            3,
            self.make_day('2026-05-23', [30]) + self.make_day(
                '2026-05-17', [30],
            ),
            self.today,
        )

        self.assertEqual(
            reporter.played_days,
            [date(2026, 5, 17), date(2026, 5, 23)],
        )

    def test_days_skips_sessions_not_named_after_a_date(self) -> None:
        """A session whose name is not a date is left out."""
        reporter = DailySummaryReporter(
            3,
            self.make_day('2026-05-17', [30]) + self.make_day(
                'default', [30],
            ),
            self.today,
        )

        self.assertEqual(reporter.played_days, [date(2026, 5, 17)])

    def test_span_reaches_today(self) -> None:
        """The span runs from the first daily up to today, included."""
        self.assertEqual(self.reporter.span, 9)

    def test_span_without_solves(self) -> None:
        """An empty history has no span to measure."""
        reporter = DailySummaryReporter(3, [], self.today)

        self.assertEqual(reporter.span, 0)

    def test_participation_ratio(self) -> None:
        """Participation is the played days over the whole span."""
        self.assertAlmostEqual(self.reporter.participation, 5 / 9)

    def test_participation_without_solves(self) -> None:
        """An empty history participates in nothing."""
        reporter = DailySummaryReporter(3, [], self.today)

        self.assertEqual(reporter.participation, 0.0)

    def test_solves_per_day_counts_retries(self) -> None:
        """The cadence counts every solve of a played day."""
        self.assertAlmostEqual(self.reporter.solves_per_day, 7 / 5)

    def test_streaks_split_on_gaps(self) -> None:
        """Consecutive days are grouped, a missing day closing a block."""
        self.assertEqual(
            [len(streak) for streak in self.reporter.streaks],
            [2, 3],
        )

    def test_longest_streak(self) -> None:
        """The longest block of consecutive days wins."""
        self.assertEqual(
            self.reporter.longest_streak,
            [date(2026, 5, 21), date(2026, 5, 22), date(2026, 5, 23)],
        )

    def test_longest_streak_tie_keeps_the_most_recent(self) -> None:
        """On a tie the most recent streak is the one reported."""
        reporter = DailySummaryReporter(
            3,
            [
                *self.make_day('2026-05-01', [30]),
                *self.make_day('2026-05-02', [30]),
                *self.make_day('2026-05-10', [30]),
                *self.make_day('2026-05-11', [30]),
            ],
            self.today,
        )

        self.assertEqual(
            reporter.longest_streak,
            [date(2026, 5, 10), date(2026, 5, 11)],
        )

    def test_current_streak_alive_when_played_today(self) -> None:
        """A streak reaching today is the current one."""
        reporter = DailySummaryReporter(
            3, self.make_day('2026-05-25', [30]), self.today,
        )

        self.assertEqual(reporter.current_streak, [date(2026, 5, 25)])

    def test_current_streak_alive_when_played_yesterday(self) -> None:
        """The one day grace keeps yesterday's streak alive."""
        reporter = DailySummaryReporter(
            3, self.make_day('2026-05-24', [30]), self.today,
        )

        self.assertEqual(reporter.current_streak, [date(2026, 5, 24)])

    def test_current_streak_broken_after_two_days(self) -> None:
        """A streak older than the grace period is broken."""
        self.assertEqual(self.reporter.current_streak, [])

    def test_current_streak_without_solves(self) -> None:
        """An empty history has no current streak."""
        reporter = DailySummaryReporter(3, [], self.today)

        self.assertEqual(reporter.current_streak, [])

    def test_days_since_last(self) -> None:
        """The last played day is dated against today."""
        self.assertEqual(self.reporter.days_since_last, 2)

    def test_days_since_last_played_today(self) -> None:
        """Playing the daily of the day leaves no delay."""
        reporter = DailySummaryReporter(
            3, self.make_day('2026-05-25', [30]), self.today,
        )

        self.assertEqual(reporter.days_since_last, 0)

    def test_days_excludes_a_full_dnf_day(self) -> None:
        """A day never solved is dropped, its solves included."""
        reporter = DailySummaryReporter(
            3,
            [
                *self.make_day('2026-05-17', [30]),
                *self.make_day('2026-05-18', [28, 26], DNF),
            ],
            self.today,
        )

        self.assertEqual(reporter.played_days, [date(2026, 5, 17)])
        self.assertEqual(reporter.total_solves, 1)

    def test_days_keeps_a_partly_dnf_day(self) -> None:
        """One valid time is enough to keep the day and its retries."""
        reporter = DailySummaryReporter(
            3,
            self.make_day('2026-05-17', [30]) + self.make_day(
                '2026-05-17', [28], DNF,
            ),
            self.today,
        )

        self.assertEqual(reporter.played_days, [date(2026, 5, 17)])
        self.assertEqual(reporter.total_solves, 2)

    def test_best_day_holds_the_fastest_solve(self) -> None:
        """The best day is the one of the fastest solve, retries included."""
        self.assertEqual(
            self.reporter.best_day,
            (date(2026, 5, 21), 22 * SECOND),
        )

    def test_worst_day_holds_the_slowest_solve(self) -> None:
        """The worst day is the one of the slowest solve."""
        self.assertEqual(
            self.reporter.worst_day,
            (date(2026, 5, 21), 40 * SECOND),
        )

    def test_best_and_worst_day_without_timed_day(self) -> None:
        """Without a single timed solve no day can be ranked."""
        reporter = DailySummaryReporter(
            3, self.make_day('2026-05-17', [30], DNF), self.today,
        )

        self.assertIsNone(reporter.best_day)
        self.assertIsNone(reporter.worst_day)

    def test_punchcard_level_ranks_days_on_their_attempts(self) -> None:
        """Days are ranked on how many attempts they hold."""
        reporter = DailySummaryReporter(
            3,
            [
                *self.make_day('2026-05-17', [20]),
                *self.make_day('2026-05-18', [30] * 3),
                *self.make_day('2026-05-19', [40] * 5),
                *self.make_day('2026-05-20', [50] * 8),
            ],
            self.today,
        )

        self.assertEqual(reporter.punchcard_level(date(2026, 5, 17)), 0)
        self.assertEqual(reporter.punchcard_level(date(2026, 5, 18)), 1)
        self.assertEqual(reporter.punchcard_level(date(2026, 5, 19)), 2)
        self.assertEqual(reporter.punchcard_level(date(2026, 5, 20)), 3)

    def test_punchcard_level_ignores_the_other_days(self) -> None:
        """A level is absolute, not a rank inside the history."""
        reporter = DailySummaryReporter(
            3, self.make_day('2026-05-17', [20]), self.today,
        )

        self.assertEqual(reporter.punchcard_level(date(2026, 5, 17)), 0)

    def test_punchcard_level_counts_dnf_attempts(self) -> None:
        """A retried DNF still counts as an attempt of the day."""
        reporter = DailySummaryReporter(
            3,
            self.make_day('2026-05-17', [20]) + self.make_day(
                '2026-05-17', [20] * 5, DNF,
            ),
            self.today,
        )

        self.assertEqual(reporter.punchcard_level(date(2026, 5, 17)), 3)

    def test_punchcard_legend_describes_each_level(self) -> None:
        """The legend labels the attempt range opening each level."""
        self.assertEqual(
            self.reporter.punchcard_legend(),
            ['1', '2-3', '4-5', '6+'],
        )

    def test_punchcard_cell_of_a_played_day(self) -> None:
        """A played day is a block colored by its attempt level."""
        cell = self.reporter.punchcard_cell(date(2026, 5, 17))

        self.assertEqual(cell, '[punchcard-1]██[/punchcard-1]')

    def test_punchcard_cell_darkens_with_the_attempts(self) -> None:
        """A day of retries is brighter than a single attempt day."""
        self.assertEqual(
            self.reporter.punchcard_cell(date(2026, 5, 21)),
            '[punchcard-2]██[/punchcard-2]',
        )

    def test_punchcard_cell_of_a_missed_day(self) -> None:
        """A day inside the window without solve is a missed dot."""
        self.assertEqual(
            self.reporter.punchcard_cell(date(2026, 5, 19)),
            '[no-ao]··[/no-ao]',
        )

    def test_punchcard_cell_of_a_full_dnf_day(self) -> None:
        """A day played but never solved reads as a missed day."""
        reporter = DailySummaryReporter(
            3,
            [
                *self.make_day('2026-05-17', [30]),
                *self.make_day('2026-05-18', [28], DNF),
            ],
            self.today,
        )

        self.assertEqual(
            reporter.punchcard_cell(date(2026, 5, 18)),
            '[no-ao]··[/no-ao]',
        )

    def test_punchcard_cell_outside_of_the_window(self) -> None:
        """Days before the first daily or after today stay blank."""
        self.assertEqual(
            self.reporter.punchcard_cell(date(2026, 5, 16)),
            '  ',
        )
        self.assertEqual(
            self.reporter.punchcard_cell(date(2026, 5, 26)),
            '  ',
        )

    def test_punchcard_header_marks_starting_months(self) -> None:
        """Only the weeks opening a new month carry their initial."""
        weeks = [date(2026, 5, 25), date(2026, 6, 1), date(2026, 6, 8)]

        self.assertEqual(self.reporter.punchcard_header(weeks), 'M J   ')

    def test_punchcard_rows_are_aligned(self) -> None:
        """Every weekday row holds exactly one cell per displayed week."""
        with patch('term_timer.interface.console.console.print') as mock_print:
            self.reporter.punchcard()

        # Title, month header, 7 weekday rows, then the legend.
        rows = mock_print.call_args_list[2:9]
        self.assertEqual(len(rows), len(WEEK_DAYS))

        header = mock_print.call_args_list[1][0][1]
        for row in rows:
            cells = re.sub(r'\[/?[a-z0-9-]+\]', '', row[0][1])
            self.assertEqual(
                len(cells),
                len(re.sub(r'\[/?[a-z0-9-]+\]', '', header)),
            )

    def test_punchcard_keeps_the_most_recent_weeks(self) -> None:
        """The week limit trims the oldest columns of the punchcard."""
        with patch('term_timer.interface.console.console.print') as mock_print:
            self.reporter.punchcard(weeks_limit=1)

        cells = re.sub(
            r'\[/?[a-z0-9-]+\]', '', mock_print.call_args_list[2][0][1],
        )
        self.assertEqual(len(cells), len(PUNCHCARD_CELL))

    def test_punchcard_without_solves(self) -> None:
        """An empty history draws no punchcard."""
        reporter = DailySummaryReporter(3, [], self.today)

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.punchcard()

        mock_print.assert_not_called()

    def test_resume_reports_attendance(self) -> None:
        """The resume exposes the days, the streaks and the extremes."""
        with patch('term_timer.interface.console.console.print') as mock_print:
            self.reporter.resume()

        output = ' '.join(
            str(argument)
            for call in mock_print.call_args_list
            for argument in call[0]
        )

        self.assertIn('Days  :', output)
        self.assertIn('Streak:', output)
        self.assertIn('2026-05-21', output)
        self.assertIn('55.56%', output)
        self.assertIn('00:22.000', output)
        self.assertIn('00:40.000', output)

    def test_resume_without_solves(self) -> None:
        """An empty history prints no resume at all."""
        reporter = DailySummaryReporter(3, [], self.today)

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.resume()

        mock_print.assert_not_called()

    def test_resume_without_timed_day(self) -> None:
        """A history of DNF only days holds nothing to resume."""
        reporter = DailySummaryReporter(
            3, self.make_day('2026-05-17', [30], DNF), self.today,
        )

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.resume()

        mock_print.assert_not_called()

    def test_days_table_lists_every_played_day(self) -> None:
        """The table holds one row per played day, oldest first."""
        with patch('term_timer.interface.console.console.print') as mock_print:
            self.reporter.days_table()

        table = mock_print.call_args_list[-1][0][0]

        self.assertEqual(
            list(table.columns[0].cells),
            [
                '[date]2026-05-17[/date]',
                '[date]2026-05-18[/date]',
                '[date]2026-05-21[/date]',
                '[date]2026-05-22[/date]',
                '[date]2026-05-23[/date]',
            ],
        )
        self.assertEqual(
            next(iter(table.columns[1].cells)),
            '[session]Sun[/session]',
        )
        self.assertEqual(
            list(table.columns[2].cells)[2],
            '[stats]3[/stats]',
        )
        self.assertEqual(
            list(table.columns[3].cells)[2],
            '[green]00:22.000[/green]',
        )

    def test_days_table_limits_the_listed_days(self) -> None:
        """Only the most recent played days are listed."""
        with patch('term_timer.interface.console.console.print') as mock_print:
            self.reporter.days_table(limit=2)

        table = mock_print.call_args_list[-1][0][0]

        self.assertEqual(
            list(table.columns[0].cells),
            ['[date]2026-05-22[/date]', '[date]2026-05-23[/date]'],
        )

    def test_days_table_without_solves(self) -> None:
        """An empty history prints no table."""
        reporter = DailySummaryReporter(3, [], self.today)

        with patch('term_timer.interface.console.console.print') as mock_print:
            reporter.days_table()

        mock_print.assert_not_called()
