import asyncio
import time

from term_timer.constants import SECOND
from term_timer.constants import REFRESH
from term_timer.formatter import format_time


class StopWatch:
    start_time = 0
    end_time = 0
    elapsed_time = 0

    metronome = 0

    solve_started_event = asyncio.Event()
    solve_completed_event = asyncio.Event()

    async def stopwatch(self) -> None:
        self.clear_line(full=True)

        tempo_elapsed = 0
        self.start_time = time.perf_counter_ns()

        self.set_state('solving', self.start_time)

        while not self.solve_completed_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time
            new_tempo = int(elapsed_time / (SECOND * self.metronome or 1))

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
            elif elapsed_time > 5 * SECOND:
                style = 'timer_05'

            if tempo_elapsed != new_tempo:
                tempo_elapsed = new_tempo
                if self.metronome:
                    self.beep()

            self.clear_line(full=False)
            self.console.print(
                f'[{ style }]Go Go Go:[/{ style }]',
                f'[result]{ format_time(elapsed_time) }[/result]',
                end='',
            )

            await asyncio.sleep(REFRESH)

        self.set_state('stop')
