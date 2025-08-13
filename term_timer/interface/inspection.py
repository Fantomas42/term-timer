import asyncio
import time

from term_timer.constants import REFRESH
from term_timer.constants import SECOND


class Inspecter:

    def __init__(self):
        super().__init__()

        self.countdown = 0

        self.inspection_completed_event = asyncio.Event()

    async def inspection(self) -> None:
        self.clear_line(full=True)

        state = 0
        first = True
        inspection_start_time = time.perf_counter_ns()

        self.set_state('inspecting', inspection_start_time)

        while not self.inspection_completed_event.is_set():
            elapsed_time = time.perf_counter_ns() - inspection_start_time
            elapsed_seconds = elapsed_time / SECOND

            klass = 'result'
            remaining_time = self.countdown - elapsed_seconds
            remaining_time_rounded = int(remaining_time // 1)

            if remaining_time_rounded != state:
                state = remaining_time_rounded
                if state in {2, 1, 0}:
                    self.beep()

            if remaining_time < 1:
                klass = 'warning'
            elif remaining_time < 3:
                klass = 'caution'

            if first:
                first = False
                self.clear_line(full=False)
                self.console.print(
                    '[inspection]Inspection :[/inspection]',
                    f'[{ klass }]{ remaining_time:.2f}[/{ klass }]',
                    end='',
                )
            else:
                self.back(4)
                self.console.print(
                    f'[{ klass }]{ remaining_time:.2f}[/{ klass }]',
                    end='',
                )

            await asyncio.sleep(REFRESH)

        self.set_state('inspected')
