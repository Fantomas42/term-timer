import sys
import termios
import time
import tty
from threading import Event
from threading import Thread

from term_timer.colors import Color as C
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import Statistics


class Timer:
    thread: Thread | None

    def __init__(self, *, mode: str, iterations: int,
                 free_play: bool, show_cube: bool,
                 stack: list[Solve]):
        self.start_time = 0
        self.end_time = 0
        self.elapsed_time = 0

        self.free_play = free_play
        self.mode = mode
        self.iterations = iterations
        self.show_cube = show_cube
        self.stack = stack

        self.stop_event = Event()
        self.thread = None

    @staticmethod
    def getch() -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    @staticmethod
    def clear_line() -> None:
        print(f'\r{" " * 100}\r', end='', flush=True)

    def stopwatch(self) -> None:
        self.start_time = time.perf_counter_ns()

        while not self.stop_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time

            color = C.GO_BASE
            if elapsed_time > 35 * SECOND:
                color = C.GO_THF
            elif elapsed_time > 30 * SECOND:
                color = C.GO_THR
            elif elapsed_time > 25 * SECOND:
                color = C.GO_TWF
            elif elapsed_time > 20 * SECOND:
                color = C.GO_TWE
            elif elapsed_time > 15 * SECOND:
                color = C.GO_FIF
            elif elapsed_time > 10 * SECOND:
                color = C.GO_TEN

            print(
                f'\r{ color }Go Go Go :{ C.RESET }',
                format_time(elapsed_time),
                end='', flush=True,
            )

            time.sleep(0.01)

    @staticmethod
    def start_line() -> None:
        print(
            'Press any key to start/stop the timer,',
            f'{ C.RESULT }(q){ C.RESET } to quit.',
            end='', flush=True,
        )

    @staticmethod
    def save_line() -> None:
        print(
            'Press any key to save and continue,',
            f'{ C.RESULT }(d){ C.RESET } for DNF,',
            f'{ C.RESULT }(2){ C.RESET } for +2,',
            f'{ C.RESULT }(z){ C.RESET } to cancel,',
            f'{ C.RESULT }(q){ C.RESET } to save and quit.',
            end='', flush=True,
        )

    def start(self) -> bool:
        scramble, cube = scrambler(
            mode=self.mode,
            iterations=self.iterations,
        )

        solve_number = len(self.stack) + 1

        print(
            f'{ C.SCRAMBLE }Scramble #{ solve_number }:{ C.RESET }',
            f'{ C.RESULT }{ " ".join(scramble) }{ C.RESET }',
        )
        if self.show_cube:
            print(str(cube), end='')

        self.start_line()

        char = self.getch()
        if char == 'q':
            return False

        self.clear_line()

        self.stop_event.clear()
        self.thread = Thread(target=self.stopwatch)
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
                extra += f' { C.MO3 }Mo3 { format_time(mo3) }{ C.RESET }'

            if new_stats.total >= 5:
                ao5 = new_stats.ao5
                extra += f' { C.AO5 }Ao5 { format_time(ao5) }{ C.RESET }'

            if new_stats.total >= 12:
                ao12 = new_stats.ao12
                extra += f' { C.AO12 }Ao12 { format_time(ao12) }{ C.RESET }'

        print(
            f'\r{ C.DURATION }Duration #{ solve_number }:{ C.RESET }',
            f'{ C.RESULT }{ format_time(self.elapsed_time) }{ C.RESET }',
            extra,
        )

        if new_stats.total > 1:
            if new_stats.best < old_stats.best:
                print(
                    f'{ C.RECORD }** New PB !!! ***{ C.RESET }',
                    f'{ C.RESULT }{ format_time(new_stats.best) }{ C.RESET }',
                    format_delta(new_stats.best - old_stats.best),
                )

            if new_stats.ao5 < old_stats.best_ao5:
                print(
                    f'{ C.RECORD }** New Best Ao5 !!! ***{ C.RESET}',
                    f'{ C.RESULT }{ format_time(new_stats.ao5) }{ C.RESET }',
                    format_delta(new_stats.ao5 - old_stats.best_ao5),
                )

            if new_stats.ao12 < old_stats.best_ao12:
                print(
                    f'{ C.RECORD }** New Best Ao12 !!! ***{ C.RESET}',
                    f'{ C.RESULT }{ format_time(new_stats.ao12) }{ C.RESET }',
                    format_delta(new_stats.ao12 - old_stats.best_ao12),
                )

            if new_stats.ao100 < old_stats.best_ao100:
                print(
                    f'{ C.RECORD }** New Best Ao100 !!! ***{ C.RESET}',
                    f'{ C.RESULT }{ format_time(new_stats.ao100) }{ C.RESET }',
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
