import asyncio
import logging
import time
from datetime import datetime
from datetime import timezone

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.size import compress_moves

from term_timer.config import CUBE_ORIENTATION
from term_timer.console import console
from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
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
        self.start_time = 0
        self.end_time = 0
        self.elapsed_time = 0
        self.scramble = []
        self.scramble_oriented = []
        self.scrambled = []
        self.moves = []
        self.state = 'init'

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
        self.facelets_scrambled = ''
        self.cube_orientation = CUBE_ORIENTATION

        self.stop_event = asyncio.Event()
        self.scramble_completed_event = asyncio.Event()
        self.solve_started_event = asyncio.Event()
        self.solve_completed_event = asyncio.Event()

        self.save_moves = []
        self.save_gesture = ''
        self.save_gesture_event = asyncio.Event()

        if self.free_play:
            console.print(
                '🔒 Mode Free Play is active, '
                'solves will not be recorded !',
                style='warning',
            )

    def handle_bluetooth_move(self, event):
        if self.state in {'start', 'scrambling'}:
            self.scrambled.append(event['move'])

            self.handle_scrambled()

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
                    not self.stop_event.is_set()
                    and self.bluetooth_cube.is_solved
            ):
                self.end_time = event['clock']
                self.stop_event.set()
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

    async def inspection(self) -> None:
        self.clear_line(full=True)

        self.set_state('inspecting')
        self.stop_event.clear()

        state = 0
        inspection_start_time = time.perf_counter_ns()

        while not self.stop_event.is_set():
            elapsed_time = time.perf_counter_ns() - inspection_start_time
            elapsed_seconds = elapsed_time / SECOND

            remaining_time = round(self.countdown - elapsed_seconds, 1)

            if int(remaining_time // 1) != state:
                state = int(remaining_time // 1)
                if state in {2, 1, 0}:
                    self.beep()

            self.clear_line(full=False)
            console.print(
                '[inspection]Inspection :[/inspection]',
                f'[result]{ remaining_time }[/result]',
                end='',
            )

            await asyncio.sleep(0.01)

    async def stopwatch(self) -> None:
        self.clear_line(full=True)

        self.stop_event.clear()
        self.solve_completed_event.clear()

        self.start_time = time.perf_counter_ns()
        self.end_time = 0
        self.elapsed_time = 0

        self.set_state('solving', self.start_time)

        tempo_elapsed = 0

        while not self.stop_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time
            new_tempo = int(elapsed_time / (SECOND * self.metronome or 1))

            style = 'timer_base'
            if elapsed_time > 50 * SECOND:
                style = 'timer_50'
            elif elapsed_time > 45 * SECOND:
                style = 'timer_45'
            elif elapsed_time > 40 * SECOND:
                style = 'timer_40'
            elif elapsed_time > 35 * SECOND:
                style = 'timer_35'
            elif elapsed_time > 30 * SECOND:
                style = 'timer_30'
            elif elapsed_time > 25 * SECOND:
                style = 'timer_25'
            elif elapsed_time > 20 * SECOND:
                style = 'timer_20'
            elif elapsed_time > 15 * SECOND:
                style = 'timer_15'
            elif elapsed_time > 10 * SECOND:
                style = 'timer_10'
            elif elapsed_time > 5 * SECOND:
                style = 'timer_05'

            if tempo_elapsed != new_tempo:
                tempo_elapsed = new_tempo
                if self.metronome:
                    self.beep()

            self.clear_line(full=False)
            console.print(
                f'[{ style }]Go Go Go:[/{ style }]',
                f'[result]{ format_time(elapsed_time) }[/result]',
                end='',
            )

            await asyncio.sleep(0.01)

        self.set_state('stop')

    def start_line(self) -> None:
        if self.bluetooth_interface:
            if self.countdown:
                console.print(
                    'Apply the scramble on the cube to start the inspection,',
                    '[b](q)[/b] to quit.',
                    end='', style='consign',
                )
            else:
                console.print(
                    'Apply the scramble on the cube to init the timer,',
                    '[b](q)[/b] to quit.',
                    end='', style='consign',
                )
        elif self.countdown:
            console.print(
                'Press any key once scrambled to start the inspection,',
                '[b](q)[/b] to quit.',
                end='', style='consign',
            )
        else:
            console.print(
                'Press any key once scrambled to start/stop the timer,',
                '[b](q)[/b] to quit.',
                end='', style='consign',
            )

    @staticmethod
    def save_line(flag: str) -> None:
        console.print(
            'Press any key to save and continue,',
            '[b](d)[/b] for DNF,' if flag != DNF else '[b](o)[/b] for OK',
            '[b](2)[/b] for +2,',
            '[b](z)[/b] to cancel,',
            '[b](q)[/b] to save and quit.',
            end='', style='consign',
        )

    def reorient(self, algorithm: Algorithm) -> Algorithm:
        if self.cube_orientation:
            new_algorithm = self.cube_orientation + algorithm
            return new_algorithm.transform(
                degrip_full_moves,
                remove_final_rotations,
            )
        return algorithm

    def handle_scrambled(self):
        if self.bluetooth_cube.state == self.facelets_scrambled:
            self.scramble_completed_event.set()
            self.beep()
            out = (
                '[result]Cube scrambled and ready to be solved ![/result] '
                '[consign]Start solving to launch the timer.[/consign]'
            )
            full_clear = True
        else:
            out = ''
            algo = self.reorient(
                parse_moves(self.scrambled).transform(compress_moves),
            )
            p_algo = self.reorient(
                parse_moves(self.scrambled[:-1]).transform(compress_moves),
            )

            on_good_way = True
            for i, move in enumerate(algo):
                expected = self.scramble_oriented[i]
                style = 'move'
                if expected != move or not on_good_way:
                    on_good_way = False
                    style = 'warning'
                    if expected[0] == move[0]:
                        style = 'caution'

                out += f'[{ style }]{ move }[/{ style }] '
            full_clear = len(algo) < len(p_algo) or len(algo) <= 1

        self.clear_line(full=full_clear)

        console.print(
            f'[scramble]Scramble #{ len(self.stack) + 1 }:[/scramble]',
            out,
            end='',
        )

    def handle_solve(self, solve: Solve) -> None:
        old_stats = Statistics(self.stack)

        self.stack = [*self.stack, solve]
        new_stats = Statistics(self.stack)

        self.clear_line(full=True)

        if solve.raw_moves:
            if solve.flag != DNF:
                if self.show_reconstruction:
                    console.print(solve.method_line, end='')
                if self.show_time_graph:
                    solve.time_graph  # noqa B018
                console.print(
                    f'[analysis]Analysis #{ len(self.stack) }:[/analysis] '
                    f'{ solve.report_line }',
                )
            else:
                console.print(
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

        console.print(
            f'[duration]Duration #{ len(self.stack) }:[/duration]',
            f'[result]{ format_time(self.elapsed_time) }[/result]',
            extra,
        )

        if new_stats.total > 1:
            mc = 10 + len(str(len(self.stack))) - 1
            if new_stats.best < old_stats.best:
                console.print(
                    f'[record]:rocket:{ "New PB !".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.best) }[/best]',
                    format_delta(new_stats.best - old_stats.best),
                )

            if new_stats.ao5 < old_stats.best_ao5:
                console.print(
                    f'[record]:boom:{ "Best Ao5".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao5) }[/best]',
                    format_delta(new_stats.ao5 - old_stats.best_ao5),
                )

            if new_stats.ao12 < old_stats.best_ao12:
                console.print(
                    f'[record]:muscle:{ "Best Ao12".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao12) }[/best]',
                    format_delta(new_stats.ao12 - old_stats.best_ao12),
                )

            if new_stats.ao100 < old_stats.best_ao100:
                console.print(
                    f'[record]:crown:{ "Best Ao100".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao100) }[/best]',
                    format_delta(new_stats.ao100 - old_stats.best_ao100),
                )

            if new_stats.ao1000 < old_stats.best_ao1000:
                console.print(
                    f'[record]:trophy:{ "Best Ao1000".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao1000) }[/best]',
                    format_delta(new_stats.ao1000 - old_stats.best_ao1000),
                )

    def set_state(self, state, extra=''):
        self.state = state
        logger.info('Passing to state %s %s', state.upper(), extra)

    async def start(self) -> bool:
        self.set_state('start')
        self.moves = []

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

        if self.show_cube:
            console.print(str(cube), end='')

        console.print(
            f'[scramble]Scramble #{ len(self.stack) + 1 }:[/scramble]',
            f'[moves]{ self.scramble_oriented }[/moves]',
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

        if self.countdown:
            inspection_task = asyncio.create_task(self.inspection())

            if self.bluetooth_interface:

                _done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(
                            self.getch(
                                'inspected', self.countdown,
                            ),
                        ),
                        asyncio.create_task(self.solve_started_event.wait()),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()

                await asyncio.gather(*pending, return_exceptions=True)

                if not self.solve_started_event.is_set():
                    self.solve_started_event.set()
                if not self.stop_event.is_set():
                    self.stop_event.set()
            else:
                await self.getch('inspected', self.countdown)
                self.solve_started_event.set()
                self.stop_event.set()

            await inspection_task

        elif self.bluetooth_interface:
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

        flag = ''
        moves = []
        if self.moves:
            first_time = self.moves[0]['time']
            for move in self.moves:
                timing = int((move['time'] - first_time) / MS_TO_NS_FACTOR)
                moves.append(f'{ move["move"] }@{ timing }')
            if not self.bluetooth_cube.is_solved:
                flag = DNF

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
                self.save_gesture_event.clear()

                tasks = [
                    asyncio.create_task(self.getch('save')),
                    asyncio.create_task(self.save_gesture_event.wait()),
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
                    self.save_gesture_event.set()
                else:
                    self.clear_line(full=True)
                    char = self.save_gesture
                self.save_moves = []
                self.save_gesture = ''
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
                console.print(
                    f'[duration]Duration #{ len(self.stack) }:[/duration] '
                    f'[warning]{ save_string }[/warning]',
                )
            if char == 'q':
                return False

        return True
