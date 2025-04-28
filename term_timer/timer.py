import asyncio
import sys
import termios
import time
import tty
from datetime import datetime
from datetime import timezone

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.size import compress_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import CubeNotFoundError
from term_timer.config import CUBE_ORIENTATION
from term_timer.console import console
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.in_out import save_solves
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import Statistics


class Timer:
    def __init__(self, *, cube_size: int,
                 iterations: int, easy_cross: bool,
                 session: str, free_play: bool,
                 show_cube: bool, countdown: int,
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
        self.countdown = countdown
        self.metronome = metronome

        self.bluetooth_cube = None
        self.bluetooth_queue = None
        self.bluetooth_interface = None
        self.bluetooth_consumer_ref = None
        self.bluetooth_hardware = {}

        self.stack = stack
        self.facelets_scrambled = ''
        self.cube_orientation = CUBE_ORIENTATION

        self.stop_event = asyncio.Event()
        self.scramble_completed_event = asyncio.Event()
        self.solve_started_event = asyncio.Event()
        self.solve_completed_event = asyncio.Event()

        self.facelets_received_event = asyncio.Event()
        self.hardware_received_event = asyncio.Event()

        if self.free_play:
            console.print(
                '🔒 Mode Free Play is active, '
                'solves will not be recorded !',
                style='warning',
            )

    async def bluetooth_connect(self) -> bool:
        self.bluetooth_queue = asyncio.Queue()

        try:
            self.bluetooth_interface = BluetoothInterface(
                self.bluetooth_queue,
            )

            console.print(
                '[bluetooth]📡Bluetooth:[/bluetooth] '
                'Scanning for Bluetooth cube for '
                f'{ self.bluetooth_interface.scan_timeout}s...',
                end='',
            )

            device = await self.bluetooth_interface.scan()

            await self.bluetooth_interface.__aenter__(device)  # noqa: PLC2801

            self.clear_line(full=True)
            console.print(
                '[bluetooth]🔗Bluetooth:[/bluetooth] '
                f'{ self.bluetooth_device_label } '
                'connected successfully !',
                end='',
            )

            self.facelets_received_event.clear()
            self.hardware_received_event.clear()

            self.bluetooth_consumer_ref = asyncio.create_task(
                self.bluetooth_consumer(),
            )

            await self.bluetooth_interface.send_command('REQUEST_BATTERY')
            await self.bluetooth_interface.send_command('REQUEST_HARDWARE')
            await self.bluetooth_interface.send_command('REQUEST_FACELETS')

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        self.facelets_received_event.wait(),
                        self.hardware_received_event.wait(),
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:  # noqa: UP041
                self.clear_line(full=True)
                console.print(
                    '[bluetooth]😱Bluetooth:[/bluetooth] '
                    '[warning]Cube could not be initialized properly. '
                    'Running in manual mode.[/warning]',
                )
                return False

            self.clear_line(full=True)

            console.print(
                '[bluetooth]🤓Bluetooth:[/bluetooth] '
                f'[result]{ self.bluetooth_device_label } '
                'initialized successfully ![/result]',
            )
        except CubeNotFoundError:
            self.clear_line(full=True)
            console.print(
                '[bluetooth]😥Bluetooth:[/bluetooth] '
                '[warning]No Bluetooth cube could be found. '
                'Running in manual mode.[/warning]',
            )
            return False
        else:
            return True

    async def bluetooth_disconnect(self) -> None:
        if self.bluetooth_interface and self.bluetooth_interface.device:
            console.print(
                '[bluetooth]🔗 Bluetooth[/bluetooth] '
                f'{ self.bluetooth_device_label } disconnecting...',
            )
            await self.bluetooth_interface.__aexit__(None, None, None)

    async def bluetooth_consumer(self) -> None:
        while True:
            events = await self.bluetooth_queue.get()

            if events is None:
                break

            for event in events:
                event_name = event['event']

                if event_name == 'hardware':
                    event.pop('event')
                    event.pop('timestamp')
                    self.bluetooth_hardware.update(event)
                    self.hardware_received_event.set()

                if event_name == 'battery':
                    self.bluetooth_hardware['battery_level'] = event['level']

                elif event_name == 'facelets':
                    self.bluetooth_cube = VCube(event['facelets'])

                    if not self.bluetooth_cube.is_solved:
                        self.clear_line(full=True)
                        console.print(
                            '[bluetooth]🫤Bluetooth:[/bluetooth] '
                            '[warning]Cube is not in solved state[/warning]',
                        )
                        console.print(
                            '[bluetooth]❓Bluetooth:[/bluetooth] '
                            '[consign]Is the cube is really solved ? '
                            '[b](y)[/b] to reset the cube.[/consign]',
                        )
                        char = await self.getch()
                        if char == 'y':
                            for command in ['RESET', 'FACELETS']:
                                await self.bluetooth_interface.send_command(
                                    f'REQUEST_{ command }',
                                )
                            continue

                        console.print(
                            '[warning]Quit until solved[/warning]',
                        )
                        await self.bluetooth_queue.put(None)
                        continue

                    self.facelets_received_event.set()
                elif event_name == 'move':
                    if not self.bluetooth_cube:
                        continue

                    self.bluetooth_cube.rotate(event['move'])

                    if self.state in {'init', 'scrambling'}:
                        self.scrambled.append(event['move'])

                        self.handle_scrambled()

                    elif self.state in {'inspecting', 'scrambled'}:
                        self.moves.append(
                            {
                                'move': event['move'],
                                'time': event['cubeTimestamp'],
                            },
                        )
                        self.solve_started_event.set()

                    elif self.state == 'solving':
                        self.moves.append(
                            {
                                'move': event['move'],
                                'time': event['cubeTimestamp'],
                            },
                        )

                        if (
                                not self.stop_event.is_set()
                                and self.bluetooth_cube.is_solved
                        ):
                            self.end_time = time.perf_counter_ns()
                            self.stop_event.set()
                            self.solve_completed_event.set()

    @property
    def bluetooth_device_label(self):
        device_label = self.bluetooth_interface.device.name

        if 'hardware_version' in self.bluetooth_hardware:
            device_label += f"v{ self.bluetooth_hardware['hardware_version'] }"

        battery_level = self.bluetooth_hardware.get('battery_level')
        if battery_level:
            if battery_level <= 15:
                device_label += f' ([warning]{ battery_level }[/warning]%)'
            else:
                device_label += f' ({ battery_level }%)'

        return device_label

    async def getch(self, timeout: float | None = None) -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        ch = ''

        try:
            tty.setcbreak(fd)

            loop = asyncio.get_event_loop()
            future = loop.create_future()

            def stdin_callback() -> None:
                if not future.done():
                    ch = sys.stdin.read(1)
                    future.set_result(ch)

            loop.add_reader(fd, stdin_callback)

            try:
                if timeout is not None:
                    await asyncio.wait_for(future, timeout)
                else:
                    await future

                ch = future.result()
            except asyncio.TimeoutError:  # noqa UP041
                ch = ''
            finally:
                loop.remove_reader(fd)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        self.clear_line(full=True)

        return ch

    @staticmethod
    def clear_line(full) -> None:
        if full:
            print(f'\r{ " " * 100}\r', flush=True, end='')
        else:
            print('\r', end='')

    @staticmethod
    def beep() -> None:
        print('\a', end='', flush=True)

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

    async def inspection(self) -> None:
        self.clear_line(full=True)

        self.state = 'inspecting'
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
        self.scrambled = []
        self.state = 'solving'

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
    def save_line() -> None:
        console.print(
            'Press any key to save and continue,',
            '[b](d)[/b] for DNF,',
            '[b](2)[/b] for +2,',
            '[b](z)[/b] to cancel,',
            '[b](q)[/b] to save and quit.',
            end='', style='consign',
        )

    def reorient(self, algorithm: Algorithm) -> Algorithm:
        if self.cube_orientation:
            new_algorithm = self.cube_orientation + algorithm
            new_algorithm = new_algorithm.transform(
                degrip_full_moves,
                remove_final_rotations,
            )
        return new_algorithm

    def handle_solve(self, solve: Solve) -> None:
        old_stats = Statistics(self.stack)

        self.stack = [*self.stack, solve]
        new_stats = Statistics(self.stack)

        self.clear_line(full=True)

        if solve.raw_moves:
            console.print(solve.method_line, end='')
            console.print(
                f'[analysis]Analysis #{ len(self.stack) }:[/analysis] '
                f'{ solve.report_line }',
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

    async def start(self) -> bool:
        self.moves = []

        self.scramble, cube = scrambler(
            cube_size=self.cube_size,
            iterations=self.iterations,
            easy_cross=self.easy_cross,
        )
        self.scramble_oriented = self.reorient(self.scramble)
        self.facelets_scrambled = cube.get_kociemba_facelet_positions()

        if self.show_cube:
            console.print(str(cube), end='')

        console.print(
            f'[scramble]Scramble #{ len(self.stack) + 1 }:[/scramble]',
            f'[moves]{ self.scramble_oriented }[/moves]',
        )

        self.state = 'scrambling'
        self.scrambled = []
        self.start_line()

        if self.bluetooth_interface:
            self.scramble_completed_event.clear()

            tasks = [
                asyncio.create_task(self.getch()),
                asyncio.create_task(self.scramble_completed_event.wait()),
            ]
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            char = ''
            if tasks[0] in done:
                char = tasks[0].result()
                self.scramble_completed_event.set()
        else:
            char = await self.getch()

        if char == 'q':
            return False

        self.state = 'scrambled'
        self.solve_started_event.clear()

        if self.countdown:
            inspection_task = asyncio.create_task(self.inspection())

            if self.bluetooth_interface:

                _done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(self.getch(self.countdown)),
                        asyncio.create_task(self.solve_started_event.wait()),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()

                if not self.solve_started_event.is_set():
                    self.solve_started_event.set()
                if not self.stop_event.is_set():
                    self.stop_event.set()
            else:
                await self.getch(self.countdown)
                self.solve_started_event.set()
                self.stop_event.set()

            await inspection_task

        elif self.bluetooth_interface:
            _done, pending = await asyncio.wait(
                [
                    asyncio.create_task(self.getch()),
                    asyncio.create_task(self.solve_started_event.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            if not self.solve_started_event.is_set():
                self.solve_started_event.set()

        stopwatch_task = asyncio.create_task(self.stopwatch())

        if self.bluetooth_interface:
            _done, pending = await asyncio.wait(
                [
                    asyncio.create_task(self.getch()),
                    asyncio.create_task(self.solve_completed_event.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            if not self.stop_event.is_set():
                self.end_time = time.perf_counter_ns()
                self.stop_event.set()
        else:
            await self.getch()
            self.end_time = time.perf_counter_ns()
            self.stop_event.set()

        await stopwatch_task

        self.elapsed_time = self.end_time - self.start_time

        moves = []

        if self.moves:
            first_time = self.moves[0]['time']
            for move in self.moves:
                moves.append(f'{ move["move"] }@{ move["time"] - first_time }')

        solve = Solve(
            datetime.now(tz=timezone.utc).timestamp(),  # noqa: UP017
            self.elapsed_time,
            str(self.scramble),
            timer='Term-Timer',
            device=(
                self.bluetooth_interface
                and self.bluetooth_interface.device.name
            ) or '',
            moves=' '.join(moves),
        )

        self.handle_solve(solve)

        if not self.free_play:
            self.save_line()

            char = await self.getch()

            if char == 'd':
                self.stack[-1].flag = DNF
            elif char == '2':
                self.stack[-1].flag = PLUS_TWO
            elif char == 'z':
                self.stack.pop()

            save_solves(
                self.cube_size,
                self.session,
                self.stack,
            )

            if char == 'q':
                return False

        return True
