import asyncio
import logging
import time
from datetime import datetime
from datetime import timezone

from cubing_algs.algorithm import Algorithm

from term_timer.constants import DNF
from term_timer.constants import ESCAPE_CHAR
from term_timer.constants import PLUS_TWO
from term_timer.in_out import save_solves
from term_timer.interface.bluetooth import Bluetooth
from term_timer.interface.console import Console
from term_timer.interface.controler import Controler
from term_timer.interface.cube import Orienter
from term_timer.interface.gesture import Gesture
from term_timer.interface.getcher import Getcher
from term_timer.interface.inspection import Inspecter
from term_timer.interface.scrambler import Scrambler
from term_timer.interface.state import State
from term_timer.interface.stopwatch import StopWatch
from term_timer.interface.terminal import Terminal
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
    - Gesture: Gesture detection
    - Bluetooth: Bluetooth cube integration
    """

    def __init__(self) -> None:
        super().__init__()

        self.date: float = 0.0
        self.session: str = ''
        self.cube_size: int = 3
        self.stack: list[Solve] = []

    def init_solve(self) -> None:
        """
        Initialize all state for a new solve.
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
        Handle the scrambling phase of the solve.
        """
        self.set_state('scrambling')

        if self.bluetooth_interface:
            getch_task = asyncio.create_task(self.getch('scrambled'))
            tasks = [
                getch_task,
                asyncio.create_task(self.scramble_completed_event.wait()),
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

    async def inspect_solve(self) -> None:
        """
        Run the inspection countdown phase.
        """
        inspection_task = asyncio.create_task(self.inspection())

        if self.bluetooth_interface:
            tasks = [
                asyncio.create_task(self.getch('inspected', self.countdown)),
                asyncio.create_task(self.solve_started_event.wait()),
            ]
            await self.wait_control(tasks)

            if not self.inspection_completed_event.is_set():
                self.inspection_completed_event.set()
        else:
            await self.getch('inspected', self.countdown)
            self.inspection_completed_event.set()

        await inspection_task

    async def wait_solve(self) -> None:
        """
        Wait for the solve to start (either keyboard or bluetooth).
        """
        if self.bluetooth_interface:
            tasks = [
                asyncio.create_task(self.getch('start')),
                asyncio.create_task(self.solve_started_event.wait()),
            ]
            await self.wait_control(tasks)

    async def time_solve(self) -> None:
        """
        Time the solve execution with stopwatch display.
        """
        if not self.start_time:
            self.start_time = time.perf_counter_ns()

        stopwatch_task = asyncio.create_task(self.stopwatch())

        if self.bluetooth_interface:
            tasks = [
                asyncio.create_task(self.getch('stop')),
                asyncio.create_task(self.solve_completed_event.wait()),
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
        Handle saving the completed solve with optional flag modifications.
        """
        self.set_state('saving')

        if self.bluetooth_interface:
            getch_task = asyncio.create_task(self.getch('save'))
            tasks = [
                getch_task,
                asyncio.create_task(self.save_gesture_event.wait()),
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
        if char == 'd':
            self.stack[-1].flag = DNF
            save_string = 'Solve marked as DNF'
            save_style = 'caution'
        elif char == 'o':
            self.stack[-1].flag = ''
            save_string = 'Solve marked as OK'
            save_style = 'success'
        elif char == '2':
            self.stack[-1].flag = PLUS_TWO
            save_string = 'Solve marked as +2'
            save_style = 'caution'
        elif char == 'z':
            self.stack.pop()
            save_string = 'Solve cancelled'

        save_solves(
            self.cube_size,
            self.session,
            self.stack,
        )

        if save_string:
            self.console.print(
                f'[duration]Duration #{ self.counter }:[/duration] '
                f'[{ save_style }]{ save_string }[/{ save_style }]',
            )

        if char != 'z':
            self.counter += 1

        return char in {'q', ESCAPE_CHAR}
