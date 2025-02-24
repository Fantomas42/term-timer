import sys
import termios
import time
import tty
from threading import Event
from threading import Thread

from term_timer.console import console
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
                 metronome: bool, stack: list[Solve]):
        self.start_time = 0
        self.end_time = 0
        self.elapsed_time = 0

        self.free_play = free_play
        self.mode = mode
        self.iterations = iterations
        self.show_cube = show_cube
        self.metronome = metronome
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

        print(f'\r{ " " * 100}\r', flush=True, end='')

        return ch

    def stopwatch(self) -> None:
        self.start_time = time.perf_counter_ns()

        seconds_elapsed = 0

        while not self.stop_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time
            rounded_seconds = int(elapsed_time / SECOND)

            style = 'timer_base'
            if elapsed_time > 50 * SECOND:
                style = 'timer_50'
            elif elapsed_time > 45 * SECOND:
                style = 'timer_45'
            elif elapsed_time > 40 * SECOND:
                style = 'timer_40'
            elif elapsed_time > 35 * SECOND:
                style = 'timer_35'
            elif elapsed_time > 30 * SECOND:
                style = 'timer_30'
            elif elapsed_time > 25 * SECOND:
                style = 'timer_25'
            elif elapsed_time > 20 * SECOND:
                style = 'timer_20'
            elif elapsed_time > 15 * SECOND:
                style = 'timer_15'
            elif elapsed_time > 10 * SECOND:
                style = 'timer_10'

            if seconds_elapsed != rounded_seconds:
                seconds_elapsed = rounded_seconds
                if self.metronome:
                    print('\a', end='', flush=True)

            print('\r', end='')
            console.print(
                f'[{ style }]Go Go Go:[/{ style }]',
                f'[result]{ format_time(elapsed_time) }[/result]',
                end='',
            )

            time.sleep(0.01)

    @staticmethod
    def start_line() -> None:
        console.print(
            'Press any key to start/stop the timer,',
            '[b](q)[/b] to quit.',
            end='', style='consign',
        )

    @staticmethod
    def save_line() -> None:
        console.print(
            'Press any key to save and continue,',
            '[b](d)[/b] for DNF,',
            '[b](2)[/b] for +2,',
            '[b](z)[/b] to cancel,',
            '[b](q)[/b] to save and quit.',
            end='', style='consign',
        )

    def handle_solve(self, solve: Solve) -> None:
        old_stats = Statistics(self.stack)

        self.stack = [*self.stack, solve]
        new_stats = Statistics(self.stack)

        extra = ''
        if new_stats.total > 1:
            extra += format_delta(new_stats.delta)

            if new_stats.total >= 3:
                mo3 = new_stats.mo3
                extra += f' [mo3]Mo3 { format_time(mo3) }[/mo3]'

            if new_stats.total >= 5:
                ao5 = new_stats.ao5
                extra += f' [ao5]Ao5 { format_time(ao5) }[/ao5]'

            if new_stats.total >= 12:
                ao12 = new_stats.ao12
                extra += f' [ao12]Ao12 { format_time(ao12) }[/ao12]'

        print('\r', end='')
        console.print(
            f'[duration]Duration #{ len(self.stack) }:[/duration]',
            f'[result]{ format_time(self.elapsed_time) }[/result]',
            extra,
        )

        if new_stats.total > 1:
            mc = 10 + len(str(len(self.stack))) - 1
            if new_stats.best < old_stats.best:
                console.print(
                    f'[record]:rocket:{ "New PB !".center(mc) }[/record]',
                    f'[result]{ format_time(new_stats.best) }[/result]',
                    format_delta(new_stats.best - old_stats.best),
                )

            if new_stats.ao5 < old_stats.best_ao5:
                console.print(
                    f'[record]:boom:{ "Best Ao5".center(mc) }[/record]',
                    f'[result]{ format_time(new_stats.ao5) }[/result]',
                    format_delta(new_stats.ao5 - old_stats.best_ao5),
                )

            if new_stats.ao12 < old_stats.best_ao12:
                console.print(
                    f'[record]:muscle:{ "Best Ao12".center(mc) }[/record]',
                    f'[result]{ format_time(new_stats.ao12) }[/result]',
                    format_delta(new_stats.ao12 - old_stats.best_ao12),
                )

            if new_stats.ao100 < old_stats.best_ao100:
                console.print(
                    f'[record]:crown:{ "Best Ao100".center(mc) }[/record]',
                    f'[result]{ format_time(new_stats.ao100) }[/result]',
                    format_delta(new_stats.ao100 - old_stats.best_ao100),
                )

    def start(self) -> bool:
        scramble, cube = scrambler(
            mode=self.mode,
            iterations=self.iterations,
        )

        console.print(
            f'[scramble]Scramble #{ len(self.stack) + 1 }:[/scramble]',
            f'[moves]{ " ".join(scramble) }[/moves]',
        )

        if self.show_cube:
            console.print(str(cube), end='')

        self.start_line()

        char = self.getch()

        if char == 'q':
            return False

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

        self.handle_solve(solve)

        if not self.free_play:
            self.save_line()

            char = self.getch()

            if char == 'd':
                self.stack[-1].flag = DNF
            elif char == '2':
                self.stack[-1].flag = PLUS_TWO
            elif char == 'z':
                self.stack.pop()
            elif char == 'q':
                return False

        return True
