"""Inspection countdown functionality for timed solves."""

import asyncio
import time
from typing import TYPE_CHECKING

from term_timer.constants import REFRESH
from term_timer.constants import SECOND

if TYPE_CHECKING:
    from rich.console import Console as RichConsole


class Inspecter:
    """Mixin providing inspection countdown functionality for timed solves."""

    if TYPE_CHECKING:
        # Attributes from State mixin
        state: str
        # Attributes from Console mixin
        console: RichConsole

        # Methods from State mixin
        def set_state(self, state: str, timestamp: int | None = None) -> None:
            """Set the current state with an optional timestamp."""
            ...

        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None:
            """Clear the current terminal line."""
            ...

        def back(self, size: int) -> None:
            """Move the cursor back by the specified number of characters."""
            ...

        def beep(self) -> None:
            """Emit an audible beep sound."""
            ...

    def __init__(self) -> None:
        """
        Initialize the inspection countdown with default values.

        Set up the countdown timer at 0 seconds and create an asyncio Event
        for signaling when inspection is completed.
        """
        super().__init__()

        self.countdown: int = 0

        self.inspection_completed_event = asyncio.Event()

    async def inspection(self) -> None:
        """
        Run the inspection countdown timer with visual feedback.

        Display a countdown timer in the terminal that updates in real-time,
        showing the remaining inspection time. The display changes color as
        time decreases (normal -> caution -> warning) and emits beeps at 2, 1,
        and 0 seconds remaining. Continue until the inspection_completed_event
        is set, then transition to the 'inspected' state.

        The timer format shows seconds with 2 decimal places and updates at
        the REFRESH rate for smooth countdown display.
        """
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
