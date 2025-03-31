import asyncio
import sys
import termios
import time
import tty

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import CubeNotFoundError
from term_timer.console import console
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.magic_cube import Cube
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import Statistics


class Timer:
    def __init__(self, *, cube_size: int,  # noqa: PLR0913
                 iterations: int, easy_cross: bool,
                 free_play: bool, show_cube: bool,
                 countdown: int, metronome: float,
                 stack: list[Solve]):
        self.start_time = 0
        self.end_time = 0
        self.elapsed_time = 0
        self.move_count = 0
        self.state = 'init'

        self.cube_size = cube_size
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
        self.bluetooth_facelets = ''

        self.stack = stack

        self.stop_event = asyncio.Event()
        self.scramble_completed_event = asyncio.Event()
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

            await self.bluetooth_interface.__aenter__(device)

            self.bluetooth_hardware['device_name'] = self.bluetooth_interface.device.name

            self.clear_line(full=True)
            console.print(
                '[bluetooth]🔗Bluetooth:[/bluetooth] '
                f'{ self.bluetooth_hardware['device_name'] } '
                'connected successfully !',
                end='',
            )

            self.facelets_received_event.clear()
            self.hardware_received_event.clear()

            self.bluetooth_consumer_ref = asyncio.create_task(
                self.bluetooth_consumer(),
            )

            await self.bluetooth_interface.send_command('REQUEST_HARDWARE')
            await self.bluetooth_interface.send_command('REQUEST_FACELETS')
            await self.bluetooth_interface.send_command('REQUEST_BATTERY')

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        self.facelets_received_event.wait(),
                        self.hardware_received_event.wait(),
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
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
                f'[result]{ self.bluetooth_hardware['label'] } '
                'initialized successfully ![/result]',
            )
            return True
        except CubeNotFoundError:
            self.clear_line(full=True)
            console.print(
                '[bluetooth]😥Bluetooth:[/bluetooth] '
                '[warning]No Bluetooth cube could be found. '
                'Running in manual mode.[/warning]',
            )
            return False

    async def bluetooth_disconnect(self) -> None:
        if self.bluetooth_interface and self.bluetooth_interface.device:
            console.print(
                '[bluetooth]🔗 Bluetooth[/bluetooth] '
                f'{ self.bluetooth_hardware["label"] } disconnecting...',
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
                    self.bluetooth_hardware['hardware_name'] = event['hardware_name']
                    self.bluetooth_hardware['hardware_version'] = event['hardware_version']
                    self.bluetooth_hardware['software_version'] = event['software_version']
                    self.bluetooth_hardware['gyroscope_supported'] = event['gyroscope_supported']

                    # TODO(me): factorize
                    device_label = (
                        f"{ self.bluetooth_hardware['device_name'] }"
                        f"v{ self.bluetooth_hardware['hardware_version'] }"
                    )
                    if 'battery_level' in self.bluetooth_hardware:
                        device_label += f" ({ self.bluetooth_hardware['battery_level'] }%)"
                    self.bluetooth_hardware['label'] = device_label

                    self.hardware_received_event.set()
                if event_name == 'battery':
                    self.bluetooth_hardware['battery_level'] = event['level']

                    # TODO(me): factorize
                    device_label = (
                        f"{ self.bluetooth_hardware['device_name'] }"
                        f"v{ self.bluetooth_hardware['hardware_version'] }"
                    )
                    if 'battery_level' in self.bluetooth_hardware:
                        device_label += f" ({ self.bluetooth_hardware['battery_level'] }%)"
                    self.bluetooth_hardware['label'] = device_label

                elif event_name == 'facelets':
                    self.bluetooth_facelets = event['facelets']
                    self.bluetooth_cube = Cube(3, event['facelets'])

                    if not self.bluetooth_cube.is_done():
                        self.clear_line(full=True)
                        console.print(
                            '[bluetooth]🫤Bluetooth:[/bluetooth] '
                            '[warning]Cube is not in solved state[/warning]',
                        )
                    self.facelets_received_event.set()
                elif event_name == 'move':
                    if self.bluetooth_cube:
                        self.bluetooth_cube.rotate([event['move']])

                    if self.state == 'solving':
                        self.move_count += 1

                        if not self.stop_event.is_set() and self.bluetooth_cube.is_done():
                            self.end_time = time.perf_counter_ns()
                            self.stop_event.set()
                            self.solve_completed_event.set()

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

    async def inspection(self) -> None:
        state = 0
        self.stop_event.clear()
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
        self.stop_event.clear()
        self.solve_completed_event.clear()

        self.start_time = time.perf_counter_ns()
        self.end_time = 0
        self.move_count = 0
        self.elapsed_time = 0
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

    @staticmethod
    def start_line() -> None:
        console.print(
            'Press any key to start/stop the timer,',
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

    def handle_solve(self, solve: Solve) -> None:
        old_stats = Statistics(self.stack)

        self.stack = [*self.stack, solve]
        new_stats = Statistics(self.stack)

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

            if self.move_count:
                extra += f' [move]{ self.move_count } moves[/move]'

        elif self.move_count:
            extra += f'[move]{ self.move_count } moves[/move]'

        self.clear_line(full=False)
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
        scramble, cube = scrambler(
            cube_size=self.cube_size,
            iterations=self.iterations,
            easy_cross=self.easy_cross,
        )

        console.print(
            f'[scramble]Scramble #{ len(self.stack) + 1 }:[/scramble]',
            f'[moves]{ " ".join(scramble) }[/moves]',
        )

        if self.show_cube:
            console.print(str(cube), end='')

        self.start_line()

        char = await self.getch()

        if char == 'q':
            return False

        if self.countdown:
            inspection_task = asyncio.create_task(self.inspection())

            await self.getch(self.countdown)

            self.stop_event.set()
            await inspection_task

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

        solve = Solve(
            self.start_time,
            self.end_time,
            ' '.join(scramble),
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
            elif char == 'q':
                return False

        return True
