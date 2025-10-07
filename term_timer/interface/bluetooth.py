import asyncio
import logging
from typing import TYPE_CHECKING
from typing import TypedDict

from cubing_algs.vcube import VCube
from rich.console import Console as RichConsole

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.types import EventDict
from term_timer.config import BLUETOOTH_CONFIG
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.exceptions import CubeNotFoundError

logger = logging.getLogger(__name__)


class MoveInfo(TypedDict):
    """
    Representing a move with timing information.
    """
    move: str
    time: int


class Bluetooth:
    """Mixin providing Bluetooth cube integration."""

    if TYPE_CHECKING:
        # Attributes from State mixin
        state: str
        # Attributes from Console mixin
        console: RichConsole
        # Attributes from StopWatch mixin
        start_time: int
        end_time: int
        solve_started_event: asyncio.Event
        solve_completed_event: asyncio.Event

        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None: ...
        # Methods from Scrambler mixin
        def handle_scrambled(self, timed_move: str) -> None: ...
        # Methods from Gesture mixin
        def handle_save_gestures(self, move: str) -> None: ...

    def __init__(self) -> None:
        super().__init__()

        self.moves: list[MoveInfo] = []

        self.bluetooth_queue: asyncio.Queue[
            list[EventDict] | None
        ] | None = None
        self.bluetooth_cube: VCube | None = None
        self.bluetooth_interface: BluetoothInterface | None = None
        self.bluetooth_consumer_ref: asyncio.Task[None] | None = None
        self.bluetooth_hardware: dict[str, str | int] = {}

        self.facelets_received_event = asyncio.Event()
        self.hardware_received_event = asyncio.Event()

    async def bluetooth_connect(self) -> bool:
        """
        Connect to a Bluetooth cube.
        """
        address = BLUETOOTH_CONFIG.get('address', '')

        self.bluetooth_queue = asyncio.Queue()

        try:
            self.bluetooth_interface = BluetoothInterface(
                self.bluetooth_queue,
            )
            if not address:
                self.console.print(
                    '[bluetooth]📡Bluetooth:[/bluetooth] '
                    'Scanning for Bluetooth cube for '
                    f'{ self.bluetooth_interface.scan_timeout }s...',
                    end='',
                )

                device = await self.bluetooth_interface.scan()
                if device:
                    address = device.address
            else:
                self.console.print(
                    '[bluetooth]📡Bluetooth:[/bluetooth] '
                    'Connecting to Bluetooth cube address '
                    f'[b]{ address }[/b]...',
                    end='',
                )

            await self.bluetooth_interface.__aenter__(address)  # noqa: PLC2801

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
        """
        Disconnect from the Bluetooth cube if connected.
        """
        if (
                self.bluetooth_interface
                and self.bluetooth_interface.client
                and self.bluetooth_interface.client.is_connected
        ):
            self.console.print(
                '[bluetooth]🔗 Bluetooth[/bluetooth] '
                f'{ self.bluetooth_device_label } disconnecting...',
            )
            await self.bluetooth_interface.__aexit__(None, None, None)

    @property
    def bluetooth_device_label(self) -> str:
        """
        Get a formatted label for the connected Bluetooth device.
        """
        if not self.bluetooth_interface or not self.bluetooth_interface.client:
            return ''

        device_label = self.bluetooth_interface.client.name

        if 'hardware_version' in self.bluetooth_hardware:
            device_label += f'v{ self.bluetooth_hardware["hardware_version"] }'

        battery_level = self.bluetooth_hardware.get('battery_level')
        if isinstance(battery_level, int):
            if battery_level <= 15:
                device_label += f' ([warning]{ battery_level }[/warning]%)'
            else:
                device_label += f' ({ battery_level }%)'

        return device_label

    async def bluetooth_consumer(self) -> None:
        """
        Consume events from the Bluetooth queue and process them.
        """
        if not self.bluetooth_queue:
            return

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

                    self.facelets_received_event.set()

                elif event_name == 'move':
                    if not self.bluetooth_cube:
                        continue

                    self.bluetooth_cube.rotate(event['move'])

                    self.handle_bluetooth_move(event)

    def handle_bluetooth_move(self, event: EventDict) -> None:
        """
        Handle a move event from the Bluetooth cube.
        """
        move = event.get('move')
        clock = event.get('clock')

        if not isinstance(move, str) or not isinstance(clock, int):
            return

        timed_move = (
            f'{ move }@'
            f'{ int(clock / MS_TO_NS_FACTOR) }'
        )

        if self.state in {'start', 'scrambling'}:
            self.handle_scrambled(timed_move)

        elif self.state == 'saving':
            self.handle_save_gestures(timed_move)

        elif self.state == 'scrambled':
            self.moves.append(
                {
                    'move': move,
                    'time': clock,
                },
            )

            self.start_time = clock
            self.solve_started_event.set()

        elif self.state == 'solving':
            self.moves.append(
                {
                    'move': move,
                    'time': clock,
                },
            )

            if (
                    not self.solve_completed_event.is_set()
                    and self.cube_is_solved()
            ):
                self.end_time = clock
                self.solve_completed_event.set()
                logger.info('Bluetooth Stop: %s', self.end_time)

    def cube_is_solved(self) -> bool:
        """
        Check if the Bluetooth cube is in solved state.
        """
        return self.bluetooth_cube.is_solved if self.bluetooth_cube else False
