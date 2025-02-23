import statistics
from functools import cached_property

import numpy as np

from term_timer.colors import Color as C
from term_timer.constants import STEP_BAR
from term_timer.formatter import computing_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_edge
from term_timer.formatter import format_time
from term_timer.solve import Solve


class Statistics:
    def __init__(self, stack: list[Solve]):
        self.stack = stack

        self.stack_time = [
            s.final_time for s in stack
        ]

    @staticmethod
    def ao(limit: int, stack_elapsed: list[int]) -> int:
        if limit > len(stack_elapsed):
            return -1

        last_of = stack_elapsed[-limit:]
        last_of.remove(min(last_of))
        last_of.remove(max(last_of))
        return int(statistics.fmean(last_of))

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

    @cached_property
    def mo3(self) -> int:
        return int(statistics.fmean(self.stack_time[-3:]))

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
        return min(t for t in self.stack_time if t)

    @cached_property
    def worst(self) -> int:
        return max(self.stack_time)

    @cached_property
    def mean(self) -> int:
        return int(statistics.fmean(self.stack_time))

    @cached_property
    def median(self) -> int:
        return int(statistics.median(self.stack_time))

    @cached_property
    def stdev(self) -> int:
        return int(statistics.stdev(self.stack_time))

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
    def repartition(self) -> list[tuple[int, float]]:
        (histo, bin_edges) = np.histogram(self.stack_time, bins=6)

        return [
            (value, edge)
            for value, edge in zip(histo, bin_edges, strict=False)
            if value
        ]

    def resume(self, prefix: str = '') -> None:
        if not self.stack:
            print(f'{ C.RED }No saved solves yet.{ C.RESET }')
            return

        print(
            f'{ C.STATS }{ prefix }Total :{ C.RESET }',
            f'{ C.RESULT }{ self.total }{ C.RESET }',
        )
        print(
            f'{ C.STATS }{ prefix }Time  :{ C.RESET }',
            f'{ C.RESULT }{ format_time(self.total_time) }{ C.RESET }',
        )
        print(
            f'{ C.STATS }{ prefix }Mean  :{ C.RESET }',
            f'{ C.RESULT }{ format_time(self.mean) }{ C.RESET }',
        )
        print(
            f'{ C.STATS }{ prefix }Median:{ C.RESET }',
            f'{ C.RESULT }{ format_time(self.median) }{ C.RESET }',
        )
        print(
            f'{ C.STATS }{ prefix }Stdev :{ C.RESET }',
            f'{ C.RESULT }{ format_time(self.stdev) }{ C.RESET }',
        )
        if self.total >= 2:
            print(
                f'{ C.STATS }{ prefix }Best  :{ C.RESET }',
                f'{ C.GREEN }{ format_time(self.best) }{ C.RESET }',
            )
            print(
                f'{ C.STATS }{ prefix }Worst :{ C.RESET }',
                f'{ C.RED }{ format_time(self.worst) }{ C.RESET }',
            )
        if self.total >= 3:
            print(
                f'{ C.STATS }{ prefix }Mo3   :{ C.RESET }',
                f'{ C.MO3 }{ format_time(self.mo3) }{ C.RESET }',
            )
        if self.total >= 5:
            print(
                f'{ C.STATS }{ prefix }Ao5   :{ C.RESET }',
                f'{ C.AO5 }{ format_time(self.ao5) }{ C.RESET }',
                f'{ C.STATS }Best :{ C.RESET }',
                f'{ C.RESULT }{ format_time(self.best_ao5) }{ C.RESET }',
                format_delta(self.ao5 - self.best_ao5),
            )
        if self.total >= 12:
            print(
                f'{ C.STATS }{ prefix }Ao12  :{ C.RESET }',
                f'{ C.AO12 }{ format_time(self.ao12) }{ C.RESET }',
                f'{ C.STATS }Best :{ C.RESET }',
                f'{ C.RESULT }{ format_time(self.best_ao12) }{ C.RESET }',
                format_delta(self.ao12 - self.best_ao12),
            )
        if self.total >= 100:
            print(
                f'{ C.STATS }{ prefix }Ao100 :{ C.RESET }',
                f'{ C.AO100 }{ format_time(self.ao100) }{ C.RESET }',
                f'{ C.STATS }Best :{ C.RESET }',
                f'{ C.RESULT }{ format_time(self.best_ao100) }{ C.RESET }',
                format_delta(self.ao100 - self.best_ao100),
            )

        if self.total > 2:
            print(f'{ C.STATS }Distribution :{ C.RESET }')
            max_count = computing_padding(
                max(c for c, e in self.repartition),
            )
            max_edge = computing_padding(
                max(e for c, e in self.repartition),
            )

            for count, edge in self.repartition:
                percent = (count / self.total)

                start = f'{ C.STATS }{ count!s:{" "}>{max_count}} '
                start += f'(+{ format_edge(edge) })'
                start = start.ljust(15 + max_count + max_edge)

                print(
                    f'{ start }:{ C.RESET }',
                    f'{ C.SCRAMBLE }{ round(percent * STEP_BAR) * " " }{ C.RESET }'  # noqa: E501
                    f'{ (STEP_BAR - round(percent * STEP_BAR)) * " " }'
                    f'{ C.RESULT }{ percent * 100:.2f}%{ C.RESET }',
                )
