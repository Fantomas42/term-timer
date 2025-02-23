# ruff: noqa: T201
import logging
import statistics
import sys
import termios
import threading
import time
import tty
from argparse import ArgumentParser
from functools import cached_property
from pathlib import Path
from random import seed

import numpy as np

from cubing.scrambler import scrambler

C_RESET = '\x1b[0;0m'
C_STATS = '\x1b[38;5;75m'
C_RECORD = '\x1b[48;5;85m\x1b[38;5;232m'
C_SCRAMBLE = '\x1b[48;5;40m\x1b[38;5;232m'
C_DURATION = '\x1b[48;5;208m\x1b[38;5;232m'
C_GO_BASE = '\x1b[48;5;150m\x1b[38;5;232m'
C_GO_TEN = '\x1b[48;5;112m\x1b[38;5;232m'
C_GO_FIF = '\x1b[48;5;80m\x1b[38;5;232m'
C_GO_TWE = '\x1b[48;5;220m\x1b[38;5;232m'
C_GO_TWF = '\x1b[48;5;208m\x1b[38;5;232m'
C_GO_THR = '\x1b[48;5;160m\x1b[38;5;230m'
C_GO_THF = '\x1b[48;5;89m\x1b[38;5;230m'
C_RESULT = '\x1b[38;5;231m'
C_RED = '\x1b[38;5;196m'
C_GREEN = '\x1b[38;5;82m'
C_MO3 = '\x1b[38;5;172m'
C_AO5 = '\x1b[38;5;86m'
C_AO12 = '\x1b[38;5;99m'
C_AO100 = '\x1b[38;5;208m'

SECOND = 1_000_000_000

STEP_BAR = 15

SAVE_FILE = Path.home() / '.solves'


def load_solves():
    if SAVE_FILE.exists():
        with SAVE_FILE.open() as fd:
            datas = fd.readlines()
        return [
            Solve(*data.split(';')[1:-1])
            for data in datas
        ]

    return []


def save_solves(solves):
    with SAVE_FILE.open('w+') as fd:
        for s in solves:
            fd.write(
                f'{ format_duration(s.elapsed_time) };'
                f'{ s.start_time };{ s.end_time };'
                f'{ s.scramble};{ s.flag };\n',
            )


def format_time(elapsed_ns):
    if not elapsed_ns:
        return 'DNF'

    elapsed_sec = elapsed_ns / SECOND
    mins, secs = divmod(int(elapsed_sec), 60)
    _hours, mins = divmod(mins, 60)
    milliseconds = (elapsed_ns // 1_000_000) % 1000
    return f'{mins:02}:{secs:02}.{milliseconds:03}'


def format_duration(elapsed_ns):
    return f'{ elapsed_ns / SECOND:.2f}'


def format_edge(elapsed_ns):
    return f'{ elapsed_ns / SECOND:.0f}'


def format_delta(delta):
    return '%s%ss%s' % (
        delta > 0 and f'{ C_RED }+' or C_GREEN,
        format_duration(delta),
        C_RESET,
    )


def clear_line():
    print(f'\r{" " * 100}\r', end='', flush=True)


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


class Solve:
    def __init__(self, start_time, end_time, scramble, flag=''):
        self.start_time = int(start_time)
        self.end_time = int(end_time)
        self.scramble = scramble
        self.flag = flag

        self.elapsed_time = self.end_time - self.start_time

    @property
    def final_time(self):
        elapsed = self.elapsed_time

        if self.flag == '+2':
            return elapsed + (2 * SECOND)
        if self.flag == 'DNF':
            return 0

        return elapsed

    def __str__(self):
        return f'{ format_time(self.elapsed_time) }{ self.flag }'


class Timer:
    def __init__(self, free_play, mode, iterations, show_cube, stack):
        self.start_time = None
        self.end_time = None
        self.elapsed_time = None

        self.free_play = free_play
        self.mode = mode
        self.iterations = iterations
        self.show_cube = show_cube
        self.stack = stack

        self.stop_event = threading.Event()
        self.thread = None

    @staticmethod
    def getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def stopwatch(self):
        self.start_time = time.perf_counter_ns()

        while not self.stop_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time

            color = C_GO_BASE
            if elapsed_time > 35 * SECOND:
                color = C_GO_THF
            elif elapsed_time > 30 * SECOND:
                color = C_GO_THR
            elif elapsed_time > 25 * SECOND:
                color = C_GO_TWF
            elif elapsed_time > 20 * SECOND:
                color = C_GO_TWE
            elif elapsed_time > 15 * SECOND:
                color = C_GO_FIF
            elif elapsed_time > 10 * SECOND:
                color = C_GO_TEN

            print(
                f'\r{ color }Go Go Go :{ C_RESET }',
                format_time(elapsed_time),
                end='', flush=True,
            )

            time.sleep(0.01)

    @staticmethod
    def start_line():
        print(
            'Press any key to start/stop the timer,',
            f'{ C_RESULT }(q){ C_RESET } to quit.',
            end='', flush=True,
        )

    @staticmethod
    def save_line():
        print(
            'Press any key to save and continue,',
            f'{ C_RESULT }(d){ C_RESET } for DNF,',
            f'{ C_RESULT }(2){ C_RESET } for +2,',
            f'{ C_RESULT }(z){ C_RESET } to cancel,',
            f'{ C_RESULT }(q){ C_RESET } to save and quit.',
            end='', flush=True,
        )

    def start(self) -> bool:
        scramble, cube = scrambler(
            mode=self.mode,
            iterations=self.iterations,
            show_cube=False,
        )

        solve_number = len(self.stack) + 1

        print(
            f'{ C_SCRAMBLE }Scramble #{ solve_number }:{ C_RESET }',
            f'{ C_RESULT }{ " ".join(scramble) }{ C_RESET }',
        )
        if self.show_cube:
            print(str(cube), end='')

        self.start_line()

        char = self.getch()
        if char == 'q':
            return False

        clear_line()

        self.stop_event.clear()
        self.thread = threading.Thread(target=self.stopwatch)
        self.thread.start()

        self.getch()

        self.end_time = time.perf_counter_ns()

        self.stop_event.set()
        self.thread.join()

        self.elapsed_time = self.end_time - self.start_time

        solve = Solve(
            self.start_time,
            self.end_time,
            ' '.join(scramble),
        )

        old_stats = Statistics(self.stack)
        self.stack = [*self.stack, solve]
        new_stats = Statistics(self.stack)

        extra = ''
        if new_stats.total > 1:
            extra += format_delta(new_stats.delta)

            if new_stats.total >= 3:
                mo3 = new_stats.mo3
                extra += f' { C_MO3 }Mo3 { format_time(mo3) }{ C_RESET }'

            if new_stats.total >= 5:
                ao5 = new_stats.ao5
                extra += f' { C_AO5 }Ao5 { format_time(ao5) }{ C_RESET }'

            if new_stats.total >= 12:
                ao12 = new_stats.ao12
                extra += f' { C_AO12 }Ao12 { format_time(ao12) }{ C_RESET }'

        print(
            f'\r{ C_DURATION }Duration #{ solve_number }:{ C_RESET }',
            f'{ C_RESULT }{ format_time(self.elapsed_time) }{ C_RESET }',
            extra,
        )

        if new_stats.total > 1:
            if new_stats.best < old_stats.best:
                print(
                    f'{ C_RECORD }** New PB !!! ***{ C_RESET }',
                    f'{ C_RESULT }{ format_time(new_stats.best) }{ C_RESET }',
                    format_delta(new_stats.best - old_stats.best),
                )

            if new_stats.ao5 < old_stats.best_ao5:
                print(
                    f'{ C_RECORD }** New Best Ao5 !!! ***{ C_RESET}',
                    f'{ C_RESULT }{ format_time(new_stats.ao5) }{ C_RESET }',
                    format_delta(new_stats.ao5 - old_stats.best_ao5),
                )

            if new_stats.ao12 < old_stats.best_ao12:
                print(
                    f'{ C_RECORD }** New Best Ao12 !!! ***{ C_RESET}',
                    f'{ C_RESULT }{ format_time(new_stats.ao12) }{ C_RESET }',
                    format_delta(new_stats.ao12 - old_stats.best_ao12),
                )

            if new_stats.ao100 < old_stats.best_ao100:
                print(
                    f'{ C_RECORD }** New Best Ao100 !!! ***{ C_RESET}',
                    f'{ C_RESULT }{ format_time(new_stats.ao100) }{ C_RESET }',
                    format_delta(new_stats.ao100 - old_stats.best_ao100),
                )

        if not self.free_play:
            self.save_line()

            char = self.getch()

            clear_line()

            if char == 'd':
                self.stack[-1].flag = 'DNF'
            elif char == '2':
                self.stack[-1].flag = '+2'
            elif char == 'z':
                self.stack.pop()
            elif char == 'q':
                return False

        return True


def main():
    parser = ArgumentParser(
        description='3x3 timer',
    )
    parser.add_argument(
        'scrambles',
        nargs='?',
        help='Number of scrambles',
        default=0,
        type=int,
    )
    parser.add_argument(
        '-c', '--show-cube',
        help='Show the cube scrambled',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '-f', '--free-play',
        help='Disable recording of solves',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '-s', '--seed',
        help='Seed of random moves',
    )
    parser.add_argument(
        '-i', '--iterations',
        help='Iterations of random moves',
        default=0,
        type=int,
    )
    parser.add_argument(
        '-m', '--mode',
        help='Mode of the scramble',
        default='default',
    )
    parser.add_argument(
        '--stats',
        help='Show the statistics',
        action='store_true',
        default=False,
    )

    options = parser.parse_args(sys.argv[1:])

    logging.disable(logging.INFO)

    if options.stats:
        session_stats = Statistics(load_solves())
        session_stats.resume('Global ')
        return 0

    free_play = options.free_play
    if options.seed or options.iterations or options.mode != 'default':
        free_play = True

    if free_play:
        stack = []
        print(
            f'{ C_RED }Mode Free Play is active, '
            f'solves will not be recorded !{ C_RESET }',
        )
    else:
        stack = load_solves()

    if options.seed:
        seed(options.seed)

    solves_done = 0

    while 42:
        timer = Timer(
            free_play=free_play,
            mode=options.mode,
            iterations=options.iterations,
            show_cube=options.show_cube,
            stack=stack,
        )

        done = timer.start()
        stack = timer.stack

        if done:
            solves_done += 1

            if options.scrambles and solves_done >= options.scrambles:
                break
        else:
            break

    clear_line()

    if not free_play:
        save_solves(stack)

    if len(stack) > 1:
        session_stats = Statistics(stack)
        session_stats.resume(free_play and 'Session ' or 'Global ')

    return 0


if __name__ == '__main__':
    # TODO(me): better colors
    #           other cubes ?
    #           decompte
    sys.exit(main())
