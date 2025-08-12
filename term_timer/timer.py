import logging

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.interface import SolveInterface
from term_timer.scrambler import scramble_moves
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import Statistics

logger = logging.getLogger(__name__)


class Timer(SolveInterface):
    def __init__(self, *,
                 cube_size: int,
                 iterations: int,
                 easy_cross: bool,
                 scramble: str,
                 session: str,
                 free_play: bool,
                 show_cube: bool,
                 show_reconstruction: bool,
                 show_tps_graph: bool,
                 show_time_graph: bool,
                 show_recognition_graph: bool,
                 countdown: int,
                 metronome: float,
                 stack: list[Solve]):
        super().__init__()

        self.set_state('configure')

        self.cube_size = cube_size
        self.session = session
        self.free_play = free_play
        self.iterations = iterations
        self.easy_cross = easy_cross
        self.raw_scramble = scramble
        self.show_cube = show_cube
        self.show_reconstruction = show_reconstruction
        self.show_tps_graph = show_tps_graph
        self.show_time_graph = show_time_graph
        self.show_recognition_graph = show_recognition_graph
        self.countdown = countdown
        self.metronome = metronome
        self.stack = stack

        self.counter = len(stack) + 1

        if self.free_play:
            self.console.print(
                '🔒 Mode Free Play is active, '
                'solves will not be recorded !',
                style='warning',
            )

    def start_line(self, cube) -> None:
        if self.show_cube:
            self.console.print(str(cube), end='')

        self.console.print(
            f'[scramble]Scramble #{ self.counter }:[/scramble]',
            f'[moves]{ self.scramble_oriented }[/moves]',
        )

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

    def save_line(self, flag: str) -> None:
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

    def solve_line(self, solve: Solve) -> None:
        old_stats = Statistics(self.stack)

        self.stack = [*self.stack, solve]
        new_stats = Statistics(self.stack)

        self.clear_line(full=True)

        if solve.advanced:
            if solve.flag != DNF:
                if self.show_reconstruction:
                    self.console.print(solve.method_line, end='')
                if self.show_time_graph:
                    solve.time_graph()
                if self.show_tps_graph:
                    solve.tps_graph()
                if self.show_recognition_graph:
                    solve.recognition_graph()
                self.console.print(
                    f'[localhost][link={ solve.link_term_timer }]'
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

    async def start(self) -> bool:
        self.init_solve()

        self.scramble, cube = scrambler(
            cube_size=self.cube_size,
            iterations=self.iterations,
            easy_cross=self.easy_cross,
            raw_scramble=self.raw_scramble,
        )

        if self.bluetooth_cube and not self.bluetooth_cube.is_solved:
            scramble = scramble_moves(
                cube.get_kociemba_facelet_positions(),
                self.bluetooth_cube.state,
            )
            self.scramble_oriented = self.reorient(scramble)
        else:
            self.scramble_oriented = self.reorient(self.scramble)
        self.facelets_scrambled = cube.get_kociemba_facelet_positions()

        self.start_line(cube)

        quit_solve = await self.scramble_solve()

        if quit_solve:
            return False

        if self.countdown:
            await self.inspect_solve()
        else:
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
            session=self.session,
            solve_id=self.counter,
            cube_size=self.cube_size,
            moves=' '.join(moves),
        )

        self.solve_line(solve)

        if not self.free_play:
            self.save_line(flag)

            quit_solve = await self.save_solve()

            if quit_solve:
                return False

        return True
