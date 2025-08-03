import asyncio
import logging

from cubing_algs.vcube import VCube

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import CubeNotFoundError

logger = logging.getLogger(__name__)


class Bluetooth:

    def __init__(self):
        super().__init__()

        self.moves = []

        self.bluetooth_queue = None
        self.bluetooth_cube = None
        self.bluetooth_interface = None
        self.bluetooth_consumer_ref = None
        self.bluetooth_hardware = {}

        self.facelets_received_event = asyncio.Event()
        self.hardware_received_event = asyncio.Event()

    async def bluetooth_connect(self) -> bool:
        self.bluetooth_queue = asyncio.Queue()

        try:
            self.bluetooth_interface = BluetoothInterface(
                self.bluetooth_queue,
            )

            self.console.print(
                '[bluetooth]📡Bluetooth:[/bluetooth] '
                'Scanning for Bluetooth cube for '
                f'{ self.bluetooth_interface.scan_timeout }s...',
                end='',
            )

            device = await self.bluetooth_interface.scan()

            await self.bluetooth_interface.__aenter__(device)  # noqa: PLC2801

            self.clear_line(full=True)
            self.console.print(
                '[bluetooth]🔗Bluetooth:[/bluetooth] '
                f'{ self.bluetooth_device_label } '
                'connected successfully !',
                end='',
            )

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
            except asyncio.TimeoutError:  # noqa: UP041
                self.clear_line(full=True)
                self.console.print(
                    '[bluetooth]😱Bluetooth:[/bluetooth] '
                    '[warning]Cube could not be initialized properly. '
                    'Running in manual mode.[/warning]',
                )
                return False

            self.clear_line(full=True)

            self.console.print(
                '[bluetooth]🤓Bluetooth:[/bluetooth] '
                f'[result]{ self.bluetooth_device_label } '
                'initialized successfully ![/result]',
            )
        except CubeNotFoundError:
            self.clear_line(full=True)
            self.console.print(
                '[bluetooth]😥Bluetooth:[/bluetooth] '
                '[warning]No Bluetooth cube could be found. '
                'Running in manual mode.[/warning]',
            )
            return False
        else:
            return True

    async def bluetooth_disconnect(self) -> None:
        if self.bluetooth_interface and self.bluetooth_interface.device:
            self.console.print(
                '[bluetooth]🔗 Bluetooth[/bluetooth] '
                f'{ self.bluetooth_device_label } disconnecting...',
            )
            await self.bluetooth_interface.__aexit__(None, None, None)

    @property
    def bluetooth_device_label(self) -> str:
        device_label = self.bluetooth_interface.device.name

        if 'hardware_version' in self.bluetooth_hardware:
            device_label += f'v{ self.bluetooth_hardware["hardware_version"] }'

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

                elif event_name == 'battery':
                    self.bluetooth_hardware['battery_level'] = event['level']

                elif event_name == 'facelets':
                    if self.facelets_received_event.is_set():
                        continue

                    self.bluetooth_cube = VCube(event['facelets'])

                    if not self.bluetooth_cube.is_solved:
                        self.clear_line(full=True)
                        self.console.print(
                            '[bluetooth]🫤Bluetooth:[/bluetooth] '
                            '[warning]Cube is not in solved state[/warning]',
                        )
                        self.console.print(
                            '[bluetooth]❓Bluetooth:[/bluetooth] '
                            '[consign]Is the cube is really solved ? '
                            '[key](y)[/key] to reset the cube.[/consign]',
                        )
                        char = await self.getch('reset cube')
                        if char == 'y':
                            for command in ['RESET', 'FACELETS']:
                                await self.bluetooth_interface.send_command(
                                    f'REQUEST_{ command }',
                                )
                            continue

                        self.console.print(
                            'Quit until solved',
                            style='warning',
                        )
                        await self.bluetooth_queue.put(None)
                        continue

                    self.facelets_received_event.set()

                elif event_name == 'move':
                    if not self.bluetooth_cube:
                        continue

                    self.bluetooth_cube.rotate(event['move'])

                    self.handle_bluetooth_move(event)

    def handle_bluetooth_move(self, event) -> None:
        if self.state in {'start', 'scrambling'}:
            self.scrambled += event['move']
            self.handle_scrambled()

        elif self.state == 'scrambled':
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
            self.handle_save_gestures(
                event['move'],
                event['clock'],
            )
