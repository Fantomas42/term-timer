"""Interface modules providing mixins for timer and trainer functionality."""
import logging
import time
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm

from term_timer.constants import DNF
from term_timer.constants import ESCAPE_CHAR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SOLVES_DIRECTORY
from term_timer.in_out import save_solves
from term_timer.interface.bluetooth import Bluetooth
from term_timer.interface.console import Console
from term_timer.interface.controler import Controler
from term_timer.interface.cube import Orienter
from term_timer.interface.gesture import Gesture
from term_timer.interface.getcher import Getcher
from term_timer.interface.inspection import Inspecter
from term_timer.interface.scrambler import Scrambler
from term_timer.interface.series import SeriesReporter
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.interface.state import State
from term_timer.interface.stopwatch import StopWatch
from term_timer.interface.terminal import Terminal
from term_timer.logger import spawn

if TYPE_CHECKING:
    from term_timer.solve import Solve

logger = logging.getLogger(__name__)


class SolveInterface(
        State,
        Terminal,
        Console,
        Controler,
        Getcher,
        Orienter,
        StopWatch,
        Inspecter,
        Scrambler,
        SeriesReporter,
        Gesture,
        Bluetooth,
):
    """
    Main interface combining all mixins for solve timing and tracking.

    This class uses multiple inheritance with mixins to provide a complete
    solving interface. Each mixin provides specific functionality:
    - State: State management and transitions
    - Terminal: Low-level terminal control
    - Console: Rich console output
    - Controler: Async task coordination
    - Getcher: Async keyboard input
    - Orienter: Cube orientation handling
    - StopWatch: Timer functionality
    - Inspecter: Inspection countdown
    - Scrambler: Scramble tracking
    - SeriesReporter: Rolling-average series display
    - Gesture: Gesture detection
    - Bluetooth: Bluetooth cube integration

    Attributes:
        date: Timestamp of the current solve in UTC seconds since epoch.
        session: Name of the current solving session.
        cube_size: Size of the cube being solved (2-7).
        stack: List of completed solves in the current session.

    """

    def __init__(self) -> None:
        """Initialize the solve interface with default state values."""
        super().__init__()

        self.date: float = 0.0
        self.session: str = ''
        self.cube_size: int = 3
        self.stack: list[Solve] = []
        self.stack_done: list[Solve] = []
        self.save_directory = SOLVES_DIRECTORY
        self.retry_enabled: bool = True
        self.retry_requested: bool = False

    def init_solve(self) -> None:
        """
        Reset all state variables to prepare for a new solve attempt.

        Clears timing data, scramble information, moves history, and all
        synchronization events. Sets the solve state to 'init' and records
        the current timestamp.
        """
        self.set_state('init')
        self.date = datetime.now(tz=timezone.utc).timestamp()  # noqa: UP017
        self.end_time = 0
        self.start_time = 0
        self.elapsed_time = 0

        self.moves = []

        self.save_moves = Algorithm()
        self.save_gesture = ''
        self.save_gesture_event.clear()

        self.scramble = Algorithm()
        self.scrambled = Algorithm()
        self.scramble_oriented = Algorithm()
        self.facelets_scrambled = ''
        self.scramble_completed_event.clear()

        self.solve_started_event.clear()
        self.solve_completed_event.clear()

        self.inspection_completed_event.clear()

    async def scramble_solve(self) -> bool | None:
        """
        Manage the scrambling phase waiting for user or bluetooth input.

        Sets state to 'scrambling' and waits for keyboard input or bluetooth
        cube scramble completion. Handles both bluetooth and non-bluetooth
        input modes.

        Returns:
            False if user quit (pressed 'q' or ESC), True if bluetooth
            scramble interrupted by keyboard, None if scramble completed
            normally.

        """
        self.set_state('scrambling')

        if self.bluetooth_interface:
            getch_task = spawn(self.getch('scrambled'), 'getch-scrambled')
            tasks = [
                getch_task,
                spawn(
                    self.scramble_completed_event.wait(),
                    'event-scramble-completed',
                ),
            ]
            await self.wait_control(tasks)

            char = ''
            if not self.scramble_completed_event.is_set():
                result = getch_task.result()
                char = result if isinstance(result, str) else ''
        else:
            char = await self.getch('scrambled')

        if char in {'q', ESCAPE_CHAR}:
            return False

        if char and self.bluetooth_interface:
            return True

        self.set_state('scrambled')

        return None

    async def inspect_solve(self) -> bool:
        """
        Execute the inspection countdown phase before solve start.

        Runs the inspection countdown task and waits for either keyboard
        input or bluetooth solve start event. Sets the inspection completed
        event when finished. Handles both bluetooth and non-bluetooth modes.

        Returns:
            True if user quit (pressed 'q' or ESC) in bluetooth mode,
            False otherwise.

        """
        inspection_task = spawn(self.inspection(), 'inspection')

        if self.bluetooth_interface:
            getch_task = spawn(
                self.getch('inspected', self.countdown),
                'getch-inspected',
            )
            tasks = [
                getch_task,
                spawn(
                    self.solve_started_event.wait(),
                    'event-solve-started',
                ),
            ]
            await self.wait_control(tasks)

            if not self.inspection_completed_event.is_set():
                self.inspection_completed_event.set()

            if not self.solve_started_event.is_set():
                result = getch_task.result()
                char = result if isinstance(result, str) else ''
                if not char:
                    SOUND_PLAYER.la_4()
                elif char in {'q', ESCAPE_CHAR}:
                    await inspection_task
                    return True
        else:
            char = await self.getch('inspected', self.countdown)
            if not char:
                SOUND_PLAYER.la_4()
            self.inspection_completed_event.set()
            if char in {'q', ESCAPE_CHAR}:
                await inspection_task
                return True

        await inspection_task
        return False

    async def wait_solve(self) -> bool:
        """
        Wait for solve start trigger from keyboard or bluetooth cube.

        In bluetooth mode, races keyboard input against the solve started
        event from the bluetooth cube. Ensures the solve begins only when
        triggered by the appropriate input source.

        Returns:
            True if user quit (pressed 'q' or ESC) in bluetooth mode,
            False otherwise.

        """
        if self.bluetooth_interface:
            getch_task = spawn(self.getch('start'), 'getch-start')
            tasks = [
                getch_task,
                spawn(
                    self.solve_started_event.wait(),
                    'event-solve-started',
                ),
            ]
            await self.wait_control(tasks)

            if not self.solve_started_event.is_set():
                result = getch_task.result()
                char = result if isinstance(result, str) else ''
                if char in {'q', ESCAPE_CHAR}:
                    return True

        return False

    async def time_solve(self) -> None:
        """
        Record solve duration with live stopwatch display.

        Captures the start time if not already set, displays a running
        stopwatch, and waits for solve completion via keyboard or bluetooth
        cube. Records the end time and logs the stop event source.
        """
        if not self.start_time:
            self.start_time = time.perf_counter_ns()

        stopwatch_task = spawn(self.stopwatch(), 'stopwatch')

        if self.bluetooth_interface:
            tasks = [
                spawn(self.getch('stop'), 'getch-stop'),
                spawn(
                    self.solve_completed_event.wait(),
                    'event-solve-completed',
                ),
            ]
            await self.wait_control(tasks)

            if not self.solve_completed_event.is_set():
                self.end_time = time.perf_counter_ns()
                self.solve_completed_event.set()
                logger.info('Keyboard Stop: %s', self.end_time)
        else:
            await self.getch('stop')

            self.end_time = time.perf_counter_ns()
            self.solve_completed_event.set()
            logger.info('Keyboard Stop: %s', self.end_time)

        await stopwatch_task

    async def save_solve(self) -> bool:
        """
        Save the completed solve with optional flag modifications.

        Waits for user input to mark the solve with a flag (DNF, +2) or
        cancel it. Flag keys are only honored in manual mode: with a
        Bluetooth cube the flag is derived from the cube state and
        cannot be edited. Persists the solve to storage and displays
        confirmation. Handles both keyboard and bluetooth gesture input.

        A retry is a discard that replays the same scramble immediately,
        so it drops the solve like 'z' does and flags the replay instead
        of quitting. It is only honored where it differs from a discard:
        an imposed scramble is already replayed by the next attempt, and
        'r' saves there like any other unrecognised key.

        Returns:
            True if user quit (pressed 'q', 'k' or ESC), False otherwise.

        """
        self.set_state('saving')

        if self.bluetooth_interface:
            getch_task = spawn(self.getch('save'), 'getch-save')
            tasks = [
                getch_task,
                spawn(
                    self.save_gesture_event.wait(),
                    'event-save-gesture',
                ),
            ]
            await self.wait_control(tasks)

            char = ''
            if not self.save_gesture_event.is_set():
                result = getch_task.result()
                char = result if isinstance(result, str) else ''
            else:
                self.clear_line(full=True)
                char = self.save_gesture
        else:
            char = await self.getch('save')

        save_string = ''
        save_style = 'warning'
        manual = self.bluetooth_interface is None
        retry = char == 'r' and self.retry_enabled
        if manual and char == 'd':
            self.stack[-1].flag = DNF
            self.stack_done[-1].flag = DNF
            save_string = 'Solve marked as DNF'
            save_style = 'caution'
        elif manual and char == '2':
            self.stack[-1].flag = PLUS_TWO
            self.stack_done[-1].flag = PLUS_TWO
            save_string = 'Solve marked as +2'
            save_style = 'caution'
        elif retry or char in {'z', 'k'}:
            self.stack.pop()
            self.stack_done.pop()
            self.retry_requested = retry
            save_string = (
                'Retrying scramble'
                if retry
                else 'Solve discarded'
            )

        save_solves(
            self.cube_size,
            self.session,
            self.stack,
            self.save_directory,
        )

        if save_string:
            self.console.print(
                f'[duration]Duration #{ self.counter }:[/duration] '
                f'[{ save_style }]{ save_string }[/{ save_style }]',
            )

        if not retry and char not in {'z', 'k'}:
            self.counter += 1
            SOUND_PLAYER.save_confirmed()
        else:
            SOUND_PLAYER.save_discarded()

        return char in {'q', 'k', ESCAPE_CHAR}
