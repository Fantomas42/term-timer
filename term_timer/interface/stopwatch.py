import asyncio
import time

from term_timer.constants import REFRESH
from term_timer.constants import SECOND
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
        previous_style = ''
        self.start_time = time.perf_counter_ns()

        self.set_state('solving', self.start_time)

        while not self.solve_completed_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time
            elapsed_seconds = elapsed_time / SECOND
            new_tempo = int(elapsed_time / (SECOND * self.metronome or 1))

            style = 'timer_base'
            if elapsed_seconds > 50:
                style = 'timer_50'
            elif elapsed_seconds > 45:
                style = 'timer_45'
            elif elapsed_seconds > 40:
                style = 'timer_40'
            elif elapsed_seconds > 35:
                style = 'timer_35'
            elif elapsed_seconds > 30:
                style = 'timer_30'
            elif elapsed_seconds > 25:
                style = 'timer_25'
            elif elapsed_seconds > 20:
                style = 'timer_20'
            elif elapsed_seconds > 15:
                style = 'timer_15'
            elif elapsed_seconds > 10:
                style = 'timer_10'
            elif elapsed_seconds > 5:
                style = 'timer_05'

            if tempo_elapsed != new_tempo:
                tempo_elapsed = new_tempo
                if self.metronome:
                    self.beep()

            if style != previous_style:
                previous_style = style
                self.clear_line(full=False)
                self.console.print(
                    f'[{ style }]Go Go Go:[/{ style }]',
                    f'[result]{ format_time(elapsed_time) }[/result]',
                    end='',
                )
            else:
                self.back(9)
                self.console.print(
                    f'[result]{ format_time(elapsed_time) }[/result]',
                    end='',
                )

            await asyncio.sleep(REFRESH)

        self.set_state('stop')
