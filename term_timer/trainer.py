"""Training interface for practicing specific CFOP cases."""
from dataclasses import dataclass
from functools import cached_property
from random import Random
from typing import Final

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_collection
from cubing_algs.cases.case import Case
from cubing_algs.vcube import VCube

from term_timer.constants import CROSS_CASE
from term_timer.constants import EASY_CROSS_CASE
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SolveFlag
from term_timer.exceptions import InvalidCaseError
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_time
from term_timer.in_out import load_trainings
from term_timer.interface import SolveInterface
from term_timer.methods.base import FaceletAnalyser
from term_timer.printer import print_cube_trainer
from term_timer.scrambler import trainer
from term_timer.solve import Solve
from term_timer.triggers import DEFAULT_TRIGGERS

CROSS_MODES: Final = ('cross', 'ecross')


@dataclass
class TrainingCase:
    """Wrapper for Case with pre-computed best setup algorithms."""

    case: Case
    best_setups: list[Algorithm]


class Trainer(SolveInterface):
    """
    Training interface for practicing specific CFOP cases.

    Generates targeted scrambles for practicing cross, F2L, OLL, or PLL
    cases with optional solution hints.
    """

    def __init__(  # noqa: PLR0913
            self, *,
            step: str,
            case_codes: list[str],
            free_play: bool,
            show_solution: bool,
            show_cube: bool,
            orientation: str,
            metronome: float,
            rng: Random) -> None:
        """Initialize trainer with step configuration and display options."""
        super().__init__()

        self.set_state('configure')

        self.method = 'CFOP'
        self.step = step
        self.step_upper = step.upper()
        self.free_play = free_play
        self.show_solution = show_solution
        self.show_cube = show_cube
        self.metronome = metronome
        self.case_codes = case_codes
        self.rng = rng
        self.orientation_faces = orientation

        self.cases = self.get_cases()

        self.training_stats = []
        if not self.free_play:
            self.training_stats = load_trainings(
                self.method,
                self.step_upper,
            )

        self.console.print(
            f'Training on { len(self.cases) } '
            f'case{ "s" if len(self.cases) > 1 else "" } on '
            f'{ self.method }/{ self.step_upper }',
            style='trainer',
        )

        self.counter = 1

    @cached_property
    def step_code(self) -> str:
        """Step code used for cheching step."""
        if self.step in CROSS_MODES:
            return 'Cross'
        return self.step_upper

    def get_cases(self) -> list[TrainingCase]:
        """
        Build list of trained cases.

        Returns:
            List of validated cases to use in training.

        Raises:
            InvalidCaseError: If selected case is not valid for the step.

        """
        if self.step == 'ecross':
            return [TrainingCase(EASY_CROSS_CASE, [])]
        if self.step == 'cross':
            return [TrainingCase(CROSS_CASE, [])]

        cases = get_collection(f'{ self.method }/{ self.step }').cases
        valid_cases: dict[str, Case] = {
            v.code: v for v in cases.values()
            if v.setup_algorithms
        }

        case_codes = self.case_codes or list(valid_cases.keys())

        def setup_sorter(algorithm: Algorithm) -> tuple[float, float]:
            ergonomics = algorithm.ergonomics
            return (
                ergonomics.estimated_execution_time,
                -ergonomics.comfort_score,
            )

        selected_cases = []
        for case_code in case_codes:
            if case_code not in valid_cases:
                error_string = (
                    f'Invalid case "{ case_code }" for '
                    f'{ self.method }/{ self.step_upper }'
                )
                raise InvalidCaseError(error_string)
            valid_case = valid_cases[case_code]

            setups = valid_case.setup_algorithms

            best_setups = sorted(
                setups,
                key=setup_sorter,
                reverse=False,
            )[:5]

            selected_cases.append(TrainingCase(valid_case, best_setups))

        return selected_cases

    def start_line(self, cube: VCube, selected_case: Case) -> None:
        """Display training case, scramble, and optional solution."""
        link = selected_case.cubing_fache_url
        name = selected_case.pretty_name

        mode = 'cross' if self.step in CROSS_MODES else self.step

        if self.show_cube:
            print_cube_trainer(cube, self.orientation_faces, mode)

        scramble_line = f'[moves]{ self.scramble_oriented }[/moves]'
        if self.cube_orientation_moves:
            scramble_line = (
                f'[rotation]{ self.cube_orientation_moves }[/rotation] '
                + scramble_line
            )

        self.console.print(
            f'[scramble]Training #{ self.counter }:[/scramble]',
            scramble_line,
            f'[comment]// [link={ link }]{ name }[/link][/comment]',
        )

        if self.show_solution and selected_case.main_algorithm:
            formatted_algorithm = format_alg_triggers(
                format_alg_moves(
                    format_alg_aufs(
                        str(selected_case.main_algorithm),
                        pre_auf=True,
                        post_auf=True,
                    ),
                ),
                DEFAULT_TRIGGERS,
            )

            self.console.print(
                f'[solution]Solution #{ self.counter }:[/solution]',
                f'[moves]{ formatted_algorithm }[/moves]',
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

    def cube_is_solved(self) -> bool:
        """
        Check if training step is completed.

        Returns:
            True if the step is solved, False otherwise.

        """
        if self.bluetooth_cube:
            return FaceletAnalyser().check_step(
                self.step_code,
                self.bluetooth_cube.state,
                self.orientation_faces,
            )
        return False

    def solve_line(self, solve: Solve) -> None:
        """Display training solve results and execution details."""
        self.clear_line(full=True)

        if solve.method_applied:
            self.console.print(
                f'[analysis]Executed #{ self.counter }:[/analysis] [consign]' +
                solve.reconstruction_step_line(
                    solve.method_applied.summary[0],
                    multiple=True,
                ) + '[/consign]',
            )

        self.console.print(
            f'[duration]Duration #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]',
            f'{ solve.trainer_line }',
        )

    async def start(self) -> bool:
        """
        Execute training workflow for single case.

        Returns:
            True to continue training, False to quit.

        """
        self.init_solve()

        selected_case, self.scramble, cube = trainer(
                self.step, self.cases,
                self.cube_orientation_moves,
                self.rng,
                self.bluetooth_cube,
        )

        self.scramble_oriented = self.reorient(self.scramble)
        self.facelets_scrambled = cube.state

        self.start_line(cube, selected_case)

        quit_solve = await self.scramble_solve()

        if quit_solve is not None:
            return quit_solve

        await self.wait_solve()
        await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time

        flag: SolveFlag = ''
        moves = []
        if self.moves:
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
                and self.bluetooth_interface.client
                and self.bluetooth_interface.client.name
            ) or '',
            session='training',
            solve_id=self.counter,
            cube_size=3,
            moves=' '.join(moves),
        )
        solve.method_name = self.method.lower()

        self.solve_line(solve)

        self.counter += 1

        return True
