"""Timer interface for recording and analyzing cube solves."""
import logging
from random import Random

from cubing_algs.algorithm import Algorithm
from cubing_algs.solver import facelets_to_facelets_algorithm
from cubing_algs.vcube import VCube

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SolveFlag
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.interface import SolveInterface
from term_timer.printer import print_cube_scrambled
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter

logger = logging.getLogger(__name__)


class Timer(SolveInterface):
    """
    Main timer interface for recording and analyzing cube solves.

    Manages the complete solve workflow including scrambling, timing,
    recording moves, and displaying statistics.
    """

    def __init__(  # noqa: PLR0913
            self, *,
            cube_size: int,
            iterations: int,
            easy_cross: bool,
            scramble: str,
            scrambles: list[Algorithm],
            session: str,
            free_play: bool,
            show_cheers: bool,
            show_cube: bool,
            show_reconstruction: bool,
            show_tps_graph: bool,
            show_time_graph: bool,
            show_fluency_graph: bool,
            show_recognition_graph: bool,
            method: str,
            orientation: str,
            countdown: int,
            metronome: float,
            stack: list[Solve],
            rng: Random) -> None:
        """Initialize timer with configuration and existing solve stack."""
        super().__init__()

        self.set_state('configure')

        self.cube_size = cube_size
        self.session = session
        self.free_play = free_play
        self.iterations = iterations
        self.easy_cross = easy_cross
        self.raw_scramble = scramble
        self.scrambles = scrambles
        self.scramble_index = 0
        self.show_cheers = show_cheers
        self.show_cube = show_cube
        self.show_reconstruction = show_reconstruction
        self.show_tps_graph = show_tps_graph
        self.show_time_graph = show_time_graph
        self.show_fluency_graph = show_fluency_graph
        self.show_recognition_graph = show_recognition_graph
        self.method = method
        self.orientation_faces = orientation
        self.countdown = countdown
        self.metronome = metronome
        self.stack = stack
        self.stack_done: list[Solve] = []
        self.rng = rng

        self.counter = len(stack) + 1

        if self.free_play:
            self.console.print(
                '🔒 Mode Free Play is active, '
                'solves will not be recorded !',
                style='warning',
            )

    def start_line(self, cube: VCube) -> None:
        """Display scramble information and instructions to start solve."""
        if self.show_cube:
            print_cube_scrambled(cube, self.orientation_faces, self.scramble)

        scramble_line = f'[scramble]Scramble #{ self.counter }:[/scramble] '
        if self.cube_orientation_moves:
            scramble_line += (
                f'[rotation]{ self.cube_orientation_moves }[/rotation] '
            )
        scramble_line += f'[moves]{ self.scramble_oriented }[/moves]'

        self.console.print(scramble_line)

        if self.bluetooth_interface:
            if self.countdown:
                self.console.print(
                    'Apply the scramble on the cube to start the inspection,',
                    '[key](q)[/key] to quit.',
                    end='', style='consign',
                )
            else:
                self.console.print(
                    'Apply the scramble on the cube to init the timer,',
                    '[key](q)[/key] to quit.',
                    end='', style='consign',
                )
        elif self.countdown:
            self.console.print(
                'Press any key once scrambled to start the inspection,',
                '[key](q)[/key] to quit.',
                end='', style='consign',
            )
        else:
            self.console.print(
                'Press any key once scrambled to start/stop the timer,',
                '[key](q)[/key] to quit.',
                end='', style='consign',
            )

    def save_line(self, flag: SolveFlag) -> None:
        """Display instructions for saving or canceling the solve."""
        if self.bluetooth_interface:
            self.console.print(
                'Press any key to save and continue,',
                '[key](z)[/key] to cancel,',
                '[key](q)[/key] to save and quit.',
                end='', style='consign',
            )
        else:
            self.console.print(
                'Press any key to save and continue,',
                (
                    '[key](d)[/key] for DNF,'
                    if flag != DNF
                    else '[key](o)[/key] for OK'
                ),
                '[key](2)[/key] for +2,',
                '[key](z)[/key] to cancel,',
                '[key](q)[/key] to save and quit.',
                end='', style='consign',
            )

    def solve_line(self, solve: Solve) -> None:  # noqa: C901, PLR0912
        """Display solve results, statistics, and record achievements."""
        old_stats = SolveStatisticsReporter(self.cube_size, self.stack)

        self.stack_done.append(solve)
        self.stack = [*self.stack, solve]
        new_stats = SolveStatisticsReporter(self.cube_size, self.stack)

        self.clear_line(full=True)

        if solve.advanced:
            if solve.flag != DNF:
                if self.show_reconstruction:
                    self.console.print(solve.method_line, end='')
                if self.show_time_graph:
                    solve.time_graph()
                if self.show_tps_graph:
                    solve.tps_graph()
                if self.show_fluency_graph:
                    solve.fluency_graph()
                if self.show_recognition_graph:
                    solve.recognition_graph()
                if self.show_cheers:
                    self.console.print(solve.cheers())

                link = (
                    solve.link_term_timer
                    if not self.free_play
                    else solve.link_alg_cubing
                )
                self.console.print(
                    f'[localhost][link={ link }]'
                    f'Analysis #{ self.counter }:[/link][/localhost] '
                    f'{ solve.report_line }',
                )
            else:
                self.console.print(
                    f'[duration]Duration #{ self.counter }:[/duration]',
                    f'[time]{ format_time(self.elapsed_time) }[/time]',
                    '[dnf]DNF[/dnf]',
                )
                return

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

    async def start(self) -> bool:  # noqa: C901, PLR0912
        """
        Execute complete solve workflow from scramble to save.

        Returns:
            True to continue with next solve, False to quit.

        """
        self.init_solve()

        if self.scrambles:
            if self.scramble_index >= len(self.scrambles):
                self.console.print(
                    'All scrambles completed!',
                    style='success',
                )
                return False

            self.scramble = self.scrambles[self.scramble_index]
            self.scramble_index += 1

            cube = VCube(size=self.cube_size)
            cube.rotate(self.scramble)
        else:
            self.scramble, cube = scrambler(
                cube_size=self.cube_size,
                iterations=self.iterations,
                easy_cross=self.easy_cross,
                raw_scramble=self.raw_scramble,
                rng=self.rng,
            )

        if self.bluetooth_cube and not self.bluetooth_cube_is_solved:
            scramble = facelets_to_facelets_algorithm(
                self.bluetooth_cube_state,
                cube.state,
            )
            self.scramble_oriented = self.reorient(scramble)
        else:
            self.scramble_oriented = self.reorient(self.scramble)
        self.facelets_scrambled = cube.state

        self.start_line(cube)

        quit_solve = await self.scramble_solve()

        if quit_solve is not None:
            return quit_solve

        if self.countdown:
            await self.inspect_solve()
        else:
            await self.wait_solve()

        await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time

        flag: SolveFlag = ''
        moves = []
        if self.moves:
            if self.bluetooth_cube and not self.bluetooth_cube_is_solved:
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
                and self.bluetooth_interface.client
                and self.bluetooth_interface.client.name
            ) or '',
            session=self.session,
            solve_id=self.counter,
            cube_size=self.cube_size,
            moves=' '.join(moves),
        )

        solve.method_name = self.method
        solve.orientation = self.orientation_faces

        self.solve_line(solve)

        if not self.free_play:
            self.save_line(flag)

            quit_solve = await self.save_solve()

            if quit_solve:
                return False
        else:
            self.counter += 1

        return True
