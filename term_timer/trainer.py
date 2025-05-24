import asyncio
import logging

from term_timer.interface import SolveInterface
from term_timer.scrambler import trainer
from term_timer.scrambler import scramble_moves

logger = logging.getLogger(__name__)


class Trainer(SolveInterface):
    def __init__(self, *, mode: str,
                 show_cube: bool,
                 metronome: float):

        self.set_state('configure')

        self.mode = mode
        self.show_cube = show_cube
        self.metronome = metronome

        self.trainings = 1

    def handle_bluetooth_move(self, event):
        if self.state in {'start', 'scrambling'}:
            self.scrambled.append(event['move'])
            self.handle_scrambled(self.trainings)  # TODO find a way

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
                logger.info('Bluetooth Stop: %s', self.end_time)

        elif self.state == 'saving':
            self.handle_save_gestures(event['move'])

    def start_line(self, cube) -> None:
        if self.show_cube:
            self.console.print(str(cube), end='')  # TODO special view

        self.console.print(
            f'[scramble]Training #{ self.trainings }:[/scramble]',
            f'[moves]{ self.scramble }[/moves]',
        )

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
        self.init_solve()

        self.scramble, cube = trainer(self.mode)

        if self.bluetooth_cube and not self.bluetooth_cube.is_solved:
            scramble = scramble_moves(
                cube.get_kociemba_facelet_positions(),
                self.bluetooth_cube.state,
            )
            self.scramble = scramble
        self.facelets_scrambled = cube.get_kociemba_facelet_positions()

        self.start_line(cube)

        quit_solve = await self.scramble_solve()

        if quit_solve:
            return False

        await self.wait_solve()
        await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time

        self.trainings += 1

        # self.solve_line()
        return True
