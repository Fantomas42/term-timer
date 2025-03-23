from functools import cached_property

import numpy as np

from term_timer.console import console
from term_timer.constants import HISTOGRAM_BIN
from term_timer.constants import SECOND
from term_timer.constants import STEP_BAR
from term_timer.formatter import computing_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_edge
from term_timer.formatter import format_time
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
    def __init__(self, cube_size: int, stack: list[Solve]):
        self.cube_size = cube_size
        self.cube_name = f'{ cube_size }x{ cube_size }x{ cube_size }'

        super().__init__(stack)

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
            self.stack[-1].elapsed_time
            - self.stack[-2].elapsed_time
        )

    @cached_property
    def total(self) -> int:
        return len(self.stack)

    @cached_property
    def total_time(self) -> int:
        return sum(self.stack_time)

    @cached_property
    def repartition(self) -> list[tuple[int, int]]:
        values = [st / SECOND for st in self.stack_time]

        min_val = int((np.min(values) // HISTOGRAM_BIN) * HISTOGRAM_BIN)
        max_val = int(((np.max(values) // HISTOGRAM_BIN) + 1) * HISTOGRAM_BIN)

        bins = np.arange(
            int(min_val),
            int(max_val + HISTOGRAM_BIN),
            HISTOGRAM_BIN,
        )

        (histo, bin_edges) = np.histogram(values, bins=bins)

        return [
            (value, edge)
            for value, edge in zip(histo, bin_edges, strict=False)
            if value
        ]

    def resume(self, prefix: str = '') -> None:
        if not self.stack:
            console.print(
                '[warning]No saved solves yet '
                f'for { self.cube_name }.[/warning]',
            )
            return

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
                    f'[edge]{ total_percent * 100:05.2f}%[/edge]',
                )
