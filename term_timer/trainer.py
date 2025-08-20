from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.formatter import format_time
from term_timer.interface import SolveInterface
from term_timer.methods.base import FaceletAnalyser
from term_timer.scrambler import scramble_moves
from term_timer.scrambler import trainer
from term_timer.solve import Solve


class Trainer(SolveInterface):
    def __init__(self, *,
                 step: str,
                 cases: list[str],
                 show_cube: bool,
                 metronome: float):
        super().__init__()

        self.set_state('configure')

        self.step = step
        self.show_cube = show_cube
        self.metronome = metronome
        self.cases = cases

        self.step_code = self.step.upper()
        if self.step == 'cross':
            self.step_code = 'Cross'

        self.counter = 1

    def start_line(self, cube, case) -> None:
        if self.show_cube:
            if self.step == 'cross':
                self.console.print(str(cube), end='')
            else:
                self.console.print(getattr(cube, self.step)(), end='')

        if self.step == 'cross':
            link = ''
        else:
            link = (
                'https://cubing.fache.fr/'
                f'{ self.step_code }/'
                f'{ case.split(" ")[0] }.html'
            )

        self.console.print(
            f'[scramble]Training #{ self.counter }:[/scramble]',
            f'[moves]{ self.scramble_oriented }[/moves]',
            f'[comment]// [link={ link }]{ case }[/link][/comment]',
        )

        if self.bluetooth_interface:
            self.console.print(
                'Apply the scramble on the cube to init the timer,',
                '[key](q)[/key] to quit.',
                end='', style='consign',
            )
        else:
            self.console.print(
                'Press any key once scrambled to start/stop the timer,',
                '[key](q)[/key] to quit.',
                end='', style='consign',
            )

    def cube_is_solved(self):
        return FaceletAnalyser().check_step(
            self.step_code,
            self.bluetooth_cube.state,
        )

    def solve_line(self, solve: Solve) -> None:
        self.clear_line(full=True)

        if solve.advanced:
            self.console.print(
                f'[analysis]Executed #{ self.counter }:[/analysis] [consign]' +
                solve.reconstruction_step_line(
                    solve.method_applied.summary[0],
                    multiple=True) +
                '[/consign]',
            )

        self.console.print(
            f'[duration]Duration #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]',
            f'{ solve.trainer_line }',
        )

    async def start(self) -> bool:
        self.init_solve()

        case, self.scramble, cube = trainer(self.step, self.cases)

        if self.bluetooth_cube and not self.bluetooth_cube.is_solved:
            scramble = scramble_moves(
                cube.get_kociemba_facelet_positions(),
                self.bluetooth_cube.state,
            )
            self.scramble_oriented = self.reorient(scramble)
        else:
            self.scramble_oriented = self.reorient(self.scramble)
        self.facelets_scrambled = cube.get_kociemba_facelet_positions()

        self.start_line(cube, case)

        quit_solve = await self.scramble_solve()

        if quit_solve:
            return False

        await self.wait_solve()
        await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time

        flag = ''
        moves = []
        if self.moves:
            if not self.bluetooth_cube.is_solved:
                flag = DNF

            first_time = self.moves[0]['time']
            for move in self.moves:
                timing = int((move['time'] - first_time) / MS_TO_NS_FACTOR)
                moves.append(f'{ move["move"] }@{ timing }')

        solve = Solve(
            self.date,
            self.elapsed_time,
            self.scramble,
            flag=flag,
            timer='Term-Timer',
            device=(
                self.bluetooth_interface
                and self.bluetooth_interface.client.name
            ) or '',
            session='training',
            solve_id=self.counter,
            cube_size=3,
            moves=' '.join(moves),
        )
        solve.method_name = 'cfop'

        self.solve_line(solve)

        self.counter += 1

        return True
