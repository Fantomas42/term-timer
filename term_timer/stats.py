"""Statistics calculation and display for solve sessions."""
from datetime import date
from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING
from typing import cast

import numpy as np
import plotext as plt
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases.case import Case
from cubing_algs.vcube import VCube
from numpy.lib.stride_tricks import sliding_window_view
from rich import box
from rich.table import Table

from term_timer.annotations import CaseStats
from term_timer.annotations import ListingFilters
from term_timer.annotations import MethodAnalysis
from term_timer.config import STATS_DISTRIBUTION
from term_timer.config import STATS_GRAPH_SERIES
from term_timer.config import STATS_SESSION_SERIES
from term_timer.config import STATS_SOLVE_METRICS
from term_timer.config import STATS_TRIM
from term_timer.constants import DAILY_DAYS_LISTED
from term_timer.constants import DNF
from term_timer.constants import GRAPH_CONSOLE_COLORS
from term_timer.constants import GRAPH_CONSOLE_FALLBACK
from term_timer.constants import GRAPH_CONSOLE_LIMIT
from term_timer.constants import MONTH_INITIALS
from term_timer.constants import PLUS_TWO
from term_timer.constants import PUNCHCARD_CELL
from term_timer.constants import PUNCHCARD_LEVELS
from term_timer.constants import PUNCHCARD_STYLES
from term_timer.constants import PUNCHCARD_WEEKS
from term_timer.constants import SECOND
from term_timer.constants import SECOND_BINS
from term_timer.constants import STEP_BAR
from term_timer.constants import WEEK_DAYS
from term_timer.formatter import compute_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_duration
from term_timer.formatter import format_edge
from term_timer.formatter import format_flag
from term_timer.formatter import format_fluency
from term_timer.formatter import format_fsrs_due
from term_timer.formatter import format_fsrs_state
from term_timer.formatter import format_grade
from term_timer.formatter import format_score
from term_timer.formatter import format_term_timer_case_url
from term_timer.formatter import format_time
from term_timer.interface.console import console
from term_timer.interface.series import SeriesReporter
from term_timer.printer import print_cube_scrambled
from term_timer.solve import Solve

if TYPE_CHECKING:
    from term_timer.fsrs.storage import CaseTraining
    from term_timer.methods.base import Analyser


# Sentinels returned by target_to_beat_best_ao alongside a positive target
# time: no next solve can set a new best, or any next solve will
TARGET_NEVER = -2
TARGET_ALWAYS = -3


class StatisticsTools:
    """
    Provides core statistical calculation tools for timed sessions.

    This class handles the fundamental calculations for time statistics
    including mean of N (mo), average of N (ao), and best results.
    """

    def __init__(self, stack_time: list[int]) -> None:
        """
        Initialize the statistics tools with a stack of times.

        Args:
            stack_time: List of time objects to analyze.

        """
        self.stack_time = stack_time
        self.stack_time_sorted = sorted(
            [s for s in self.stack_time if s],
        )

    @staticmethod
    def mo(limit: int, stack_elapsed: list[int]) -> int:
        """
        Calculate the mean of N (moN) for the last N times.

        A DNF time (0) in the window makes the whole moN a DNF,
        following WCA semantics.

        Args:
            limit: Number of most recent times to include.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Mean time in milliseconds, 0 if the window contains a DNF,
            or -1 if insufficient data.

        """
        if limit > len(stack_elapsed):
            return -1

        last_of = stack_elapsed[-limit:]
        if 0 in last_of:
            return 0

        return int(np.mean(last_of))

    @staticmethod
    def mb(limit: int, stack_elapsed: list[int]) -> int:
        """
        Calculate the mean of the N fastest times (mbN).

        DNF times (0) are the worst possible results and never rank among
        the fastest, so they are excluded before averaging; a session made
        entirely of DNFs has no valid best and is itself a DNF.

        Args:
            limit: Number of fastest times to include.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Mean of the N best times in milliseconds, 0 if every time is a
            DNF, or -1 if insufficient data.

        """
        if limit > len(stack_elapsed):
            return -1

        valid = sorted(time for time in stack_elapsed if time)
        if not valid:
            return 0

        return int(np.mean(valid[:limit]))

    @staticmethod
    def mw(limit: int, stack_elapsed: list[int]) -> int:
        """
        Calculate the mean of the N slowest times (mwN).

        DNF times (0) carry no real duration and are excluded before
        averaging; a session made entirely of DNFs has no valid worst and
        is itself a DNF.

        Args:
            limit: Number of slowest times to include.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Mean of the N worst times in milliseconds, 0 if every time is a
            DNF, or -1 if insufficient data.

        """
        if limit > len(stack_elapsed):
            return -1

        valid = sorted(time for time in stack_elapsed if time)
        if not valid:
            return 0

        return int(np.mean(valid[-limit:]))

    @staticmethod
    def trim_count(spec: str, limit: int) -> int:
        """
        Compute how many solves to drop from each end of a window.

        Supports three trim modes:

        - ``pN`` trims ``ceil(limit * N / 100)`` per side (percentage,
          WCA = 5)
        - ``m`` trims ``limit // 2`` per side (median)
        - a bare integer trims that many solves per side (fixed count)

        The trim steps back by one when both sides together would consume
        the whole window; a final clamp keeps at least one solve for
        degenerate configurations.

        Args:
            spec: Trim specification (``pN``, ``m`` or an integer string).
            limit: Window size.

        Returns:
            Number of solves to drop from each end of the window.

        """
        if spec.startswith('p'):
            count = int(np.ceil(limit * int(spec[1:]) / 100))
        elif spec == 'm':
            count = limit // 2
        else:
            count = int(spec)

        if 2 * count == limit:
            count = max(count - 1, 0)

        return min(count, (limit - 1) // 2)

    @staticmethod
    def normalize_trim(spec: str) -> str:
        """
        Validate and normalise a trim specification string.

        Accepts trim specs — ``pN`` (percentage), ``m`` (median) or a bare
        integer (fixed count) — and falls back to the WCA default ``p5``
        for anything unrecognised.

        Args:
            spec: Raw trim specification to validate.

        Returns:
            A valid trim specification string.

        """
        spec = spec.strip()
        if spec == 'm':
            return spec
        if spec.startswith('p') and spec[1:].isdigit():
            return spec
        if spec.isdigit():
            return spec

        return 'p5'

    @staticmethod
    def ao(limit: int, stack_elapsed: list[int]) -> int:
        """
        Calculate the average of N (aoN) excluding best/worst times.

        Trims the top and bottom of the window before averaging, using the
        configured trim mode (default WCA 5% per side); see ``trim_count``.

        DNF times (0) count as the worst times and are trimmed first;
        if the window contains more DNFs than the trim cap, the whole
        aoN is a DNF, following WCA semantics.

        Args:
            limit: Number of most recent times to include.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Average time in milliseconds, 0 if the window contains too
            many DNFs, or -1 if insufficient data.

        """
        if limit > len(stack_elapsed):
            return -1

        cap = StatisticsTools.trim_count(STATS_TRIM, limit)

        last_of = stack_elapsed[-limit:]

        dnfs = last_of.count(0)
        if dnfs > cap:
            return 0

        last_of = [time for time in last_of if time]
        for _ in range(cap - dnfs):
            last_of.remove(max(last_of))
        for _ in range(cap):
            last_of.remove(min(last_of))

        return int(np.mean(last_of))

    def best_mo(self, limit: int) -> int:
        """
        Find the best mean of N across all rolling windows.

        Iterates through all possible consecutive time windows to find
        the minimum mean time. Windows containing a DNF are skipped.

        Args:
            limit: Window size for calculating mean.

        Returns:
            Best mean time in milliseconds, 0 if no valid windows, or -1
            if there are fewer times than the window size.

        """
        if limit > len(self.stack_time):
            return -1

        windows = sliding_window_view(
            np.asarray(self.stack_time, dtype=np.float64),
            limit,
        )

        # A DNF (0) anywhere in a window invalidates it
        valid = ~(windows == 0).any(axis=1)
        if not valid.any():
            return 0

        return int(windows[valid].mean(axis=1).min())

    def best_ao(self, limit: int) -> int:
        """
        Find the best average of N across all rolling windows.

        Iterates through all possible consecutive time windows to find
        the minimum average time. Windows counting as DNF are skipped.

        Args:
            limit: Window size for calculating average.

        Returns:
            Best average time in milliseconds, 0 if no valid windows, or
            -1 if there are fewer times than the window size.

        """
        if limit > len(self.stack_time):
            return -1

        cap = self.trim_count(STATS_TRIM, limit)

        # DNF (0) maps to +inf so it sorts as a worst time and is trimmed
        # from the top first, mirroring the WCA semantics
        arr = np.asarray(self.stack_time, dtype=np.float64)
        arr = np.where(arr == 0, np.inf, arr)

        windows = np.sort(sliding_window_view(arr, limit), axis=1)
        trimmed = windows[:, cap:limit - cap]

        # A window with more DNFs than the trim cap keeps an inf and is
        # itself a DNF, so it is excluded from the best average
        valid = np.isfinite(trimmed).all(axis=1)
        if not valid.any():
            return 0

        return int(trimmed[valid].mean(axis=1).min())

    @staticmethod
    def bpa(limit: int, stack_elapsed: list[int]) -> int:
        """
        Calculate the best possible average on the next solve (BPA).

        Returns the aoN you would obtain if the next solve were perfect.
        The window is the last ``limit - 1`` real solves plus a synthetic
        perfect solve (0 ms, the best possible time), trimmed with the same
        caps as ``ao``.

        DNF times (0) count as the worst and are trimmed first; if the
        existing window already holds more DNFs than the trim cap, even a
        perfect solve cannot save it and the BPA is a DNF.

        Args:
            limit: Window size of the average being projected.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Best possible average in milliseconds, 0 if the window is a DNF,
            or -1 if there are fewer than ``limit - 1`` times.

        """
        if limit - 1 > len(stack_elapsed):
            return -1

        cap = StatisticsTools.trim_count(STATS_TRIM, limit)

        window = stack_elapsed[len(stack_elapsed) - (limit - 1):]
        if window.count(0) > cap:
            return 0

        # DNF (0) maps to +inf to sort and trim as the worst; the perfect
        # next solve enters as a genuine 0 ms, the absolute best time
        arr = np.asarray(window, dtype=np.float64)
        arr = np.where(arr == 0, np.inf, arr)
        arr = np.sort(np.append(arr, 0.0))

        return int(arr[cap:limit - cap].mean())

    @staticmethod
    def wpa(limit: int, stack_elapsed: list[int]) -> int:
        """
        Calculate the worst possible average on the next solve (WPA).

        Returns the aoN you would obtain if the next solve were a DNF.
        The window is the last ``limit - 1`` real solves plus a synthetic
        DNF, trimmed with the same caps as ``ao``.

        The synthetic DNF counts as the worst time and is trimmed first; if
        adding it pushes the DNF count beyond the trim cap, the WPA is a DNF.

        Args:
            limit: Window size of the average being projected.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Worst possible average in milliseconds, 0 if the window is a DNF,
            or -1 if there are fewer than ``limit - 1`` times.

        """
        if limit - 1 > len(stack_elapsed):
            return -1

        cap = StatisticsTools.trim_count(STATS_TRIM, limit)

        window = stack_elapsed[len(stack_elapsed) - (limit - 1):]
        if window.count(0) + 1 > cap:
            return 0

        # DNF (0) and the synthetic DNF next solve map to +inf, sorting and
        # trimming as the worst times
        arr = np.asarray(window, dtype=np.float64)
        arr = np.where(arr == 0, np.inf, arr)
        arr = np.sort(np.append(arr, np.inf))

        return int(arr[cap:limit - cap].mean())

    def target_to_beat_best_ao(self, limit: int) -> int:
        """
        Time to hit on the next solve to set a new best average of N.

        Answers: how fast must the next solve be so the resulting aoN ties
        or beats the session's current best aoN? The projected window is the
        last ``limit - 1`` real solves plus the upcoming solve, trimmed with
        the same caps as ``ao``.

        Returns:
            A positive target time in milliseconds (solve that or faster to
            set a new best); ``TARGET_ALWAYS`` if any time would do it (no
            valid best yet); ``TARGET_NEVER`` if no time can (the target
            would be unreachable or the projected window is a DNF); or -1 if
            there are fewer than ``limit`` times.

        """
        if limit > len(self.stack_time):
            return -1

        cap = StatisticsTools.trim_count(STATS_TRIM, limit)
        neff = limit - 2 * cap

        # The next solve is a real time; the carried part is the last
        # limit - 1 solves. Too many DNFs there force the next aoN to a DNF.
        window = self.stack_time[len(self.stack_time) - (limit - 1):]
        if window.count(0) > cap:
            return TARGET_NEVER

        # No valid best average yet (every past window was a DNF): the next
        # solve sets the first one, whatever its time
        best = self.best_ao(limit)
        if best == 0:
            return TARGET_ALWAYS

        # Sort the carried solves, DNF (0) -> +inf at the worst end. The next
        # solve lands in the kept band between lower and upper; outside it the
        # trimmed average saturates, which the two sentinels capture.
        arr = sorted(np.inf if time == 0 else float(time) for time in window)
        lower = arr[cap - 1] if cap else 0.0
        upper = arr[limit - 1 - cap] if cap else np.inf
        kept_sum = sum(arr[cap:limit - 1 - cap])

        target = best * neff - kept_sum
        if target <= 0 or target < lower:
            return TARGET_NEVER
        if upper < target:
            return TARGET_ALWAYS

        return int(target)


class Statistics(StatisticsTools):  # noqa: PLR0904
    """
    Computes comprehensive statistics for timed sessions.

    Extends StatisticsTools with cached properties for commonly used
    statistics like best/worst times, averages, and distribution analysis.
    """

    @cached_property
    def mb3(self) -> int:
        """
        Calculate mean of the 3 fastest times.

        Returns:
            Mean of 3 best times in milliseconds, or -1 if insufficient data.

        """
        return self.mb(3, self.stack_time)

    @cached_property
    def mw3(self) -> int:
        """
        Calculate mean of the 3 slowest times.

        Returns:
            Mean of 3 worst times in milliseconds, or -1 if insufficient data.

        """
        return self.mw(3, self.stack_time)

    @cached_property
    def mb10(self) -> int:
        """
        Calculate mean of the 10 fastest times.

        Returns:
            Mean of 10 best times in milliseconds, or -1 if insufficient
            data.

        """
        return self.mb(10, self.stack_time)

    @cached_property
    def mw10(self) -> int:
        """
        Calculate mean of the 10 slowest times.

        Returns:
            Mean of 10 worst times in milliseconds, or -1 if insufficient
            data.

        """
        return self.mw(10, self.stack_time)

    @cached_property
    def mo3(self) -> int:
        """
        Calculate mean of last 3 times.

        Returns:
            Mean of 3 in milliseconds, or -1 if insufficient data.

        """
        return self.mo(3, self.stack_time)

    @cached_property
    def ao5(self) -> int:
        """
        Calculate average of last 5 times.

        Returns:
            Average of 5 in milliseconds, or -1 if insufficient data.

        """
        return self.ao(5, self.stack_time)

    @cached_property
    def ao12(self) -> int:
        """
        Calculate average of last 12 times.

        Returns:
            Average of 12 in milliseconds, or -1 if insufficient data.

        """
        return self.ao(12, self.stack_time)

    @cached_property
    def ao100(self) -> int:
        """
        Calculate average of last 100 times.

        Returns:
            Average of 100 in milliseconds, or -1 if insufficient data.

        """
        return self.ao(100, self.stack_time)

    @cached_property
    def ao1000(self) -> int:
        """
        Calculate average of last 1000 times.

        Returns:
            Average of 1000 in milliseconds, or -1 if insufficient data.

        """
        return self.ao(1000, self.stack_time)

    @cached_property
    def best_mo3(self) -> int:
        """
        Find best mean of 3 across all windows.

        Returns:
            Best mo3 in milliseconds, or 0 if no valid windows.

        """
        return self.best_mo(3)

    @cached_property
    def best_ao5(self) -> int:
        """
        Find best average of 5 across all windows.

        Returns:
            Best ao5 in milliseconds, or 0 if no valid windows.

        """
        return self.best_ao(5)

    @cached_property
    def best_ao12(self) -> int:
        """
        Find best average of 12 across all windows.

        Returns:
            Best ao12 in milliseconds, or 0 if no valid windows.

        """
        return self.best_ao(12)

    @cached_property
    def best_ao100(self) -> int:
        """
        Find best average of 100 across all windows.

        Returns:
            Best ao100 in milliseconds, or 0 if no valid windows.

        """
        return self.best_ao(100)

    @cached_property
    def best_ao1000(self) -> int:
        """
        Find best average of 1000 across all windows.

        Returns:
            Best ao1000 in milliseconds, or 0 if no valid windows.

        """
        return self.best_ao(1000)

    @cached_property
    def bpa5(self) -> int:
        """
        Best possible average of 5 on the next solve.

        Returns:
            Best possible ao5 in milliseconds, 0 if a DNF, or -1 if
            insufficient data.

        """
        return self.bpa(5, self.stack_time)

    @cached_property
    def wpa5(self) -> int:
        """
        Worst possible average of 5 on the next solve.

        Returns:
            Worst possible ao5 in milliseconds, 0 if a DNF, or -1 if
            insufficient data.

        """
        return self.wpa(5, self.stack_time)

    @cached_property
    def bpa12(self) -> int:
        """
        Best possible average of 12 on the next solve.

        Returns:
            Best possible ao12 in milliseconds, 0 if a DNF, or -1 if
            insufficient data.

        """
        return self.bpa(12, self.stack_time)

    @cached_property
    def wpa12(self) -> int:
        """
        Worst possible average of 12 on the next solve.

        Returns:
            Worst possible ao12 in milliseconds, 0 if a DNF, or -1 if
            insufficient data.

        """
        return self.wpa(12, self.stack_time)

    @cached_property
    def ao5_target(self) -> int:
        """
        Time to hit on the next solve to set a new best ao5.

        Returns:
            Target time in milliseconds, ``TARGET_ALWAYS``, ``TARGET_NEVER``,
            or -1 if insufficient data.

        """
        return self.target_to_beat_best_ao(5)

    @cached_property
    def ao12_target(self) -> int:
        """
        Time to hit on the next solve to set a new best ao12.

        Returns:
            Target time in milliseconds, ``TARGET_ALWAYS``, ``TARGET_NEVER``,
            or -1 if insufficient data.

        """
        return self.target_to_beat_best_ao(12)

    @cached_property
    def best(self) -> int:
        """
        Return the fastest time.

        Returns:
            Best time in milliseconds, or 0 if no data.

        """
        if self.stack_time_sorted:
            return self.stack_time_sorted[0]
        return 0

    @cached_property
    def worst(self) -> int:
        """
        Return the slowest time.

        Returns:
            Worst time in milliseconds, or 0 if no data.

        """
        if self.stack_time_sorted:
            return self.stack_time_sorted[-1]
        return 0

    @cached_property
    def mean(self) -> int:
        """
        Calculate mean time across all times, excluding DNFs.

        Returns:
            Mean time in milliseconds, or 0 if no valid times.

        """
        if self.stack_time_sorted:
            return int(np.mean(self.stack_time_sorted))
        return 0

    @cached_property
    def median(self) -> int:
        """
        Calculate median time across all times, excluding DNFs.

        Returns:
            Median time in milliseconds, or 0 if no valid times.

        """
        if self.stack_time_sorted:
            return int(np.median(self.stack_time_sorted))
        return 0

    @cached_property
    def stdev(self) -> int:
        """
        Calculate standard deviation of times, excluding DNFs.

        Returns:
            Standard deviation in milliseconds, or 0 if no valid times.

        """
        if self.stack_time_sorted:
            return int(np.std(self.stack_time_sorted))
        return 0

    @cached_property
    def delta(self) -> int:
        """
        Calculate time difference between last two times.

        Returns:
            Time delta in milliseconds (positive if slower, negative if
            faster).

        """
        if len(self.stack_time) > 1:
            return (
                self.stack_time[-1]
                - self.stack_time[-2]
            )

        return 0

    @cached_property
    def total(self) -> int:
        """
        Return total number of times in the session.

        Returns:
            Count of times.

        """
        return len(self.stack_time)

    @cached_property
    def total_time(self) -> int:
        """
        Calculate cumulative time spent solving.

        Returns:
            Total time in milliseconds.

        """
        return sum(self.stack_time)

    @cached_property
    def repartition(self) -> list[tuple[int, int]]:
        """
        Compute time distribution histogram for times.

        Creates histogram bins based on the time range and returns count
        and edge value for each non-empty bin.

        Returns:
            List of tuples containing (count, bin_edge) for distribution
            visualization.

        """
        gap = (self.worst - self.best) / SECOND

        best_bin: float = STATS_DISTRIBUTION
        if not best_bin:
            for second in SECOND_BINS:
                if gap / 10 < second:
                    best_bin = second
                    break

        values = [st / SECOND for st in self.stack_time_sorted]
        if not values:
            return []

        min_val = (np.min(values) // best_bin) * best_bin
        max_val = ((np.max(values) // best_bin) + 1) * best_bin

        bin_count = round(float(max_val - min_val) / best_bin) + 1
        bins = np.linspace(min_val, max_val, bin_count)

        (histo, bin_edges) = np.histogram(values, bins=bins)

        return [
            (value, edge)
            for value, edge in zip(histo, bin_edges, strict=False)
            if value
        ]


class SolveStatisticsReporter(Statistics):
    """
    Formats and displays statistics for solve sessions.

    Extends Statistics with methods for presenting data through the
    console, including formatted summaries, detailed solve analysis, and
    graphical visualizations.
    """

    def __init__(self, cube_size: int, stack: list[Solve]) -> None:
        """
        Initialize the statistics reporter.

        Args:
            cube_size: Dimension of the cube (e.g., 3 for 3x3x3).
            stack: List of Solve objects to analyze.

        """
        self.cube_size = cube_size
        self.cube_name = f'{ cube_size }x{ cube_size }x{ cube_size }'

        self.stack = stack
        super().__init__([s.final_time for s in stack])

    @cached_property
    def delta(self) -> int:
        """
        Override calculate time difference between last two solves,
        excluding penality.

        Returns:
            Time delta in milliseconds (positive if slower, negative if
            faster).

        """
        if len(self.stack) > 1:
            return (
                self.stack[-1].time
                - self.stack[-2].time
            )

        return 0

    @cached_property
    def total_time(self) -> int:
        """
        Override calculate cumulative time spent solving, counting
        the real time of DNF solves.

        Returns:
            Total time in milliseconds.

        """
        return sum(s.final_time or s.time for s in self.stack)

    @cached_property
    def advanced_solves(self) -> float:
        """
        Calculate ratio of advanced solves with method analysis.

        Returns:
            Proportion of advanced solves (0.0 to 1.0).

        """
        return sum(1 for s in self.stack if s.advanced) / self.total

    @cached_property
    def commented_solves(self) -> float:
        """
        Calculate ratio of commented solves.

        Returns:
            Proportion of commented solves (0.0 to 1.0).

        """
        return sum(1 for s in self.stack if s.comment) / self.total

    @cached_property
    def unfinished_solves(self) -> float:
        """
        Calculate ratio of DNF solves.

        Returns:
            Proportion of solves with a DNF flag (0.0 to 1.0).

        """
        return sum(1 for s in self.stack if s.flag == DNF) / self.total

    @cached_property
    def penalized_solves(self) -> float:
        """
        Calculate ratio of +2 solves.

        Returns:
            Proportion of solves with a +2 flag (0.0 to 1.0).

        """
        return sum(1 for s in self.stack if s.flag == PLUS_TWO) / self.total

    @cached_property
    def score(self) -> float:
        """
        Calculate average score across all analysable solves.

        Returns:
            Mean score value across all analysable solves, 0.0 when none
            is analysable. DNF solves are excluded: their method score is
            derived from an unsolved cube and would skew the mean.

        """
        scores = [
            cast('float', s.score) for s in self.stack if s.analysable
        ]

        if not scores:
            return 0.0

        return sum(scores) / len(scores)

    def resume(self, prefix: str = '', style: str = 'stats', *,
               show_title: bool = False) -> None:
        """
        Display comprehensive statistics summary to the console.

        Shows total solves, timing statistics, averages, and distribution
        histogram formatted for terminal output.

        Args:
            prefix: String to prepend to each line for indentation.
            style: Rich console style name for formatting labels.
            show_title: Whether to display the cube name title.

        """
        if show_title:
            console.print(
                f'[title]Statistics for { self.cube_name }[/title]',
            )

        dnf_count = sum(1 for s in self.stack if s.flag == DNF)
        total_display = (
            f'{ self.total - dnf_count }/{ self.total }'
            if dnf_count
            else str(self.total)
        )
        console.print(
            f'[{ style }]{ prefix }Total :[/{ style }]',
            f'[result]{ total_display }[/result]',
        )
        console.print(
            f'[{ style }]{ prefix }Time  :[/{ style }]',
            f'[result]{ format_time(self.total_time) }[/result]',
        )
        console.print(
            f'[{ style }]{ prefix }Mean  :[/{ style }]',
            f'[result]{ format_time(self.mean) }[/result]',
        )
        console.print(
            f'[{ style }]{ prefix }Median:[/{ style }]',
            f'[result]{ format_time(self.median) }[/result]',
        )
        console.print(
            f'[{ style }]{ prefix }Stdev :[/{ style }]',
            f'[result]{ format_time(self.stdev) }[/result]',
        )
        if self.total >= 2:
            if self.total >= 3:
                console.print(
                    f'[{ style }]{ prefix }Best  :[/{ style }]',
                    f'[green]{ format_time(self.best) }[/green]',
                    f'[{ style }]MB3  :[/{ style }]',
                    f'[result]{ format_time(self.mb3) }[/result]',
                    format_delta(self.mb3 - self.best),
                )
                console.print(
                    f'[{ style }]{ prefix }Worst :[/{ style }]',
                    f'[red]{ format_time(self.worst) }[/red]',
                    f'[{ style }]MW3  :[/{ style }]',
                    f'[result]{ format_time(self.mw3) }[/result]',
                    format_delta(self.mw3 - self.worst),
                )
            else:
                console.print(
                    f'[{ style }]{ prefix }Best  :[/{ style }]',
                    f'[green]{ format_time(self.best) }[/green]',
                )
                console.print(
                    f'[{ style }]{ prefix }Worst :[/{ style }]',
                    f'[red]{ format_time(self.worst) }[/red]',
                )
        for kind, size in STATS_SESSION_SERIES:
            if self.total < size:
                continue

            value = getattr(self, kind)(size, self.stack_time)
            best = getattr(self, f'best_{ kind }')(size)
            token = f'{ kind }{ size }'
            value_style = SeriesReporter.series_style(token)
            label = SeriesReporter.series_label(kind, size)
            console.print(
                f'[{ style }]{ prefix }{ label:<6}:[/{ style }]',
                f'[{ value_style }]{ format_time(value) }[/{ value_style }]',
                f'[{ style }]Best :[/{ style }]',
                f'[result]{ format_time(best) }[/result]',
                format_delta(value - best),
            )

        if self.total > 1 and self.repartition:
            max_count = compute_padding(
                max(c for c, e in self.repartition),
            )

            max_edge = max(e for c, e in self.repartition)
            decimals = 1 if any(
                e != int(e) for c, e in self.repartition
            ) else 0
            total_percent = 0.0
            for count, edge in self.repartition:
                percent = (count / self.total)
                total_percent += percent

                start = f'[{ style }]{ count!s:{" "}>{max_count}} '
                start += (
                    f'([edge]{ format_edge(edge, max_edge, decimals) }[/edge])'
                )
                start = start.ljust(26 + len(prefix))

                console.print(
                    f'{ start }:[/{ style }]',
                    f'[bar]{ round(percent * STEP_BAR) * " " }[/bar]'
                    f'{ (STEP_BAR - round(percent * STEP_BAR)) * " " }'
                    f'[result]{ percent * 100:05.2f}%[/result]   ',
                    f'[percent]{ total_percent * 100:05.2f}%[/percent]',
                )

    @staticmethod
    def matches_filters(solve: Solve, filters: ListingFilters) -> bool:  # noqa: C901, PLR0911, PLR0912
        """
        Check if a solve matches the specified filters.

        Args:
            solve: The solve to check.
            filters: The filter criteria to apply.

        Returns:
            True if the solve matches all filters, False otherwise.

        """
        if filters.with_comments and not solve.comment:
            return False
        if filters.without_comments and solve.comment:
            return False

        if filters.connected and not solve.device:
            return False
        if filters.unconnected and solve.device:
            return False

        if filters.dnf and solve.flag != DNF:
            return False
        if filters.plus_two and solve.flag != PLUS_TWO:
            return False
        if filters.no_penalty and solve.flag:
            return False

        if filters.search_comment:
            if not solve.comment:
                return False
            if filters.search_comment.lower() not in solve.comment.lower():
                return False

        if filters.search_scramble:
            scramble_str = str(solve.scramble)
            if filters.search_scramble.lower() not in scramble_str.lower():
                return False

        if filters.min_time is not None:
            min_time_ms = int(filters.min_time * SECOND)
            if solve.time < min_time_ms:
                return False

        if filters.max_time is not None:
            max_time_ms = int(filters.max_time * SECOND)
            if solve.time > max_time_ms:
                return False

        return True

    def listing(  # noqa: C901
            self, limit: int, sorting: str,
            filters: ListingFilters | None = None) -> None:
        """
        Display a formatted list of solves to the console.

        Args:
            limit: Number of solves to display (positive for first N,
                negative for last N, 0 for all).
            sorting: Sort order, either 'time' or 'chronological'.
            filters: Optional filters to apply to the solve list.

        """
        if filters is None:
            filters = ListingFilters()

        console.print(
            f'[title]Listing for { self.cube_name }[/title]',
        )

        size = len(self.stack)

        indexed_solves = [
            (size - i, self.stack[size - (i + 1)])
            for i in range(size)
        ]

        filtered_solves = [
            (idx, solve)
            for idx, solve in indexed_solves
            if self.matches_filters(solve, filters)
        ]

        if not filtered_solves:
            console.print(
                'No solves match the specified filters.',
                style='warning',
            )
            return

        filtered_size = len(filtered_solves)
        max_count = compute_padding(size) + 1

        if not limit:
            s = slice(None, None)
        elif limit > 0:
            s = slice(None, limit)
        else:
            s = slice(limit, None)

        indices = range(*s.indices(filtered_size))

        if sorting == 'time':
            filtered_solves.sort(
                key=lambda x: (x[1].final_time == 0, x[1].final_time),
            )

        for indice in indices:
            original_index, solve = filtered_solves[indice]
            index = f'#{ original_index }'
            date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

            header = (
                f'[localhost][link={ solve.link_term_timer }]'
                f'{ index:{" "}>{max_count}}'
                '[/link][/localhost]'
            )

            time_klass = 'result'
            if solve.final_time == self.best:
                time_klass = 'success'
            elif solve.final_time == self.worst:
                time_klass = 'warning'

            footer = ''
            if solve.flag:
                footer += format_flag(solve.flag)
                footer += ' '
            if solve.comment:
                footer += f"[comment]{ '*' if solve.comment else '' }[/comment]"

            console.print(
                header,
                f'[{ time_klass }]{ format_time(solve.time) }[/{ time_klass }]',
                f'[date]{ date }[/date]',
                f'[consign]{ solve.scramble }[/consign]',
                footer,
            )

    def detail(  # noqa: C901, PLR0912, PLR0913, PLR0914, PLR0915
            self,
            solve_id: int,
            method: str,
            orientation: CubeOrientation,
            *,
            disable_rotations: bool,
            show_highlights: bool,
            show_doctor: bool,
            show_cube: bool,
            show_reconstruction: bool,
            show_tps_graph: bool,
            show_time_graph: bool,
            show_fluency_graph: bool,
            show_recognition_graph: bool,
    ) -> None:
        """
        Display detailed analysis for a specific solve.

        Shows comprehensive metrics including timing, method analysis,
        recognition/execution breakdown, and optional visualizations.

        Args:
            solve_id: 1-based index of the solve to analyze.
            method: Solving method name for analysis (e.g., 'CFOP').
            orientation: Cube orientation string (e.g., 'UF').
            disable_rotations: Disable rotations for analysis.
            show_highlights: Whether to display highlights after analyse.
            show_doctor: Whether to display doctor diagnostics after analyse.
            show_cube: Whether to display scrambled cube state.
            show_reconstruction: Whether to show move sequence breakdown.
            show_tps_graph: Whether to display turns per second graph.
            show_time_graph: Whether to display timing breakdown graph.
            show_fluency_graph: Whether to display fluency graph.
            show_recognition_graph: Whether to display recognition timing
                graph.

        """
        try:
            solve = self.stack[solve_id - 1]
        except IndexError:
            console.print(
                f'Invalid solve #{ solve_id }',
                style='warning',
            )
            return

        solve.method_name = method
        solve.orientation = orientation
        solve.disable_rotations = disable_rotations

        date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        console.print(
            f'[title]Detail for { self.cube_name } #{ solve.solve_id }[/title]',
        )
        console.print(
            '[stats]Time       :[/stats] '
            f'[time]{ format_time(solve.time) }[/time]',
            format_flag(solve.flag),
        )
        console.print(
            '[stats]Date       :[/stats] '
            f'[date]{ date }[/date]',
        )
        console.print(
            '[stats]Session    :[/stats] '
            f'[session]{ solve.session.title() }[/session]',
        )
        if solve.device:
            console.print(
                '[stats]Cube       :[/stats] '
                f'[device]{ solve.device }[/device]',
            )
        if solve.timer:
            console.print(
                '[stats]Timer      :[/stats] '
                f'[timer]{ solve.timer }[/timer]',
            )

        if solve.analysable:
            solve_score = cast('float', solve.score)
            grade = format_grade(solve_score)
            grade_klass = grade.lower()
            grade_line = (
                f' [grade_{ grade_klass }]'
                f'{ grade:<2}'
                f'[/grade_{ grade_klass }]'
                f' { format_score(solve_score) }'
            )
            console.print(f'[stats]Grade      :[/stats]{ grade_line }')

            method_applied = cast('Analyser', solve.method_applied)
            method_score = method_applied.score
            grade = format_grade(method_score)
            grade_klass = grade.lower()
            grade_line = (
                f' [grade_{ grade_klass }]'
                f'{ grade:<2}'
                f'[/grade_{ grade_klass }]'
                f' { format_score(method_score) }'
            )
            console.print(
                f'[stats]Grade { solve.method_analyser.name:<5}:[/stats]'
                f'{ grade_line }',
            )

            recognition_time = format_time(
                solve.recognition_time,
                allow_dnf=False,
            )
            recog_klass = method_applied.normalize_value(
                'solve', 'recognition',
                solve.recognition_percent, 'recognition-p',
            )
            console.print(
                '[stats]Recognition:[/stats] '
                f'[result]{ recognition_time }[/result]'
                f' [{ recog_klass }]'
                f'{ solve.recognition_percent:.2f}%'
                f'[{ recog_klass }]',
            )

            execution_time = format_time(
                solve.execution_time,
                allow_dnf=False,
            )
            exec_klass = method_applied.normalize_value(
                'solve', 'execution',
                solve.execution_percent, 'execution-p',
            )
            console.print(
                '[stats]Execution  :[/stats] '
                f'[result]{ execution_time }[/result]'
                f' [{ exec_klass }]'
                f'{ solve.execution_percent:.2f}%'
                f'[{ exec_klass }]',
            )

            metrics_dict = solve.reconstruction.metrics._asdict()
            metric_string = '[stats]Metrics    :[/stats] '
            for metric in STATS_SOLVE_METRICS:
                value = metrics_dict[metric]
                metric_string += (
                    f'[{ metric }]{ value } { metric.upper() }[/{ metric }] '
                )
            metric_string += f'[tps]{ solve.tps:.2f} TPS[/tps] '

            console.print(metric_string)

            missed_string = '[stats]Overhead   :[/stats] '
            all_missed_moves = solve.all_missed_moves
            execution_missed_moves = solve.execution_missed_moves
            transition_missed_moves = solve.transition_missed_moves
            if all_missed_moves:
                missed_string += (
                    f'[warning]{ all_missed_moves } QTM[/warning]'
                )
                if execution_missed_moves:
                    missed_string += (
                        ' [exec-overhead]'
                        f'(+{ execution_missed_moves } execution)'
                        '[/exec-overhead]'
                    )
                if transition_missed_moves:
                    missed_string += (
                        ' [trans-overhead]'
                        f'(+{ transition_missed_moves } transition)'
                        '[/trans-overhead]'
                    )
            else:
                missed_string += '[success]Optimal execution[/success]'

            console.print(missed_string)

            fluency_string = '[stats]Fluency    :[/stats] '
            fluency = solve.fluency

            if fluency > 0:
                fluency_string += format_fluency(fluency)
            else:
                fluency_string += '[result]N/A[/result]'

            console.print(fluency_string)

            pauses_string = '[stats]Pauses     :[/stats] '
            if solve.execution_pauses:
                pauses_string += (
                    f'[caution]{ solve.execution_pauses }[/caution]'
                )
            else:
                pauses_string += '[success]None[/success]'

            console.print(pauses_string)

            if solve.rotations:
                rotations_string = '[stats]Rotations  :[/stats] '
                if solve.rotations > 3:
                    rotations_string += (
                        f'[warning]{ solve.rotations }[/warning]'
                    )
                else:
                    rotations_string += (
                        f'[caution]{ solve.rotations }[/caution]'
                    )

                console.print(rotations_string)

            aufs_string = '[stats]Adjusts UF :[/stats] '
            if solve.aufs > 5:
                aufs_string += (
                    f'[warning]{ solve.aufs }[/warning]'
                )
            elif solve.aufs > 2:
                aufs_string += (
                    f'[caution]{ solve.aufs }[/caution]'
                )
            elif solve.aufs:
                aufs_string += (
                    f'[success]{ solve.aufs }[/success]'
                )
            else:
                aufs_string += '[success]None[/success]'

            console.print(aufs_string)

        if solve.comment:
            console.print(
                '[stats]Comment    :[/stats] '
                f'[comment]{ solve.comment }[/comment]',
            )

        console.print(
            '[stats]Scramble   :[/stats] '
            f'[consign]{ solve.scramble }[/consign]',
        )
        if show_cube:
            cube = VCube(size=self.cube_size)
            cube.rotate(solve.scramble)

            print_cube_scrambled(
                cube, 'UF', solve.scramble,
            )

        if solve.advanced:
            if show_reconstruction:
                console.print(
                    '[title]Reconstruction '
                    f'{ solve.method_analyser.name }[/title]',
                    f'[localhost][link={ solve.link_term_timer }]'
                    'Term-Timer[/link][/localhost]',
                    f'[algcubing][link={ solve.link_alg_cubing }]'
                    'alg.cubing.net[/link][/algcubing]',
                    f'[cubedb][link={ solve.link_cube_db }]'
                    'cubedb.net[/link][/cubedb]',
                )
                console.print(solve.method_line, end='')
            if show_time_graph:
                solve.time_graph()
            if show_tps_graph:
                solve.tps_graph()
            if show_fluency_graph:
                solve.fluency_graph()
            if show_recognition_graph:
                solve.recognition_graph()
            if show_highlights:
                console.print(solve.highlights())
            if show_doctor:
                console.print(solve.diagnostics())

    @staticmethod
    def case_table(title: str, items: dict[str, CaseStats],
                   sorting: str, ordering: str) -> None:
        """
        Display a formatted table of case statistics.

        Creates a Rich table showing detailed statistics for algorithm
        cases (e.g., OLL, PLL) with timing, frequency, and performance
        metrics.

        Args:
            title: Case type name (e.g., 'OLL', 'PLL').
            items: Dictionary mapping case names to their statistics.
            sorting: Column name to sort by.
            ordering: Sort direction, either 'asc' or 'desc'.

        """
        table = Table(title=f'{ title }s', box=box.SIMPLE)
        table.add_column('Case', width=10)
        table.add_column('Σ', width=3)
        table.add_column('Freq.', width=5, justify='right')
        table.add_column('Prob.', width=5, justify='right')
        table.add_column('Reco.', width=5, justify='right')
        table.add_column('Exec.', width=5, justify='right')
        table.add_column('Time', width=5, justify='right')
        table.add_column('Ao5', width=5, justify='right')
        table.add_column('Ao12', width=5, justify='right')
        table.add_column('QTM', width=5, justify='right')
        table.add_column('TPS', width=5, justify='right')
        table.add_column('eTPS', width=5, justify='right')

        def sort_key(item: tuple[str, CaseStats]) -> tuple[int | float, str]:
            name, stats = item
            return (cast('int | float', stats[sorting]), name)  # type: ignore[literal-required]

        case_stats: CaseStats
        for name, case_stats in sorted(
                items.items(),
                key=sort_key,
                reverse=ordering == 'desc',
        ):
            case = case_stats['case']
            percent_klass = (
                case_stats['frequency'] > case.probability
                and 'green'
            ) or 'red'

            link = format_term_timer_case_url(case)
            head = (
                f'[localhost][link={ link }]{ case.name }'
                '[/link][/localhost]'
            )

            if 'SKIP' in name:
                head = '[skipped]SKIPPED[/skipped]'

            count = case_stats['count']

            ao5 = '[no-ao]N/A[/no-ao]'
            if case_stats['ao5'] > 0:
                ao5 = f'[ao5]{ format_duration(case_stats["ao5"]) }[/ao5]'

            ao12 = '[no-ao]N/A[/no-ao]'
            if case_stats['ao12'] > 0:
                ao12 = f'[ao12]{ format_duration(case_stats["ao12"]) }[/ao12]'

            table.add_row(
                head,
                f'[stats]{ count!s }[/stats]',
                f'[{ percent_klass }]'
                f'{ (case_stats["frequency"] * 100):.2f}%'
                f'[/{ percent_klass }]',
                '[percent]'
                f'{ (case.probability * 100):.2f}%'
                '[/percent]',
                '[recognition]' +
                format_duration(int(case_stats['recognition'])) +
                '[/recognition]',
                '[execution]' +
                format_duration(int(case_stats['execution'])) +
                '[/execution]',
                '[duration]' +
                format_duration(int(case_stats['time'])) +
                '[/duration]',
                ao5,
                ao12,
                f'[moves]{ case_stats["qtm"]:.2f}[/moves]',
                f'[tps]{ case_stats["tps"]:.2f}[/tps]',
                f'[tps-e]{ case_stats["etps"]:.2f}[/tps-e]',
            )
        console.print(table)

    def cfop(self, analyses: MethodAnalysis,
             *, oll_only: bool = False, pll_only: bool = False,
             sorting: str = 'count', ordering: str = 'asc') -> None:
        """
        Display CFOP method analysis with OLL/PLL case statistics.

        Shows detailed case-by-case statistics for the CFOP solving method,
        including overall grade and performance metrics.

        Args:
            analyses: Dictionary containing method analysis data.
            oll_only: Whether to show only OLL statistics.
            pll_only: Whether to show only PLL statistics.
            sorting: Column name to sort cases by.
            ordering: Sort direction, either 'asc' or 'desc'.

        """
        if sorting == 'case':
            sorting = 'label'

        resume = analyses['resume']
        if not pll_only and 'oll' in resume:
            self.case_table('OLL', resume['oll'], sorting, ordering)
        if not oll_only and 'pll' in resume:
            self.case_table('PLL', resume['pll'], sorting, ordering)

        mean = analyses['mean']
        grade = format_grade(mean)
        grade_klass = grade.lower()
        grade_line = (
                f' [grade_{ grade_klass }]'
                f'{ grade }'
                f'[/grade_{ grade_klass }]'
            )
        console.print(
            f'[title]Grade CFOP :[/title]{ grade_line } ({ mean:.2f})',
        )

    def graph(self) -> None:
        """
        Display a terminal-based graph of solve times and trends.

        Plots individual solve times along with the rolling averages
        configured in ``STATS_GRAPH_SERIES`` (capped to the first two
        entries) to visualize performance trends over the session.
        """
        series = STATS_GRAPH_SERIES[:GRAPH_CONSOLE_LIMIT]
        series_values: list[list[float | None]] = [[] for _ in series]
        times: list[int] = []
        plot_times: list[float | None] = []

        plt.clear_figure()

        for time in self.stack_time:
            # Keep raw milliseconds in times so ao() retains full
            # precision; only the plotted values are float seconds.
            times.append(time)
            # DNF times (0) stay in times to invalidate ao windows,
            # but are plotted as gaps
            plot_times.append(time / SECOND if time else None)

            for index, (kind, size) in enumerate(series):
                value = getattr(self, kind)(size, times)
                series_values[index].append(
                    value / SECOND if value > 0 else None,
                )

        plt.plot(
            plot_times,
            marker='braille',
            label='Time',
            color=45,
        )

        for (kind, size), values in zip(series, series_values, strict=True):
            if any(values):
                token = f'{ kind }{ size }'
                plt.plot(
                    values,
                    marker='braille',
                    label=token.upper(),
                    color=GRAPH_CONSOLE_COLORS.get(
                        token, GRAPH_CONSOLE_FALLBACK,
                    ),
                )

        plt.title(f'Tendencies { self.cube_name }')
        plt.plot_size(height=25)

        n = len(times)
        step = max(1, n // 10)
        xticks = list(range(step, n + 1, step))
        if n not in xticks:
            xticks.append(n)
        plt.xticks(xticks)

        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))
        plt.ticks_style('bold')

        plt.show()


class DailySummaryReporter:
    """
    Formats and displays the participation summary of daily sessions.

    Daily solves are grouped by the day of their session instead of being
    pooled together: a daily session replays a single scramble all day
    long, so solve based averages spanning several days carry no meaning.
    The reporter exposes attendance, streaks and a per day breakdown.
    """

    def __init__(self, cube_size: int, stack: list[Solve],
                 today: date | None = None) -> None:
        """
        Initialize the daily summary reporter.

        Args:
            cube_size: Dimension of the cube (e.g., 3 for 3x3x3).
            stack: List of Solve objects from every daily session.
            today: Reference day used for the participation span and the
                current streak, defaulting to the current date.

        """
        self.cube_size = cube_size
        self.cube_name = f'{ cube_size }x{ cube_size }x{ cube_size }'

        self.stack = stack
        self.today = today or date.today()  # noqa: DTZ011

    @cached_property
    def days(self) -> dict[date, Statistics]:
        """
        Group solve times by the day of their daily session.

        Sessions not named after a date are skipped: a daily session file
        is always named after the day it belongs to. Days made only of DNF
        solves are skipped too, the daily never having been solved.

        Returns:
            Mapping of session date to its Statistics, oldest first.

        """
        grouped: dict[date, list[int]] = {}

        for solve in self.stack:
            try:
                day = date.fromisoformat(solve.session)
            except ValueError:
                continue

            grouped.setdefault(day, []).append(solve.final_time)

        days = {
            day: Statistics(times)
            for day, times in sorted(grouped.items())
        }

        return {day: stats for day, stats in days.items() if stats.best}

    @cached_property
    def played_days(self) -> list[date]:
        """
        List the days holding at least one daily solve.

        Returns:
            Sorted list of played dates, oldest first.

        """
        return list(self.days)

    @cached_property
    def span(self) -> int:
        """
        Count the days elapsed since the first daily, today included.

        Returns:
            Number of days in the participation window, 0 without solves.

        """
        if not self.played_days:
            return 0

        return (self.today - self.played_days[0]).days + 1

    @cached_property
    def participation(self) -> float:
        """
        Calculate the ratio of played days over the whole span.

        Returns:
            Proportion of played days (0.0 to 1.0).

        """
        if not self.span:
            return 0.0

        return len(self.played_days) / self.span

    @cached_property
    def total_solves(self) -> int:
        """
        Count the solves held by the played days.

        The stack is not measured directly: it also carries the solves of
        the sessions dropped by days, which no other figure counts.

        Returns:
            Number of solves, retries and DNF included.

        """
        return sum(stats.total for stats in self.days.values())

    @cached_property
    def solves_per_day(self) -> float:
        """
        Calculate the mean number of solves on a played day.

        Returns:
            Mean count of solves per played day.

        """
        if not self.played_days:
            return 0.0

        return self.total_solves / len(self.played_days)

    @cached_property
    def streaks(self) -> list[list[date]]:
        """
        Split the played days into blocks of consecutive days.

        Returns:
            List of streaks, in chronological order.

        """
        blocks: list[list[date]] = []

        for day in self.played_days:
            if blocks and (day - blocks[-1][-1]).days == 1:
                blocks[-1].append(day)
            else:
                blocks.append([day])

        return blocks

    @cached_property
    def longest_streak(self) -> list[date]:
        """
        Return the longest block of consecutive played days.

        The most recent block wins a tie, being the more motivating one.

        Returns:
            Days of the longest streak, empty without solves.

        """
        longest: list[date] = []

        for streak in self.streaks:
            if len(streak) >= len(longest):
                longest = streak

        return longest

    @cached_property
    def current_streak(self) -> list[date]:
        """
        Return the ongoing block of consecutive played days.

        A streak stays alive while its last day is today or yesterday, so
        that it does not collapse before the daily of the day is played.

        Returns:
            Days of the current streak, empty when it is broken.

        """
        if not self.streaks:
            return []

        last = self.streaks[-1]
        if (self.today - last[-1]).days <= 1:
            return last

        return []

    @cached_property
    def days_since_last(self) -> int:
        """
        Count the days elapsed since the last played daily.

        Returns:
            Number of days, 0 when the daily of the day is played.

        """
        if not self.played_days:
            return 0

        return (self.today - self.played_days[-1]).days

    @cached_property
    def best_day(self) -> tuple[date, int] | None:
        """
        Return the day of the fastest daily solve.

        Returns:
            Date and time of the fastest solve, None without played day.

        """
        if not self.played_days:
            return None

        day = min(self.played_days, key=lambda d: self.days[d].best)

        return (day, self.days[day].best)

    @cached_property
    def worst_day(self) -> tuple[date, int] | None:
        """
        Return the day of the slowest daily solve.

        Returns:
            Date and time of the slowest solve, None without played day.

        """
        if not self.played_days:
            return None

        day = max(self.played_days, key=lambda d: self.days[d].worst)

        return (day, self.days[day].worst)

    def punchcard_level(self, day: date) -> int:
        """
        Rank a played day on its number of attempts.

        Levels are absolute thresholds, not a distribution of the history:
        a day keeps its color whatever the other days hold.

        Args:
            day: Played day to rank.

        Returns:
            Index in PUNCHCARD_STYLES, 0 being the fewest attempts.

        """
        total = self.days[day].total

        return max(
            index
            for index, floor in enumerate(PUNCHCARD_LEVELS)
            if total >= floor
        )

    def resume(self, prefix: str = '', style: str = 'stats') -> None:
        """
        Display attendance and streak statistics to the console.

        Args:
            prefix: String to prepend to each line for indentation.
            style: Rich console style name for formatting labels.

        """
        if not self.played_days:
            return

        console.print(
            f'[title]Daily summary for { self.cube_name }[/title]',
        )
        console.print(
            f'[{ style }]{ prefix }Days  :[/{ style }]',
            f'[result]{ len(self.played_days) }[/result]',
            f'[{ style }]played[/{ style }]',
            f'[result]{ self.total_solves }[/result]',
            f'[{ style }]solves[/{ style }]',
            f'[result]{ self.solves_per_day:.2f}[/result]',
            f'[{ style }]per day[/{ style }]',
        )
        console.print(
            f'[{ style }]{ prefix }Since :[/{ style }]',
            f'[date]{ self.played_days[0] }[/date]',
            f'[result]{ self.span }[/result]',
            f'[{ style }]days[/{ style }]',
            f'[percent]{ (self.participation * 100):05.2f}%[/percent]',
        )
        console.print(
            f'[{ style }]{ prefix }Streak:[/{ style }]',
            f'[result]{ len(self.current_streak) }[/result]',
            f'[{ style }]current[/{ style }]',
            f'[green]{ len(self.longest_streak) }[/green]',
            f'[{ style }]best[/{ style }]',
            f'[date]{ self.longest_streak[0] }[/date]',
            f'[{ style }]→[/{ style }]',
            f'[date]{ self.longest_streak[-1] }[/date]',
        )
        console.print(
            f'[{ style }]{ prefix }Last  :[/{ style }]',
            f'[date]{ self.played_days[-1] }[/date]',
            f'[result]{ self.days_since_last }[/result]',
            f'[{ style }]days ago[/{ style }]',
        )

        if self.best_day and self.worst_day:
            best_day, best_time = self.best_day
            worst_day, worst_time = self.worst_day
            console.print(
                f'[{ style }]{ prefix }Best  :[/{ style }]',
                f'[green]{ format_time(best_time) }[/green]',
                f'[date]{ best_day }[/date]',
            )
            console.print(
                f'[{ style }]{ prefix }Worst :[/{ style }]',
                f'[red]{ format_time(worst_time) }[/red]',
                f'[date]{ worst_day }[/date]',
            )

    def punchcard_cell(self, day: date) -> str:
        """
        Render a single punchcard cell for a day.

        Args:
            day: Day to render.

        Returns:
            Rich markup of the cell, blanks outside of the window.

        """
        width = len(PUNCHCARD_CELL)

        if not self.played_days[0] <= day <= self.today:
            return ' ' * width

        if day not in self.days:
            return f'[no-ao]{ "·" * width }[/no-ao]'

        cell_style = PUNCHCARD_STYLES[self.punchcard_level(day)]

        return f'[{ cell_style }]{ PUNCHCARD_CELL }[/{ cell_style }]'

    @staticmethod
    def punchcard_legend() -> list[str]:
        """
        Build the attempt range described by each punchcard color level.

        Returns:
            Labels like '1', '2-3' and '6+', one per level.

        """
        labels = []

        for index, floor in enumerate(PUNCHCARD_LEVELS):
            if index + 1 == len(PUNCHCARD_LEVELS):
                labels.append(f'{ floor }+')
            elif PUNCHCARD_LEVELS[index + 1] - floor == 1:
                labels.append(str(floor))
            else:
                labels.append(f'{ floor }-{ PUNCHCARD_LEVELS[index + 1] - 1 }')

        return labels

    @staticmethod
    def punchcard_header(weeks: list[date]) -> str:
        """
        Render the month header of the punchcard.

        Args:
            weeks: First day of each displayed week.

        Returns:
            Header string marking the initial of each starting month.

        """
        header = ''
        month = 0

        for week in weeks:
            initial = (
                week.month != month and MONTH_INITIALS[week.month - 1]
            ) or ' '
            header += initial.ljust(len(PUNCHCARD_CELL))
            month = week.month

        return header

    def punchcard(self, weeks_limit: int = PUNCHCARD_WEEKS) -> None:
        """
        Display a participation punchcard, one column per week.

        Args:
            weeks_limit: Maximum number of weeks displayed, the most
                recent ones being kept.

        """
        if not self.played_days:
            return

        first = self.played_days[0]
        cursor = first - timedelta(days=first.weekday())

        weeks = []
        while cursor <= self.today:
            weeks.append(cursor)
            cursor += timedelta(days=7)

        weeks = weeks[-weeks_limit:]

        console.print(f'[title]Punchcard for { self.cube_name }[/title]')
        console.print('   ', f'[stats]{ self.punchcard_header(weeks) }[/stats]')

        for index, label in enumerate(WEEK_DAYS):
            cells = ''.join(
                self.punchcard_cell(week + timedelta(days=index))
                for week in weeks
            )
            console.print(f'[stats]{ label }[/stats]', cells)

        console.print(
            *(
                f'[{ style }]{ PUNCHCARD_CELL }[/{ style }]'
                f' [stats]{ label }[/stats]'
                for style, label in zip(
                    PUNCHCARD_STYLES,
                    self.punchcard_legend(),
                    strict=True,
                )
            ),
            f'[no-ao]{ "·" * len(PUNCHCARD_CELL) }[/no-ao]'
            ' [stats]missed[/stats]',
        )

    def days_table(self, limit: int = DAILY_DAYS_LISTED) -> None:
        """
        Display a table of the most recent played days.

        Args:
            limit: Maximum number of played days displayed.

        """
        if not self.days:
            return

        table = Table(title='Daily days', box=box.SIMPLE)
        table.add_column('Date', width=10)
        table.add_column('Day', width=3)
        table.add_column('Σ', width=3, justify='right')
        table.add_column('Best', width=9, justify='right')
        table.add_column('Mean', width=9, justify='right')

        for day, stats in list(self.days.items())[-limit:]:
            table.add_row(
                f'[date]{ day }[/date]',
                f'[session]{ WEEK_DAYS[day.weekday()] }[/session]',
                f'[stats]{ stats.total }[/stats]',
                f'[green]{ format_time(stats.best) }[/green]',
                f'[result]{ format_time(stats.mean) }[/result]',
            )

        console.print(table)


class DrillStatistics(Statistics):
    """Computes and displays statistics for a drill session."""

    def __init__(
            self,
            rep_times: list[int],
            rep_tps: list[float],
            rep_fluencies: list[int],
            qtm: int = 0,
    ) -> None:
        """Initialize drill statistics from per-rep collected data."""
        super().__init__(rep_times)
        self.rep_tps = rep_tps
        self.rep_fluencies = [f for f in rep_fluencies if f > 0]
        self.qtm = qtm

    @cached_property
    def total_moves(self) -> int:
        """Return total moves performed across all reps."""
        return self.qtm * self.total

    @cached_property
    def best_tps(self) -> float:
        """Return the best (highest) TPS across all reps."""
        return max(self.rep_tps) if self.rep_tps else 0.0

    @cached_property
    def worst_tps(self) -> float:
        """Return the worst (lowest) TPS across all reps."""
        return min(self.rep_tps) if self.rep_tps else 0.0

    @cached_property
    def mean_tps(self) -> float:
        """Return the mean TPS across all reps."""
        return float(np.mean(self.rep_tps)) if self.rep_tps else 0.0

    @cached_property
    def best_fluency(self) -> int:
        """Return the best (highest) fluency across all reps."""
        return max(self.rep_fluencies) if self.rep_fluencies else 0

    @cached_property
    def worst_fluency(self) -> int:
        """Return the worst (lowest) fluency across all reps."""
        return min(self.rep_fluencies) if self.rep_fluencies else 0

    @cached_property
    def mean_fluency(self) -> int:
        """Return the mean fluency across all reps."""
        return int(np.mean(self.rep_fluencies)) if self.rep_fluencies else 0

    def time_graph(self) -> None:
        """Display a terminal line graph of rep times."""
        plt.clear_figure()
        times = [t / SECOND for t in self.stack_time]
        plt.plot(times, marker='braille', label='Time', color=45)
        plt.hline(self.mean / SECOND, 'red')
        plt.xticks(list(range(1, len(times) + 1)))
        plt.title('Rep Times (seconds)')
        plt.plot_size(height=15)
        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))
        plt.ticks_style('bold')
        plt.show()

    def tps_graph(self) -> None:
        """Display a terminal line graph of TPS per rep."""
        plt.clear_figure()
        plt.plot(self.rep_tps, marker='braille', label='TPS', color=119)
        plt.hline(self.mean_tps, 'red')
        plt.xticks(list(range(1, len(self.rep_tps) + 1)))
        plt.title('Turns Per Second')
        plt.plot_size(height=15)
        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))
        plt.ticks_style('bold')
        plt.show()

    def resume(self) -> None:
        """Display drill session statistics summary."""
        has_fluency = bool(self.mean_fluency)

        console.print('[title]Drill summary[/title]')
        console.print(
            '[stats]Reps  :[/stats]',
            f'[result]{ self.total }[/result]',
        )
        if self.total_moves:
            console.print(
                '[stats]Moves :[/stats]',
                f'[result]{ self.total_moves }[/result]',
            )
        console.print(
            '[stats]Time  :[/stats]',
            f'[result]{ format_time(self.total_time) }[/result]',
        )
        console.print(
            '[stats]Mean  :[/stats]',
            f'[result]{ format_time(self.mean) }[/result]',
            f'[tps]{ self.mean_tps:05.2f} TPS[/tps]',
            f'{ format_fluency(self.mean_fluency) if has_fluency else "" }',
        )
        console.print(
            '[stats]Best  :[/stats]',
            f'[green]{ format_time(self.best) }[/green]',
            f'[tps]{ self.best_tps:05.2f} TPS[/tps]',
            f'{ format_fluency(self.best_fluency) if has_fluency else "" }',
        )
        console.print(
            '[stats]Worst :[/stats]',
            f'[red]{ format_time(self.worst) }[/red]',
            f'[tps]{ self.worst_tps:05.2f} TPS[/tps]',
            f'{ format_fluency(self.worst_fluency) if has_fluency else "" }',
        )
        self.time_graph()
        self.tps_graph()


class TrainerStatistics:
    """Computes and displays statistics for a training session."""

    def __init__(
            self,
            session_data: list[tuple[str, Case, int]],
            cases: 'dict[str, CaseTraining] | None' = None,
    ) -> None:
        """
        Initialize trainer statistics from per-training collected data.

        Args:
            session_data: Per-training tuples of case code, case and
                elapsed time.
            cases: Training data of every case, holding the FSRS cards
                as they stand at the end of the session.

        """
        self.session_data = session_data
        self.cases = cases or {}

    def resume(self) -> None:
        """Display training session statistics summary."""
        if not self.session_data:
            return

        all_times = [elapsed for _, _, elapsed in self.session_data]
        global_stats = Statistics(all_times)

        console.print('[title]Training summary[/title]')
        console.print(
            '[stats]Count :[/stats]',
            f'[result]{ global_stats.total }[/result]',
        )
        console.print(
            '[stats]Time  :[/stats]',
            f'[result]{ format_time(global_stats.total_time) }[/result]',
        )
        console.print(
            '[stats]Mean  :[/stats]',
            f'[result]{ format_time(global_stats.mean) }[/result]',
        )
        console.print(
            '[stats]Best  :[/stats]',
            f'[green]{ format_time(global_stats.best) }[/green]',
        )
        console.print(
            '[stats]Worst :[/stats]',
            f'[red]{ format_time(global_stats.worst) }[/red]',
        )

        case_groups: dict[str, tuple[Case, list[int]]] = {}
        for code, case, elapsed in self.session_data:
            if code not in case_groups:
                case_groups[code] = (case, [])
            case_groups[code][1].append(elapsed)

        if len(case_groups) < 2:
            return

        table = Table(box=box.SIMPLE)
        table.add_column('Case', width=40)
        table.add_column('Σ', width=3, justify='right')
        table.add_column('Mean', width=5, justify='right')
        table.add_column('Best', width=5, justify='right')
        table.add_column('State', width=8, justify='right')
        table.add_column('Due', width=10, justify='right')

        for code, (case, times) in sorted(case_groups.items()):
            link = format_term_timer_case_url(case)
            if link:
                head = (
                    f'[localhost][link={ link }]{ case.pretty_name }'
                    '[/link][/localhost]'
                )
            else:
                head = case.pretty_name
            stats = Statistics(times)
            case_training = self.cases.get(code)
            card = case_training.fsrs_card if case_training else None
            table.add_row(
                head,
                f'[stats]{ stats.total }[/stats]',
                f'[result]{ format_duration(stats.mean) }[/result]',
                f'[green]{ format_duration(stats.best) }[/green]',
                format_fsrs_state(card),
                format_fsrs_due(card),
            )

        console.print(table)
