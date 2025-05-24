import asyncio
import logging
import time

from term_timer.console import console
from term_timer.interface import Interface
from term_timer.scrambler import trainer
from term_timer.scrambler import scramble_moves

logger = logging.getLogger(__name__)


class Trainer(Interface):
    def __init__(self, *, mode: str,
                 show_cube: bool,
                 metronome: float):

        self.scramble = []
        self.scrambled = []
        self.moves = []
        self.trainings = 1

        self.mode = mode
        self.show_cube = show_cube
        self.metronome = metronome

    def handle_bluetooth_move(self, event):
        if self.state in {'start', 'scrambling'}:
            self.scrambled.append(event['move'])

            self.handle_scrambled()

        elif self.state == 'scrambled':
            self.moves.append(
                {
                    'move': event['move'],
                    'time': event['clock'],
                },
            )
            self.solve_started_event.set()

        elif self.state == 'solving':
            self.moves.append(
                {
                    'move': event['move'],
                    'time': event['clock'],
                },
            )

            if (
                    not self.solve_completed_event.is_set()
                    and self.bluetooth_cube.is_solved
            ):
                self.end_time = event['clock']
                self.solve_completed_event.set()
                logger.info('BT Stop: %s', self.end_time)

        elif self.state == 'saving':
            move = self.reorient(event['move'])[0]
            self.save_moves.append(move)

            if len(self.save_moves) < 2:
                return

            l_move = self.save_moves[-1]
            a_move = self.save_moves[-2]

            if l_move.base_move != a_move.base_move:
                return

            if l_move == a_move:
                return

            base_move = l_move.base_move
            if base_move in {'R', 'U'}:
                self.save_gesture = 'o'
            elif base_move == 'L':
                self.save_gesture = 'z'
            elif base_move == 'D':
                self.save_gesture = 'q'
            else:
                return

            self.save_gesture_event.set()
            logger.info(
                'Save gesture: %s => %s',
                move, self.save_gesture,
            )

    def start_line(self) -> None:
        if self.bluetooth_interface:
            self.console.print(
                'Apply the scramble on the cube to init the timer,',
                '[b](q)[/b] to quit.',
                end='', style='consign',
            )
        else:
            self.console.print(
                'Press any key once scrambled to start/stop the timer,',
                '[b](q)[/b] to quit.',
                end='', style='consign',
            )

    async def start(self) -> bool:
        self.set_state('start')
        self.moves = []

        self.scramble, cube = trainer(self.mode)

        if self.bluetooth_cube and not self.bluetooth_cube.is_solved:
            scramble = scramble_moves(
                cube.get_kociemba_facelet_positions(),
                self.bluetooth_cube.state,
            )
            self.scramble = scramble

        self.facelets_scrambled = cube.get_kociemba_facelet_positions()

        if self.show_cube:
            self.console.print(str(cube), end='')  # TODO special view

        self.console.print(
            f'[scramble]Training #{ self.trainings }:[/scramble]',
            f'[moves]{ self.scramble }[/moves]',
        )

        self.set_state('scrambling')
        self.scrambled = []
        self.start_line()

        if self.bluetooth_interface:
            self.scramble_completed_event.clear()

            tasks = [
                asyncio.create_task(self.getch('scrambled')),
                asyncio.create_task(self.scramble_completed_event.wait()),
            ]
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            await asyncio.gather(*pending, return_exceptions=True)

            char = ''
            if tasks[0] in done:
                char = tasks[0].result()
                self.scramble_completed_event.set()
        else:
            char = await self.getch('scrambled')

        if char == 'q':
            return False

        self.set_state('scrambled')
        self.solve_started_event.clear()

        if self.bluetooth_interface:
            _done, pending = await asyncio.wait(
                [
                    asyncio.create_task(self.getch('start')),
                    asyncio.create_task(self.solve_started_event.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            await asyncio.gather(*pending, return_exceptions=True)

            if not self.solve_started_event.is_set():
                self.solve_started_event.set()

        stopwatch_task = asyncio.create_task(self.stopwatch())

        if self.bluetooth_interface:
            _done, pending = await asyncio.wait(
                [
                    asyncio.create_task(self.getch('stop')),
                    asyncio.create_task(self.solve_completed_event.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            await asyncio.gather(*pending, return_exceptions=True)

            if not self.stop_event.is_set():
                self.end_time = time.perf_counter_ns()
                self.stop_event.set()
                logger.info('KB Stop: %s', self.end_time)
        else:
            await self.getch('stop')
            self.end_time = time.perf_counter_ns()
            self.stop_event.set()
            logger.info('KB Stop: %s', self.end_time)

        await stopwatch_task

        self.elapsed_time = self.end_time - self.start_time

        #self.handle_solve()
        return True
