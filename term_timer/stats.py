import statistics
from functools import cached_property

import numpy as np

from term_timer.colors import C_RED
from term_timer.colors import C_RESET
from term_timer.colors import C_STATS
from term_timer.colors import C_RESULT
from term_timer.colors import C_GREEN
from term_timer.colors import C_AO100
from term_timer.colors import C_AO12
from term_timer.colors import C_AO5
from term_timer.colors import C_MO3
from term_timer.colors import C_SCRAMBLE
from term_timer.constants import STEP_BAR
from term_timer.formatter import format_delta
from term_timer.formatter import format_edge
from term_timer.formatter import format_time



class Statistics:
    def __init__(self, stack):
        self.stack = stack

        self.stack_time = [
            s.final_time for s in stack
        ]

    @staticmethod
    def ao(limit, stack_elapsed):
        if limit > len(stack_elapsed):
            return -1

        last_of = stack_elapsed[-limit:]
        last_of.remove(min(last_of))
        last_of.remove(max(last_of))
        return int(statistics.fmean(last_of))

    def best_ao(self, limit):
        aos = []
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
    def mo3(self):
        return int(statistics.fmean(self.stack_time[-3:]))

    @cached_property
    def ao5(self):
        return self.ao(5, self.stack_time)

    @cached_property
    def ao12(self):
        return self.ao(12, self.stack_time)

    @cached_property
    def ao100(self):
        return self.ao(100, self.stack_time)

    @cached_property
    def best_ao5(self):
        return self.best_ao(5)

    @cached_property
    def best_ao12(self):
        return self.best_ao(12)

    @cached_property
    def best_ao100(self):
        return self.best_ao(100)

    @cached_property
    def best(self):
        return min(t for t in self.stack_time if t)

    @cached_property
    def worst(self):
        return max(self.stack_time)

    @cached_property
    def mean(self):
        return int(statistics.fmean(self.stack_time))

    @cached_property
    def median(self):
        return int(statistics.median(self.stack_time))

    @cached_property
    def stdev(self):
        return int(statistics.stdev(self.stack_time))

    @cached_property
    def delta(self):
        return (
            self.stack[-1].elapsed_time
            - self.stack[-2].elapsed_time
        )

    @cached_property
    def total(self):
        return len(self.stack)

    @cached_property
    def total_time(self):
        return sum(self.stack_time)

    @cached_property
    def repartition(self):
        (histo, bin_edges) = np.histogram(self.stack_time, bins=6)

        return [
            (value, edge)
            for value, edge in zip(histo, bin_edges)
            if value
        ]

    def resume(self, prefix=''):
        if not self.stack:
            print(f'{ C_RED }No saved solves yet.{ C_RESET }')
            return

        print(
            f'{ C_STATS }{ prefix }Total :{ C_RESET }',
            f'{ C_RESULT }{ self.total }{ C_RESET }',
        )
        print(
            f'{ C_STATS }{ prefix }Time  :{ C_RESET }',
            f'{ C_RESULT }{ format_time(self.total_time) }{ C_RESET }',
        )
        print(
            f'{ C_STATS }{ prefix }Mean  :{ C_RESET }',
            f'{ C_RESULT }{ format_time(self.mean) }{ C_RESET }',
        )
        print(
            f'{ C_STATS }{ prefix }Median:{ C_RESET }',
            f'{ C_RESULT }{ format_time(self.median) }{ C_RESET }',
        )
        print(
            f'{ C_STATS }{ prefix }Stdev :{ C_RESET }',
            f'{ C_RESULT }{ format_time(self.stdev) }{ C_RESET }',
        )
        if self.total >= 2:
            print(
                f'{ C_STATS }{ prefix }Best  :{ C_RESET }',
                f'{ C_GREEN }{ format_time(self.best) }{ C_RESET }',
            )
            print(
                f'{ C_STATS }{ prefix }Worst :{ C_RESET }',
                f'{ C_RED }{ format_time(self.worst) }{ C_RESET }',
            )
        if self.total >= 3:
            print(
                f'{ C_STATS }{ prefix }Mo3   :{ C_RESET }',
                f'{ C_MO3 }{ format_time(self.mo3) }{ C_RESET }',
            )
        if self.total >= 5:
            print(
                f'{ C_STATS }{ prefix }Ao5   :{ C_RESET }',
                f'{ C_AO5 }{ format_time(self.ao5) }{ C_RESET }',
                f'{ C_STATS }Best :{ C_RESET }',
                f'{ C_RESULT }{ format_time(self.best_ao5) }{ C_RESET }',
                format_delta(self.ao5 - self.best_ao5),
            )
        if self.total >= 12:
            print(
                f'{ C_STATS }{ prefix }Ao12  :{ C_RESET }',
                f'{ C_AO12 }{ format_time(self.ao12) }{ C_RESET }',
                f'{ C_STATS }Best :{ C_RESET }',
                f'{ C_RESULT }{ format_time(self.best_ao12) }{ C_RESET }',
                format_delta(self.ao12 - self.best_ao12),
            )
        if self.total >= 100:
            print(
                f'{ C_STATS }{ prefix }Ao100 :{ C_RESET }',
                f'{ C_AO100 }{ format_time(self.ao100) }{ C_RESET }',
                f'{ C_STATS }Best :{ C_RESET }',
                f'{ C_RESULT }{ format_time(self.best_ao100) }{ C_RESET }',
                format_delta(self.ao100 - self.best_ao100),
            )

        if self.total > 2:
            print(f'{ C_STATS }Distribution :{ C_RESET }')
            max_count = 1
            max_value = max(c for c, e in self.repartition)
            if max_value > 10:
                max_count = 2
            elif max_value > 100:
                max_count = 3

            for count, edge in self.repartition:
                percent = (count / self.total)
                print(
                    f'{ C_STATS }{ count!s:{" "}>{max_count}}',
                    f'(+{ format_edge(edge) }) :{ C_RESET }',
                    f'{ C_SCRAMBLE }{ round(percent * STEP_BAR) * " " }{ C_RESET }'
                    f'{ (STEP_BAR - round(percent * STEP_BAR)) * " " }'
                    f'{ C_RESULT }{ percent * 100:.2f}%{ C_RESET }',
                )
