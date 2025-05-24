import asyncio
import time

from term_timer.constants import SECOND


class Inspecter:
    countdown = 0

    inspection_completed_event = asyncio.Event()

    async def inspection(self) -> None:
        self.clear_line(full=True)

        self.inspection_completed_event.clear()

        state = 0
        inspection_start_time = time.perf_counter_ns()

        self.set_state('inspecting', inspection_start_time)

        while not self.inspection_completed_event.is_set():
            elapsed_time = time.perf_counter_ns() - inspection_start_time
            elapsed_seconds = elapsed_time / SECOND

            remaining_time = round(self.countdown - elapsed_seconds, 1)

            if int(remaining_time // 1) != state:
                state = int(remaining_time // 1)
                if state in {2, 1, 0}:
                    self.beep()

            self.clear_line(full=False)
            self.console.print(
                '[inspection]Inspection :[/inspection]',
                f'[result]{ remaining_time }[/result]',
                end='',
            )

            await asyncio.sleep(0.01)
