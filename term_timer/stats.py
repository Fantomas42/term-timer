"""Statistics calculation and display for solve sessions."""
from functools import cached_property
from typing import TYPE_CHECKING
from typing import cast

import numpy as np
import plotext as plt
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases.case import Case
from cubing_algs.vcube import VCube
from rich import box
from rich.table import Table

from term_timer.annotations import CaseStats
from term_timer.annotations import ListingFilters
from term_timer.annotations import MethodAnalysis
from term_timer.config import STATS_CONFIG
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.constants import SECOND_BINS
from term_timer.constants import STEP_BAR
from term_timer.formatter import compute_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_duration
from term_timer.formatter import format_edge
from term_timer.formatter import format_flag
from term_timer.formatter import format_fluency
from term_timer.formatter import format_grade
from term_timer.formatter import format_score
from term_timer.formatter import format_term_timer_case_url
from term_timer.formatter import format_time
from term_timer.interface.console import console
from term_timer.printer import print_cube_scrambled
from term_timer.solve import Solve

if TYPE_CHECKING:
    from term_timer.methods.base import Analyser


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

        Args:
            limit: Number of most recent times to include.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Mean time in milliseconds, or -1 if insufficient data.

        """
        if limit > len(stack_elapsed):
            return -1

        return int(np.mean(stack_elapsed[-limit:]))

    @staticmethod
    def ao(limit: int, stack_elapsed: list[int]) -> int:
        """
        Calculate the average of N (aoN) excluding best/worst times.

        Removes the top and bottom 5% of times before averaging, following
        WCA (World Cube Association) competition rules.

        Args:
            limit: Number of most recent times to include.
            stack_elapsed: List of times in milliseconds.

        Returns:
            Average time in milliseconds, or -1 if insufficient data.

        """
        if limit > len(stack_elapsed):
            return -1

        cap = int(np.ceil(limit * 5 / 100))

        last_of = stack_elapsed[-limit:]
        for _ in range(cap):
            last_of.remove(min(last_of))
            last_of.remove(max(last_of))

        return int(np.mean(last_of))

    def best_mo(self, limit: int) -> int:
        """
        Find the best mean of N across all rolling windows.

        Iterates through all possible consecutive time windows to find
        the minimum mean time.

        Args:
            limit: Window size for calculating mean.

        Returns:
            Best mean time in milliseconds, or 0 if no valid windows.

        """
        mos: list[int] = []
        stack = list(self.stack_time[:-1])

        current_mo = getattr(self, f'mo{ limit }')
        if current_mo:
            mos.append(current_mo)

        while 42:
            mo = self.mo(limit, stack)
            if mo == -1:
                break
            if mo:
                mos.append(mo)
            stack.pop()

        if mos:
            return min(mos)

        return 0

    def best_ao(self, limit: int) -> int:
        """
        Find the best average of N across all rolling windows.

        Iterates through all possible consecutive time windows to find
        the minimum average time.

        Args:
            limit: Window size for calculating average.

        Returns:
            Best average time in milliseconds, or 0 if no valid windows.

        """
        aos: list[int] = []
        stack = list(self.stack_time[:-1])

        current_ao = getattr(self, f'ao{ limit }')
        if current_ao:
            aos.append(current_ao)

        while 42:
            ao = self.ao(limit, stack)
            if ao == -1:
                break
            if ao:
                aos.append(ao)
            stack.pop()

        if aos:
            return min(aos)

        return 0


class Statistics(StatisticsTools):  # noqa: PLR0904
    """
    Computes comprehensive statistics for timed sessions.

    Extends StatisticsTools with cached properties for commonly used
    statistics like best/worst times, averages, and distribution analysis.
    """

    @cached_property
    def bpa(self) -> int:
        """
        Calculate best of 3 average (mean of 3 fastest times).

        Returns:
            Average of 3 best times in milliseconds, or 0 if insufficient.

        """
        if self.stack_time_sorted:
            return int(np.mean(self.stack_time_sorted[:3]))
        return 0

    @cached_property
    def wpa(self) -> int:
        """
        Calculate worst of 3 average (mean of 3 slowest times).

        Returns:
            Average of 3 worst times in milliseconds, or 0 if insufficient.

        """
        if self.stack_time_sorted:
            return int(np.mean(self.stack_time_sorted[-3:]))
        return 0

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
        Calculate mean time across all times.

        Returns:
            Mean time in milliseconds.

        """
        return int(np.mean(self.stack_time))

    @cached_property
    def median(self) -> int:
        """
        Calculate median time across all times.

        Returns:
            Median time in milliseconds.

        """
        return int(np.median(self.stack_time))

    @cached_property
    def stdev(self) -> int:
        """
        Calculate standard deviation of times.

        Returns:
            Standard deviation in milliseconds.

        """
        return int(np.std(self.stack_time))

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

        best_bin = STATS_CONFIG.get('distribution', 0)
        if not best_bin:
            for second in SECOND_BINS:
                if gap / 10 < second:
                    best_bin = second
                    break

        values = [st / SECOND for st in self.stack_time_sorted]
        if not values:
            return []

        min_val = int((np.min(values) // best_bin) * best_bin)
        max_val = int(((np.max(values) // best_bin) + 1) * best_bin)

        bins = np.arange(
            int(min_val),
            int(max_val + best_bin),
            best_bin,
        )

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
        Calculate average score across all advanced solves.

        Returns:
            Mean score value across all solves with method analysis.

        """
        return sum(
            cast('float', s.score) for s in self.stack if s.advanced
        ) / self.total

    def resume(self, prefix: str = '', style: str = 'stats', *,  # noqa: C901
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

        console.print(
            f'[{ style }]{ prefix }Total :[/{ style }]',
            f'[result]{ self.total }[/result]',
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
                    f'[{ style }]BPA  :[/{ style }]',
                    f'[result]{ format_time(self.bpa) }[/result]',
                    format_delta(self.bpa - self.best),
                )
                console.print(
                    f'[{ style }]{ prefix }Worst :[/{ style }]',
                    f'[red]{ format_time(self.worst) }[/red]',
                    f'[{ style }]WPA  :[/{ style }]',
                    f'[result]{ format_time(self.wpa) }[/result]',
                    format_delta(self.wpa - self.worst),
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
        if self.total >= 3:
            console.print(
                f'[{ style }]{ prefix }Mo3   :[/{ style }]',
                f'[mo3]{ format_time(self.mo3) }[/mo3]',
                f'[{ style }]Best :[/{ style }]',
                f'[result]{ format_time(self.best_mo3) }[/result]',
                format_delta(self.mo3 - self.best_mo3),
            )
        if self.total >= 5:
            console.print(
                f'[{ style }]{ prefix }Ao5   :[/{ style }]',
                f'[ao5]{ format_time(self.ao5) }[/ao5]',
                f'[{ style }]Best :[/{ style }]',
                f'[result]{ format_time(self.best_ao5) }[/result]',
                format_delta(self.ao5 - self.best_ao5),
            )
        if self.total >= 12:
            console.print(
                f'[{ style }]{ prefix }Ao12  :[/{ style }]',
                f'[ao12]{ format_time(self.ao12) }[/ao12]',
                f'[{ style }]Best :[/{ style }]',
                f'[result]{ format_time(self.best_ao12) }[/result]',
                format_delta(self.ao12 - self.best_ao12),
            )
        if self.total >= 100:
            console.print(
                f'[{ style }]{ prefix }Ao100 :[/{ style }]',
                f'[ao100]{ format_time(self.ao100) }[/ao100]',
                f'[{ style }]Best :[/{ style }]',
                f'[result]{ format_time(self.best_ao100) }[/result]',
                format_delta(self.ao100 - self.best_ao100),
            )
        if self.total >= 1000:
            console.print(
                f'[{ style }]{ prefix }Ao1000:[/{ style }]',
                f'[ao1000]{ format_time(self.ao1000) }[/ao1000]',
                f'[{ style }]Best :[/{ style }]',
                f'[result]{ format_time(self.best_ao1000) }[/result]',
                format_delta(self.ao1000 - self.best_ao1000),
            )

        if self.total > 1:
            max_count = compute_padding(
                max(c for c, e in self.repartition),
            )

            max_edge = max(e for c, e in self.repartition)
            total_percent = 0.0
            for count, edge in self.repartition:
                percent = (count / self.total)
                total_percent += percent

                start = f'[{ style }]{ count!s:{" "}>{max_count}} '
                start += f'([edge]{ format_edge(edge, max_edge) }[/edge])'
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
            filtered_solves.sort(key=lambda x: x[1].time)

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
            if solve.time == self.best:
                time_klass = 'success'
            elif solve.time == self.worst:
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

        if solve.advanced:
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
            for metric in STATS_CONFIG.get('metrics', []):
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

        Plots individual solve times along with rolling ao5 and ao12
        averages to visualize performance trends over the session.
        """
        ao5s = []
        ao12s = []
        times = []

        plt.clear_figure()

        for time in self.stack_time:
            seconds = time // SECOND
            times.append(seconds)

            ao5 = self.ao(5, times)
            ao12 = self.ao(12, times)
            ao5s.append((ao5 > 0 and ao5) or None)
            ao12s.append((ao12 > 0 and ao12) or None)

        plt.plot(
            times,
            marker='fhd',
            label='Time',
        )

        if any(ao5s):
            plt.plot(
                ao5s,
                marker='fhd',
                label='AO5',
                color='red',
            )

        if any(ao12s):
            plt.plot(
                ao12s,
                marker='fhd',
                label='AO12',
                color='blue',
            )

        plt.title(f'Tendencies { self.cube_name }')
        plt.plot_size(height=25)

        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))
        plt.ticks_style('bold')

        plt.show()


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
        plt.plot(times, marker='fhd', label='Time')
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
        plt.plot(self.rep_tps, marker='fhd', label='TPS', color=119)
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
    ) -> None:
        """Initialize trainer statistics from per-training collected data."""
        self.session_data = session_data

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

        for _, (case, times) in sorted(case_groups.items()):
            link = format_term_timer_case_url(case)
            if link:
                head = (
                    f'[localhost][link={ link }]{ case.pretty_name }'
                    '[/link][/localhost]'
                )
            else:
                head = case.pretty_name
            stats = Statistics(times)
            table.add_row(
                head,
                f'[stats]{ stats.total }[/stats]',
                f'[result]{ format_duration(stats.mean) }[/result]',
                f'[green]{ format_duration(stats.best) }[/green]',
            )

        console.print(table)
