import sys
import termios
import threading
import time
import tty

from term_timer.colors import C_AO5
from term_timer.colors import C_AO12
from term_timer.colors import C_DURATION
from term_timer.colors import C_GO_BASE
from term_timer.colors import C_GO_FIF
from term_timer.colors import C_GO_TEN
from term_timer.colors import C_GO_THF
from term_timer.colors import C_GO_THR
from term_timer.colors import C_GO_TWE
from term_timer.colors import C_GO_TWF
from term_timer.colors import C_MO3
from term_timer.colors import C_RECORD
from term_timer.colors import C_RESET
from term_timer.colors import C_RESULT
from term_timer.colors import C_SCRAMBLE
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import Statistics


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

    @staticmethod
    def clear_line():
        print(f'\r{" " * 100}\r', end='', flush=True)

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

        self.clear_line()

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

            self.clear_line()

            if char == 'd':
                self.stack[-1].flag = DNF
            elif char == '2':
                self.stack[-1].flag = PLUS_TWO
            elif char == 'z':
                self.stack.pop()
            elif char == 'q':
                return False

        return True
