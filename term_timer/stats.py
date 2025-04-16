from functools import cached_property

import numpy as np
import plotext as plt

from term_timer.config import STATS_CONFIG
from term_timer.console import console
from term_timer.constants import SECOND
from term_timer.constants import SECOND_BINS
from term_timer.constants import STEP_BAR
from term_timer.formatter import computing_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_edge
from term_timer.formatter import format_time
from term_timer.magic_cube import Cube
from term_timer.solve import Solve


class StatisticsTools:
    def __init__(self, stack: list[Solve]):
        self.stack = stack
        self.stack_time = [
            s.final_time for s in stack
        ]
        self.stack_time_sorted = sorted(self.stack_time)

    @staticmethod
    def mo(limit: int, stack_elapsed: list[int]) -> int:
        if limit > len(stack_elapsed):
            return -1

        return int(np.mean(stack_elapsed[-limit:]))

    @staticmethod
    def ao(limit: int, stack_elapsed: list[int]) -> int:
        if limit > len(stack_elapsed):
            return -1

        cap = int(np.ceil(limit * 5 / 100))

        last_of = stack_elapsed[-limit:]
        for _ in range(cap):
            last_of.remove(min(last_of))
            last_of.remove(max(last_of))

        return int(np.mean(last_of))

    def best_mo(self, limit: int) -> int:
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

        return min(mos)

    def best_ao(self, limit: int) -> int:
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

        return min(aos)


class Statistics(StatisticsTools):

    @cached_property
    def bpa(self) -> int:
        return int(np.mean(self.stack_time_sorted[:3]))

    @cached_property
    def wpa(self) -> int:
        return int(np.mean(self.stack_time_sorted[-3:]))

    @cached_property
    def mo3(self) -> int:
        return self.mo(3, self.stack_time)

    @cached_property
    def ao5(self) -> int:
        return self.ao(5, self.stack_time)

    @cached_property
    def ao12(self) -> int:
        return self.ao(12, self.stack_time)

    @cached_property
    def ao100(self) -> int:
        return self.ao(100, self.stack_time)

    @cached_property
    def best_mo3(self) -> int:
        return self.best_mo(3)

    @cached_property
    def best_ao5(self) -> int:
        return self.best_ao(5)

    @cached_property
    def best_ao12(self) -> int:
        return self.best_ao(12)

    @cached_property
    def best_ao100(self) -> int:
        return self.best_ao(100)

    @cached_property
    def best(self) -> int:
        return self.stack_time_sorted[0]

    @cached_property
    def worst(self) -> int:
        return self.stack_time_sorted[-1]

    @cached_property
    def mean(self) -> int:
        return int(np.mean(self.stack_time))

    @cached_property
    def median(self) -> int:
        return int(np.median(self.stack_time))

    @cached_property
    def stdev(self) -> int:
        return int(np.std(self.stack_time))

    @cached_property
    def delta(self) -> int:
        return (
            self.stack[-1].time
            - self.stack[-2].time
        )

    @cached_property
    def total(self) -> int:
        return len(self.stack)

    @cached_property
    def total_time(self) -> int:
        return sum(self.stack_time)

    @cached_property
    def repartition(self) -> list[tuple[int, int]]:
        gap = (self.worst - self.best) / SECOND

        best_bin = STATS_CONFIG.get('distribution')
        if not best_bin:
            for second in SECOND_BINS:
                if gap / 10 < second:
                    best_bin = second
                    break

        values = [st / SECOND for st in self.stack_time]

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


class StatisticsReporter(Statistics):

    def __init__(self, cube_size: int, stack: list[Solve]):
        self.cube_size = cube_size
        self.cube_name = f'{ cube_size }x{ cube_size }x{ cube_size }'

        super().__init__(stack)

    def resume(self, prefix: str = '', *, show_title: bool = False) -> None:
        if show_title:
            console.print(
                f'[title]Statistics for { self.cube_name }[/title]',
            )

        console.print(
            f'[stats]{ prefix }Total :[/stats]',
            f'[result]{ self.total }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Time  :[/stats]',
            f'[result]{ format_time(self.total_time) }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Mean  :[/stats]',
            f'[result]{ format_time(self.mean) }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Median:[/stats]',
            f'[result]{ format_time(self.median) }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Stdev :[/stats]',
            f'[result]{ format_time(self.stdev) }[/result]',
        )
        if self.total >= 2:
            if self.total >= 3:
                console.print(
                    f'[stats]{ prefix }Best  :[/stats]',
                    f'[green]{ format_time(self.best) }[/green]',
                    '[stats]BPA  :[/stats]',
                    f'[result]{ format_time(self.bpa) }[/result]',
                    format_delta(self.bpa - self.best),
                )
                console.print(
                    f'[stats]{ prefix }Worst :[/stats]',
                    f'[red]{ format_time(self.worst) }[/red]',
                    '[stats]WPA  :[/stats]',
                    f'[result]{ format_time(self.wpa) }[/result]',
                    format_delta(self.wpa - self.worst),
                )
            else:
                console.print(
                    f'[stats]{ prefix }Best  :[/stats]',
                    f'[green]{ format_time(self.best) }[/green]',
                )
                console.print(
                    f'[stats]{ prefix }Worst :[/stats]',
                    f'[red]{ format_time(self.worst) }[/red]',
                )
        if self.total >= 3:
            console.print(
                f'[stats]{ prefix }Mo3   :[/stats]',
                f'[mo3]{ format_time(self.mo3) }[/mo3]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_mo3) }[/result]',
                format_delta(self.mo3 - self.best_mo3),
            )
        if self.total >= 5:
            console.print(
                f'[stats]{ prefix }Ao5   :[/stats]',
                f'[ao5]{ format_time(self.ao5) }[/ao5]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_ao5) }[/result]',
                format_delta(self.ao5 - self.best_ao5),
            )
        if self.total >= 12:
            console.print(
                f'[stats]{ prefix }Ao12  :[/stats]',
                f'[ao12]{ format_time(self.ao12) }[/ao12]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_ao12) }[/result]',
                format_delta(self.ao12 - self.best_ao12),
            )
        if self.total >= 100:
            console.print(
                f'[stats]{ prefix }Ao100 :[/stats]',
                f'[ao100]{ format_time(self.ao100) }[/ao100]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_ao100) }[/result]',
                format_delta(self.ao100 - self.best_ao100),
            )

        if self.total > 1:
            max_count = computing_padding(
                max(c for c, e in self.repartition),
            )
            max_edge = max(e for c, e in self.repartition)
            total_percent = 0.0
            for count, edge in self.repartition:
                percent = (count / self.total)
                total_percent += percent

                start = f'[stats]{ count!s:{" "}>{max_count}} '
                start += f'([edge]+{ format_edge(edge, max_edge) }[/edge])'
                start = start.ljust(26 + len(prefix))

                console.print(
                    f'{ start }:[/stats]',
                    f'[bar]{ round(percent * STEP_BAR) * " " }[/bar]'
                    f'{ (STEP_BAR - round(percent * STEP_BAR)) * " " }'
                    f'[result]{ percent * 100:05.2f}%[/result]   ',
                    f'[percent]{ total_percent * 100:05.2f}%[/percent]',
                )

    def listing(self, limit: int) -> None:
        console.print(
            f'[title]Listing for { self.cube_name }[/title]',
        )

        size = len(self.stack)
        max_count = computing_padding(size) + 1

        if not limit:
            limit = size

        for i in range(limit):
            if i > size:
                return

            self.detail(size - i, max_count, advanced=False)

    def detail(self, solve_id: int, max_count: int = -1,
               *, advanced: bool = True) -> None:
        if max_count < 0:
            max_count = computing_padding(len(self.stack)) + 1

        try:
            solve = self.stack[solve_id - 1]
        except IndexError:
            console.print(
                f'Invalid solve #{ solve_id }',
                style='warning',
            )
            return

        index = f'#{ solve_id }'

        if advanced:
            console.print(
                f'[title]Detail for { self.cube_name } #{ solve_id }[/title]',
            )
            cube = Cube(self.cube_size)
            cube.rotate(solve.scramble)
            console.print(cube.printed(), end='')

        date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        console.print(
            f'[stats]{ index:{" "}>{max_count}}[/stats]',
            f'[result]{ format_time(solve.time) }[/result]',
            f'[date]{ date }[/date]',
            f'[consign]{ solve.scramble }[/consign]',
            f'[result]{ solve.flag }[/result]',
        )
        if solve.raw_moves:
            console.print(
                f'[analysis]{ index:{" "}>{max_count}}[/analysis]',
                f'{ solve.report_line }',
            )
            if advanced and solve.missed_moves:
                console.print(
                    f'[analysis]{ index:{" "}>{max_count}}[/analysis]',
                    f'[title]Missed moves[/title]\n{ solve.missed_line }',
                )

    def graph(self) -> None:
        ao5s = []
        ao12s = []
        times = []

        for time in self.stack_time:
            seconds = time / SECOND
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
