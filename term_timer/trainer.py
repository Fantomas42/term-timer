"""Training interface for practicing specific CFOP cases."""
from functools import cached_property
from operator import itemgetter
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
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.in_out import load_trainings
from term_timer.in_out import save_trainings
from term_timer.interface import SolveInterface
from term_timer.methods.base import FaceletAnalyser
from term_timer.printer import print_cube_trainer
from term_timer.scrambler import trainer
from term_timer.solve import Solve
from term_timer.stats import Statistics
from term_timer.triggers import DEFAULT_TRIGGERS
from term_timer.types import TrainingCase

CROSS_MODES: Final = ('cross', 'ecross')


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
            oldest: int,
            slowest: int,
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
        self.oldest = oldest
        self.slowest = slowest
        self.rng = rng
        self.orientation_faces = orientation

        self.trainings = load_trainings(
            self.method,
            self.step_upper,
        )

        self.cases = self.get_cases()

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

    def select_oldest_cases(
            self,
            valid_cases: dict[str, Case],
            count: int) -> list[str]:
        """
        Select cases by least recent practice date.

        Cases with no training data are prioritized as most urgent.

        Args:
            valid_cases: Dictionary of valid cases for the step
            count: Number of cases to select

        Returns:
            List of case codes sorted by practice urgency

        """
        case_dates: list[tuple[str, int]] = []

        for case_code in valid_cases:
            if case_code in self.trainings.cases:
                case_dates.append((
                    case_code,
                    self.trainings.cases[case_code].last_date,
                ))
            else:
                case_dates.append((case_code, 0))

        sorted_cases = sorted(case_dates, key=itemgetter(1))

        return [code for code, _ in sorted_cases[:count]]

    def select_slowest_cases(
            self,
            valid_cases: dict[str, Case],
            count: int) -> list[str]:
        """
        Select cases with worst average of 12.

        Cases with fewer than 12 attempts are prioritized as needing
        more practice.

        Args:
            valid_cases: Dictionary of valid cases for the step
            count: Number of cases to select

        Returns:
            List of case codes sorted by performance need

        """
        case_ao12s: list[tuple[str, int, bool]] = []

        for case_code in valid_cases:
            if case_code in self.trainings.cases:
                case_training = self.trainings.cases[case_code]
                stats = Statistics(case_training.timings)
                ao12 = stats.ao12
                has_enough = len(case_training.timings) >= 12

                if ao12 == -1:
                    case_ao12s.append((case_code, 999999999, False))
                else:
                    case_ao12s.append((case_code, ao12, has_enough))
            else:
                case_ao12s.append((case_code, 999999999, False))

        sorted_cases = sorted(
            case_ao12s,
            key=lambda x: (x[2], -x[1]),
        )

        return [code for code, _, _ in sorted_cases[:count]]

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

        if self.oldest > 0:
            case_codes = self.select_oldest_cases(
                valid_cases,
                self.oldest,
            )
        elif self.slowest > 0:
            case_codes = self.select_slowest_cases(
                valid_cases,
                self.slowest,
            )

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
            f'[comment]// [link={ link }]{ name }[/link] '
            f'#{ len(self.trainings.cases[selected_case.code].timings) }'
            '[/comment]',
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

    def solve_line(self, solve: Solve, selected_case: Case) -> None:  # noqa: C901
        """Display training solve results and execution details."""
        self.trainings.add_timing(
            selected_case.code,
            int(self.elapsed_time / MS_TO_NS_FACTOR),
            int(self.date),
        )

        timings = [
            i * MS_TO_NS_FACTOR
            for i in self.trainings.cases[selected_case.code].timings
        ]
        old_stats = Statistics(timings[:-1])
        new_stats = Statistics(timings)

        self.clear_line(full=True)

        if solve.method_applied:
            self.console.print(
                f'[analysis]Executed #{ self.counter }:[/analysis] [consign]' +
                solve.reconstruction_step_line(
                    solve.method_applied.summary[0],
                    multiple=True,
                ) + '[/consign]',
                solve.trainer_line,
            )

        extra = ''
        if new_stats.total > 1:
            extra += format_delta(new_stats.delta)

            if new_stats.total >= 3:
                mo3 = new_stats.mo3
                extra += f' [mo3]Mo3 { format_time(mo3) }[/mo3]'

            if new_stats.total >= 5:
                ao5 = new_stats.ao5
                extra += f' [ao5]Ao5 { format_time(ao5) }[/ao5]'

            if new_stats.total >= 12:
                ao12 = new_stats.ao12
                extra += f' [ao12]Ao12 { format_time(ao12) }[/ao12]'

        self.console.print(
            f'[duration]Duration #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]',
            extra,
        )

        if new_stats.total > 1:
            mc = 10 + len(str(len(self.stack))) - 1
            if new_stats.best < old_stats.best:
                self.console.print(
                    f'[record]:rocket:{ "New PB !".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.best) }[/best]',
                    format_delta(new_stats.best - old_stats.best),
                )

            if new_stats.ao5 < old_stats.best_ao5:
                self.console.print(
                    f'[record]:boom:{ "Best Ao5".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao5) }[/best]',
                    format_delta(new_stats.ao5 - old_stats.best_ao5),
                )

            if new_stats.ao12 < old_stats.best_ao12:
                self.console.print(
                    f'[record]:muscle:{ "Best Ao12".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao12) }[/best]',
                    format_delta(new_stats.ao12 - old_stats.best_ao12),
                )

            if new_stats.ao100 < old_stats.best_ao100:
                self.console.print(
                    f'[record]:crown:{ "Best Ao100".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao100) }[/best]',
                    format_delta(new_stats.ao100 - old_stats.best_ao100),
                )

            if new_stats.ao1000 < old_stats.best_ao1000:
                self.console.print(
                    f'[record]:trophy:{ "Best Ao1000".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao1000) }[/best]',
                    format_delta(new_stats.ao1000 - old_stats.best_ao1000),
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

        self.solve_line(solve, selected_case)

        if not self.free_play:
            save_trainings(self.trainings)

        self.counter += 1

        return True
