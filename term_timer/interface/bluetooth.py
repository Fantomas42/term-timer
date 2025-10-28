import asyncio
import logging
from typing import TYPE_CHECKING
from typing import cast

from cubing_algs.move import Move
from cubing_algs.vcube import VCube
from rich.console import Console as RichConsole

from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.types import BatteryEventDict
from term_timer.bluetooth.types import EventDict
from term_timer.bluetooth.types import FaceletsEventDict
from term_timer.bluetooth.types import FaceletsEventDictNoState
from term_timer.bluetooth.types import GyroEventDict
from term_timer.bluetooth.types import HardwareEventDict
from term_timer.bluetooth.types import HardwareEventMoyuDict
from term_timer.bluetooth.types import HardwareEventNameOnlyDict
from term_timer.bluetooth.types import HardwareEventPartialDict
from term_timer.bluetooth.types import HardwareEventSoftwareVersionOnlyDict
from term_timer.bluetooth.types import HardwareEventVersionOnlyDict
from term_timer.bluetooth.types import MoveEventDict
from term_timer.bluetooth.types import MoveInfo
from term_timer.bluetooth.types import RotationEventDict
from term_timer.config import BLUETOOTH_CONFIG
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.exceptions import CubeNotFoundError

logger = logging.getLogger(__name__)


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
        def handle_scrambled(self, timed_move: Move) -> None: ...
        # Methods from Gesture mixin
        def handle_save_gestures(self, move: Move) -> None: ...

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

            await self.bluetooth_interface.send_command('REQUEST_FACELETS')
            await self.bluetooth_interface.send_command('REQUEST_HARDWARE')
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

        if self.bluetooth_consumer_ref:
            await self.bluetooth_consumer_ref

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

        battery_state = self.bluetooth_hardware.get('battery_state')
        if isinstance(battery_state, int) and battery_state:
            device_label += ' (charging)'

        return device_label

    async def bluetooth_consumer(self) -> None:
        """
        Consume events from the Bluetooth queue and process them.
        """
        if not self.bluetooth_queue:
            return

        rotation_detector = RotationDetector()

        while True:
            events = await self.bluetooth_queue.get()

            if events is None:
                break

            for event in events:
                event_name = event['event']

                if event_name == 'hardware':
                    self.handle_hardware_event(event)

                elif event_name == 'battery':
                    battery_event = cast(BatteryEventDict, event)
                    self.bluetooth_hardware['battery_level'] = battery_event[
                        'level'
                    ]
                    self.bluetooth_hardware['battery_state'] = battery_event[
                        'charging_state'
                    ]

                elif event_name == 'facelets':
                    if not self.facelets_received_event.is_set():
                        facelets_event = cast(
                            FaceletsEventDict | FaceletsEventDictNoState,
                            event,
                        )
                        self.bluetooth_cube = VCube(facelets_event['facelets'])
                        self.facelets_received_event.set()

                elif event_name == 'move' and self.bluetooth_cube:
                    move_event = cast(MoveEventDict, event)
                    self.bluetooth_cube.rotate(move_event['move'])
                    self.handle_bluetooth_move(move_event)

                elif event_name == 'gyro' and self.bluetooth_cube:
                    gyro_event = cast(GyroEventDict, event)

                    rotation_result = rotation_detector.process_gyro_event(
                        gyro_event['quaternion'],
                    )
                    if rotation_result:
                        rotation_event: RotationEventDict = {
                            'event': 'rotation',
                            'clock': gyro_event['clock'],
                            'timestamp': gyro_event['timestamp'],
                            'move': rotation_result['rotation'],
                        }

                        self.handle_bluetooth_move(rotation_event)

    def handle_hardware_event(self, event: EventDict) -> None:
        """
        Extract hardware information from various hardware event types.
        """
        if 'hardware_name' in event:
            name_event = cast(
                HardwareEventDict
                | HardwareEventNameOnlyDict
                | HardwareEventMoyuDict,
                event,
            )
            self.bluetooth_hardware['hardware_name'] = name_event[
                'hardware_name'
            ]

        if 'hardware_version' in event:
            version_event = cast(
                HardwareEventDict
                | HardwareEventVersionOnlyDict
                | HardwareEventMoyuDict,
                event,
            )
            self.bluetooth_hardware['hardware_version'] = version_event[
                'hardware_version'
            ]

        if 'software_version' in event:
            software_event = cast(
                HardwareEventDict
                | HardwareEventSoftwareVersionOnlyDict
                | HardwareEventMoyuDict,
                event,
            )
            self.bluetooth_hardware['software_version'] = software_event[
                'software_version'
            ]

        if 'product_date' in event:
            date_event = cast(HardwareEventPartialDict, event)
            self.bluetooth_hardware['product_date'] = date_event['product_date']

        if 'serial' in event:
            serial_event = cast(HardwareEventMoyuDict, event)
            self.bluetooth_hardware['serial'] = serial_event['serial']

        self.hardware_received_event.set()

    def handle_bluetooth_move(
            self, event: MoveEventDict | RotationEventDict,
    ) -> None:
        """
        Handle a move or rotation event from the Bluetooth cube.
        """
        move = event['move']
        clock = event['clock']
        rotation = event['event'] == 'rotation'

        timed_move = Move(f'{ move }@{ int(clock / MS_TO_NS_FACTOR) }')

        if self.state in {'start', 'scrambling'}:
            self.handle_scrambled(timed_move)

        elif self.state == 'saving':
            self.handle_save_gestures(timed_move)

        elif self.state == 'scrambled':
            if rotation:
                return

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
