import asyncio
import logging
import time
from datetime import datetime
from datetime import timezone

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.in_out import save_solves
from term_timer.interface import Interface
from term_timer.scrambler import scramble_moves
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import Statistics

logger = logging.getLogger(__name__)


class Timer(Interface):
    def __init__(self, *, cube_size: int,
                 iterations: int, easy_cross: bool,
                 session: str, free_play: bool,
                 show_cube: bool,
                 show_reconstruction: bool,
                 show_time_graph: bool,
                 countdown: int,
                 metronome: float,
                 stack: list[Solve]):

        self.set_state('init')

        self.cube_size = cube_size
        self.session = session
        self.free_play = free_play
        self.iterations = iterations
        self.easy_cross = easy_cross
        self.show_cube = show_cube
        self.show_reconstruction = show_reconstruction
        self.show_time_graph = show_time_graph
        self.countdown = countdown
        self.metronome = metronome
        self.stack = stack

        if self.free_play:
            self.console.print(
                '🔒 Mode Free Play is active, '
                'solves will not be recorded !',
                style='warning',
            )

    def handle_bluetooth_move(self, event):
        if self.state in {'start', 'scrambling'}:
            self.scrambled.append(event['move'])
            self.handle_scrambled(len(self.stack) + 1)

        elif self.state in {'inspecting', 'scrambled'}:
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
            self.console.print(str(cube), end='')

        self.console.print(
            f'[scramble]Scramble #{ len(self.stack) + 1 }:[/scramble]',
            f'[moves]{ self.scramble_oriented }[/moves]',
        )

        if self.bluetooth_interface:
            if self.countdown:
                self.console.print(
                    'Apply the scramble on the cube to start the inspection,',
                    '[b](q)[/b] to quit.',
                    end='', style='consign',
                )
            else:
                self.console.print(
                    'Apply the scramble on the cube to init the timer,',
                    '[b](q)[/b] to quit.',
                    end='', style='consign',
                )
        elif self.countdown:
            self.console.print(
                'Press any key once scrambled to start the inspection,',
                '[b](q)[/b] to quit.',
                end='', style='consign',
            )
        else:
            self.console.print(
                'Press any key once scrambled to start/stop the timer,',
                '[b](q)[/b] to quit.',
                end='', style='consign',
            )

    def save_line(self, flag: str) -> None:
        self.console.print(
            'Press any key to save and continue,',
            '[b](d)[/b] for DNF,' if flag != DNF else '[b](o)[/b] for OK',
            '[b](2)[/b] for +2,',
            '[b](z)[/b] to cancel,',
            '[b](q)[/b] to save and quit.',
            end='', style='consign',
        )

    def handle_solve(self, solve: Solve) -> None:
        old_stats = Statistics(self.stack)

        self.stack = [*self.stack, solve]
        new_stats = Statistics(self.stack)

        self.clear_line(full=True)

        if solve.raw_moves:
            if solve.flag != DNF:
                if self.show_reconstruction:
                    self.console.print(solve.method_line, end='')
                if self.show_time_graph:
                    solve.time_graph  # noqa B018
                self.console.print(
                    f'[analysis]Analysis #{ len(self.stack) }:[/analysis] '
                    f'{ solve.report_line }',
                )
            else:
                self.console.print(
                    f'[duration]Duration #{ len(self.stack) }:[/duration]',
                    f'[result]{ format_time(self.elapsed_time) }[/result]',
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
            f'[duration]Duration #{ len(self.stack) }:[/duration]',
            f'[result]{ format_time(self.elapsed_time) }[/result]',
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
        self.set_state('start')
        self.init_solve()

        self.scramble, cube = scrambler(
            cube_size=self.cube_size,
            iterations=self.iterations,
            easy_cross=self.easy_cross,
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

        if self.countdown:
            inspection_task = asyncio.create_task(self.inspection())

            if self.bluetooth_interface:
                tasks = [
                    asyncio.create_task(
                        self.getch('inspected', self.countdown),
                    ),
                    asyncio.create_task(self.solve_started_event.wait()),
                ]
                await self.wait_control(tasks)

                if not self.inspection_completed_event.is_set():
                    self.inspection_completed_event.set()
            else:
                await self.getch('inspected', self.countdown)
                self.inspection_completed_event.set()

            await inspection_task

        elif self.bluetooth_interface:
            tasks = [
                asyncio.create_task(self.getch('start')),
                asyncio.create_task(self.solve_started_event.wait()),
            ]
            await self.wait_control(tasks)

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
            datetime.now(tz=timezone.utc).timestamp(),  # noqa: UP017
            self.elapsed_time,
            str(self.scramble),
            flag=flag,
            timer='Term-Timer',
            device=(
                self.bluetooth_interface
                and self.bluetooth_interface.device.name
            ) or '',
            moves=' '.join(moves),
        )

        self.handle_solve(solve)

        if not self.free_play:
            self.set_state('saving')
            self.save_line(flag)

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
            if char == 'q':
                return False

        return True
