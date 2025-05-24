import asyncio
import logging
import time

from term_timer.constants import DNF
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

    def init_solve(self):
        self.set_state('init')
        self.end_time = 0
        self.start_time = 0
        self.elapsed_time = 0

        self.moves = []

        self.save_moves = []
        self.save_gesture = ''
        self.save_gesture_event.clear()

        self.scramble = []
        self.scrambled = []
        self.scramble_oriented = []
        self.facelets_scrambled = ''
        self.scramble_completed_event.clear()

        self.solve_started_event.clear()
        self.solve_completed_event.clear()

        self.inspection_completed_event.clear()

    async def scramble_solve(self):
        self.set_state('scrambling')

        if self.bluetooth_interface:
            tasks = [
                asyncio.create_task(self.getch('scrambled')),
                asyncio.create_task(self.scramble_completed_event.wait()),
            ]
            await self.wait_control(tasks)

            char = ''
            if not self.scramble_completed_event.is_set():
                char = tasks[0].result()
        else:
            char = await self.getch('scrambled')

        if char == 'q':
            return False

        self.set_state('scrambled')

        return True

    async def inspect_solve(self):
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

    async def wait_solve(self):
        if self.bluetooth_interface:
            tasks = [
                asyncio.create_task(self.getch('start')),
                asyncio.create_task(self.solve_started_event.wait()),
            ]
            await self.wait_control(tasks)

    async def time_solve(self):
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

    async def save_solve(self):
        self.set_state('saving')

        if self.bluetooth_interface:
            tasks = [
                asyncio.create_task(self.getch('save')),
                asyncio.create_task(self.save_gesture_event.wait()),
            ]
            await self.wait_control(tasks)

            char = ''
            if not self.save_gesture_event.is_set():
                char = tasks[0].result()
            else:
                self.clear_line(full=True)
                char = self.save_gesture
        else:
            char = await self.getch('save')

        save_string = ''
        if char == 'd':
            self.stack[-1].flag = DNF
            save_string = 'Solve marked as DNF'
        elif char == 'o':
            self.stack[-1].flag = ''
            save_string = 'Solve marked as OK'
        elif char == '2':
            self.stack[-1].flag = PLUS_TWO
            save_string = 'Solve marked as +2'
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
                f'[duration]Duration #{ len(self.stack) }:[/duration] '
                f'[warning]{ save_string }[/warning]',
            )

        return char == 'q'
