"""Stopwatch and timer functionality for solve timing."""
import asyncio
import time
from typing import TYPE_CHECKING

from term_timer.constants import REFRESH
from term_timer.constants import SECOND
from term_timer.formatter import format_time

if TYPE_CHECKING:
    from rich.console import Console as RichConsole


class StopWatch:
    """
    Mixin providing stopwatch and timer functionality for solve timing.

    This mixin provides timing functionality for speedcubing solves, including
    a visual stopwatch display that updates in real-time with color-coded time
    thresholds and optional metronome functionality.

    Attributes:
        start_time: Nanosecond timestamp when the solve started.
        end_time: Nanosecond timestamp when the solve ended.
        elapsed_time: Total elapsed time in nanoseconds.
        metronome: Interval in seconds for metronome beeps (0.0 disables).
        solve_started_event: Asyncio event signaling solve start.
        solve_completed_event: Asyncio event signaling solve completion.

    """

    if TYPE_CHECKING:
        # Attributes from Console mixin
        console: RichConsole

        # Methods from State mixin
        def set_state(self, state: str, timestamp: int | None = None) -> None:  # noqa: D102
            ...

        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None: ...  # noqa: D102
        def back(self, size: int) -> None: ...  # noqa: D102
        def beep(self) -> None: ...  # noqa: D102

    def __init__(self) -> None:
        """Initialize the stopwatch with default timing values and events."""
        super().__init__()

        self.start_time: int = 0
        self.end_time: int = 0
        self.elapsed_time: int = 0

        self.metronome: float = 0.0

        self.solve_started_event = asyncio.Event()
        self.solve_completed_event = asyncio.Event()

    async def stopwatch(self) -> None:  # noqa: C901, PLR0912
        """
        Display a running stopwatch timer until solve is completed.

        Updates the terminal display with the current elapsed time, applying
        color-coded styles based on time thresholds (5s, 10s, 15s, etc.).
        Optionally plays metronome beeps at configured intervals. Runs until
        the solve_completed_event is set.
        """
        self.clear_line(full=True)

        tempo_elapsed = 0
        previous_style = ''

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
