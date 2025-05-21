import asyncio
import logging
import sys

from cubing_algs.vcube import VCube

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import CubeNotFoundError
from term_timer.console import console

logger = logging.getLogger(__name__)

is_windows = sys.platform in {'win32', 'cygwin'}

if is_windows:
    import msvcrt
else:
    import termios


class Terminal:

    @staticmethod
    def clear_line(full) -> None:
        if full:
            print(f'\r{ " " * 100}\r', flush=True, end='')
        else:
            print('\r', end='')

    @staticmethod
    def beep() -> None:
        print('\a', end='', flush=True)


class Getcher:

    async def getch(self, mode, timeout: float | None = None) -> str:
        logger.info('Getch %s', mode)

        if is_windows:
            ch = await self.getch_windows(timeout)
        else:
            ch = await self.getch_unix(timeout)

        self.clear_line(full=True)

        logger.info('Getched: *%s*', ch)

        return ch

    async def getch_windows(self, timeout: float | None = None) -> str:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        ch = ''

        def windows_getch() -> None:
            try:
                if msvcrt.kbhit():
                    key_bytes = msvcrt.getch()
                    key_str = key_bytes.decode('utf-8', errors='replace')
                    if not future.done():
                        future.set_result(key_str)
                else:
                    loop.call_later(0.01, windows_getch)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

        loop.call_soon(windows_getch)

        try:
            if timeout is not None:
                ch = await asyncio.wait_for(future, timeout)
            else:
                ch = await future
        except asyncio.TimeoutError:  # noqa: UP041
            ch = ''
        except Exception:
            logger.exception('Error in getch (Windows)')
            ch = ''

        return ch

    async def getch_unix(self, timeout: float | None = None) -> str:
        fd = sys.stdin.fileno()

        old_settings = termios.tcgetattr(fd)
        term = termios.tcgetattr(fd)
        ch = ''

        try:
            term[3] &= ~(
                termios.ICANON | termios.ECHO |
                termios.IGNBRK | termios.BRKINT
            )
            termios.tcsetattr(fd, termios.TCSAFLUSH, term)

            loop = asyncio.get_running_loop()
            future = loop.create_future()

            def stdin_callback() -> None:
                try:
                    ch = sys.stdin.read(1)
                    if not future.done():
                        future.set_result(ch)
                except Exception as e:
                    if not future.done():
                        future.set_exception(e)

            loop.add_reader(fd, stdin_callback)

            try:
                if timeout is not None:
                    ch = await asyncio.wait_for(future, timeout)
                else:
                    ch = await future
            except asyncio.TimeoutError:  # noqa: UP041
                ch = ''
            except Exception:
                logger.exception('Error in getch (Unix)')
                ch = ''
            finally:
                if not loop.is_closed():
                    loop.remove_reader(fd)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return ch


class Bluetooth:

    bluetooth_queue = None
    bluetooth_cube = None
    bluetooth_interface = None
    bluetooth_consumer_ref = None
    bluetooth_hardware = {}

    facelets_received_event = asyncio.Event()
    hardware_received_event = asyncio.Event()

    async def bluetooth_connect(self) -> bool:
        self.bluetooth_queue = asyncio.Queue()

        try:
            self.bluetooth_interface = BluetoothInterface(
                self.bluetooth_queue,
            )

            console.print(
                '[bluetooth]📡Bluetooth:[/bluetooth] '
                'Scanning for Bluetooth cube for '
                f'{ self.bluetooth_interface.scan_timeout }s...',
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

            await self.bluetooth_interface.send_command('REQUEST_FACELETS')
            await self.bluetooth_interface.send_command('REQUEST_BATTERY')
            await self.bluetooth_interface.send_command('REQUEST_HARDWARE')

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
                    if self.facelets_received_event.is_set():
                        continue

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
                        char = await self.getch('reset cube')
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

                    self.handle_bluetooth_move(event)

    def handle_bluetooth_move(self, event):
        raise NotImplementedError


class Interface(Terminal, Getcher, Bluetooth):
    ...
