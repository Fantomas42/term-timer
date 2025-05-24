import asyncio
import time

from term_timer.constants import REFRESH
from term_timer.constants import SECOND


class Inspecter:
    countdown = 0

    inspection_completed_event = asyncio.Event()

    async def inspection(self) -> None:
        self.clear_line(full=True)

        state = 0
        inspection_start_time = time.perf_counter_ns()

        self.set_state('inspecting', inspection_start_time)

        while not self.inspection_completed_event.is_set():
            elapsed_time = time.perf_counter_ns() - inspection_start_time
            elapsed_seconds = elapsed_time / SECOND

            klass = 'result'
            remaining_time = round(self.countdown - elapsed_seconds, 1)

            if int(remaining_time // 1) != state:
                state = int(remaining_time // 1)
                if state in {2, 1, 0}:
                    self.beep()

            if remaining_time < 1:
                klass = 'warning'
            elif remaining_time < 3:
                klass = 'caution'

            self.clear_line(full=False)
            self.console.print(
                '[inspection]Inspection :[/inspection]',
                f'[{ klass }]{ remaining_time }[/{ klass }]',
                end='',
            )

            await asyncio.sleep(REFRESH)

        self.set_state('inspected')
