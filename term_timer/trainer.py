from term_timer.interface import SolveInterface
from term_timer.scrambler import scramble_moves
from term_timer.scrambler import trainer


class Trainer(SolveInterface):
    def __init__(self, *, mode: str,
                 show_cube: bool,
                 metronome: float):

        self.set_state('configure')

        self.mode = mode
        self.show_cube = show_cube
        self.metronome = metronome

        self.counter = 1

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

        self.counter += 1

        # self.solve_line()

        return True
