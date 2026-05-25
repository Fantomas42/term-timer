"""Bluetooth cube integration interface mixin."""
import asyncio
import logging
from typing import TYPE_CHECKING
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.move import Move
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDict
from term_timer.bluetooth.annotations import FaceletsEventDictNoState
from term_timer.bluetooth.annotations import GyroConfigEventDict
from term_timer.bluetooth.annotations import GyroEventDict
from term_timer.bluetooth.annotations import HardwareEventDict
from term_timer.bluetooth.annotations import HardwareEventMoyuDict
from term_timer.bluetooth.annotations import HardwareEventNameOnlyDict
from term_timer.bluetooth.annotations import HardwareEventPartialDict
from term_timer.bluetooth.annotations import (
    HardwareEventSoftwareVersionOnlyDict,
)
from term_timer.bluetooth.annotations import HardwareEventVersionOnlyDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.annotations import MoveInfo
from term_timer.bluetooth.annotations import RotationEventDict
from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.config import DEVICE_ADDRESS
from term_timer.config import DEVICE_NAME
from term_timer.config import USE_GYROSCOPE
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.exceptions import CubeNotFoundError
from term_timer.interface.sounds import SOUND_PLAYER

if TYPE_CHECKING:
    from rich.console import Console as RichConsole

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
        def clear_line(self, *, full: bool) -> None:
            """Clear current terminal line."""
            ...

        # Methods from Scrambler mixin
        def handle_scrambled(self, timed_move: Move) -> None:
            """Handle a move during scrambling phase."""
            ...

        # Methods from Gesture mixin
        def handle_save_gestures(self, move: Move) -> None:
            """Handle a move during gesture saving phase."""
            ...

    def __init__(self) -> None:
        """Initialize Bluetooth integration state and event queues."""
        super().__init__()

        self.moves: list[MoveInfo] = []

        self.bluetooth_queue: asyncio.Queue[
            list[EventDict] | None
        ] | None = None
        self.bluetooth_cube: VCube | None = None
        self.bluetooth_cube_orientations = Algorithm()
        self.bluetooth_interface: BluetoothInterface | None = None
        self.bluetooth_consumer_ref: asyncio.Task[None] | None = None
        self.bluetooth_hardware: dict[str, str | int] = {}

        self.facelets_received_event = asyncio.Event()
        self.hardware_received_event = asyncio.Event()

    async def bluetooth_connect(
            self, *,
            use_gyroscope: bool = USE_GYROSCOPE) -> bool:
        """
        Connect to a Bluetooth cube and initialize device communication.

        Scans for or connects to a Bluetooth cube, requests initial state,
        and waits for hardware and facelet information to be received.

        Args:
            use_gyroscope: Whether the driver should use gyroscope data.

        Returns:
            True if connection and initialization succeeded, False otherwise.

        """
        address = DEVICE_ADDRESS

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
                    f'Connecting to [b]{ DEVICE_NAME or address }[/b]...',
                    end='',
                )

            await self.bluetooth_interface.__aenter__(
                address, use_gyroscope=use_gyroscope,
            )

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

            await self.bluetooth_interface.send_init_commands()

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        self.facelets_received_event.wait(),
                        self.hardware_received_event.wait(),
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:  # noqa: UP041
                SOUND_PLAYER.cube_not_connected()
                self.clear_line(full=True)
                self.console.print(
                    '[bluetooth]😱Bluetooth:[/bluetooth] '
                    '[warning]Cube could not be initialized properly. '
                    'Running in manual mode.[/warning]',
                )
                return False

            SOUND_PLAYER.cube_connected()
            self.clear_line(full=True)
            self.console.print(
                '[bluetooth]🤓Bluetooth:[/bluetooth] '
                f'[result]{ self.bluetooth_device_label } '
                'initialized successfully ![/result]',
            )
        except CubeNotFoundError:
            SOUND_PLAYER.cube_not_connected()
            self.clear_line(full=True)
            self.console.print(
                '[bluetooth]😥Bluetooth:[/bluetooth] '
                '[warning]No Bluetooth cube could be found. '
                'Running in manual mode.[/warning]',
            )
            return False
        else:
            return True

    async def bluetooth_handoff(self, target: 'Bluetooth') -> None:
        """
        Transfer Bluetooth connection to another SolveInterface instance.

        Stops the current consumer task, transfers all connection state to
        target, and starts a new consumer task on target. The underlying
        Bluetooth connection is not interrupted.

        Args:
            target: The instance that will take over the connection.

        """
        if self.bluetooth_queue:
            await self.bluetooth_queue.put(None)
        if self.bluetooth_consumer_ref:
            await self.bluetooth_consumer_ref

        target.bluetooth_queue = self.bluetooth_queue
        target.bluetooth_interface = self.bluetooth_interface
        target.bluetooth_cube = self.bluetooth_cube
        target.bluetooth_cube_orientations = self.bluetooth_cube_orientations
        target.bluetooth_hardware = self.bluetooth_hardware
        target.facelets_received_event = self.facelets_received_event
        target.hardware_received_event = self.hardware_received_event

        if target.bluetooth_queue is not None:
            target.bluetooth_consumer_ref = asyncio.create_task(
                target.bluetooth_consumer(),
            )

    async def bluetooth_disconnect(self) -> None:
        """Disconnect from the Bluetooth cube if connected."""
        if (
                self.bluetooth_interface
                and self.bluetooth_interface.client
                and self.bluetooth_interface.client.is_connected
        ):
            SOUND_PLAYER.cube_disconnected()
            self.console.print(
                '[bluetooth]🔗Bluetooth:[/bluetooth] '
                f'{ self.bluetooth_device_label } disconnecting...',
            )
            await self.bluetooth_interface.__aexit__(None, None, None)

        if self.bluetooth_consumer_ref:
            await self.bluetooth_consumer_ref

    @property
    def bluetooth_device_label(self) -> str:
        """Get a formatted label with device name, version, and battery."""
        if not self.bluetooth_interface or not self.bluetooth_interface.client:
            return ''

        device_label = DEVICE_NAME
        if not device_label:
            device_label = self.bluetooth_interface.client.name

            if 'hardware_version' in self.bluetooth_hardware:
                device_label += (
                    f'v{ self.bluetooth_hardware["hardware_version"] }'
                )

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

    async def bluetooth_consumer(self) -> None:  # noqa: C901, PLR0912
        """
        Consume events from Bluetooth queue and dispatch to handlers.

        Processes hardware, battery, facelets, move, and gyroscope events
        from the Bluetooth cube, updating state and triggering appropriate
        handlers based on event type.

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
                    await self.reconcile_gyroscope_state()

                elif event_name == 'battery':
                    battery_event = cast('BatteryEventDict', event)

                    self.bluetooth_hardware['battery_level'] = battery_event[
                        'level'
                    ]
                    self.bluetooth_hardware['battery_state'] = battery_event[
                        'charging_state'
                    ]

                elif event_name == 'facelets':
                    if not self.facelets_received_event.is_set():
                        facelets_event = cast(
                            'FaceletsEventDict | FaceletsEventDictNoState',
                            event,
                        )

                        self.bluetooth_cube = VCube(
                            facelets_event['facelets'],
                            size=3,
                        )
                        if not self.bluetooth_cube_is_solved:
                            self.clear_line(full=True)
                            self.console.print(
                                '[bluetooth]🫤Bluetooth:[/bluetooth] '
                                '[warning]'
                                'Cube is not in solved state. '
                                'Run "term-timer reset" if needed.'
                                '[/warning]',
                            )

                        self.facelets_received_event.set()

                elif event_name == 'move':
                    move_event = cast('MoveEventDict', event)

                    self.handle_bluetooth_cube_move(move_event['move'])
                    self.handle_bluetooth_move(move_event)

                elif event_name == 'gyro' and self.bluetooth_cube:
                    gyro_event = cast('GyroEventDict', event)

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

                        self.handle_bluetooth_cube_move(rotation_result['rotation'])
                        self.handle_bluetooth_move(rotation_event)

                elif event_name == 'gyro-config':
                    gyro_config_event = cast('GyroConfigEventDict', event)

                    self.bluetooth_hardware['gyroscope_enabled'] = (
                        gyro_config_event['gyroscope_enabled']
                    )
                    self.bluetooth_hardware['gyroscope_ready'] = (
                        gyro_config_event['gyroscope_ready']
                    )
                    self.bluetooth_hardware['gyroscope_supported'] = (
                        gyro_config_event['gyroscope_supported']
                    )

    def handle_hardware_event(self, event: EventDict) -> None:
        """
        Extract and store hardware info from various event types.

        Processes hardware events to extract device name, version numbers,
        production date, and serial number into bluetooth_hardware dict.

        Args:
            event: Hardware event containing device information.

        """
        if 'hardware_name' in event:
            name_event = cast(
                'HardwareEventDict | '
                'HardwareEventNameOnlyDict | '
                'HardwareEventMoyuDict',
                event,
            )
            self.bluetooth_hardware['hardware_name'] = name_event[
                'hardware_name'
            ]

        if 'hardware_version' in event:
            version_event = cast(
                'HardwareEventDict | '
                'HardwareEventVersionOnlyDict | '
                'HardwareEventMoyuDict',
                event,
            )
            self.bluetooth_hardware['hardware_version'] = version_event[
                'hardware_version'
            ]

        if 'software_version' in event:
            software_event = cast(
                'HardwareEventDict | '
                'HardwareEventSoftwareVersionOnlyDict | '
                'HardwareEventMoyuDict',
                event,
            )
            self.bluetooth_hardware['software_version'] = software_event[
                'software_version'
            ]

        if 'product_date' in event:
            date_event = cast('HardwareEventPartialDict', event)
            self.bluetooth_hardware['product_date'] = date_event['product_date']

        if 'serial' in event:
            serial_event = cast('HardwareEventMoyuDict', event)
            self.bluetooth_hardware['serial'] = serial_event['serial']

        if 'gyroscope_enabled' in event:
            gyro_enabled_event = cast(
                'HardwareEventDict | HardwareEventMoyuDict',
                event,
            )
            self.bluetooth_hardware['gyroscope_enabled'] = (
                gyro_enabled_event['gyroscope_enabled']
            )

        if 'gyroscope_ready' in event:
            gyro_ready_event = cast(
                'HardwareEventDict | HardwareEventMoyuDict',
                event,
            )
            self.bluetooth_hardware['gyroscope_ready'] = (
                gyro_ready_event['gyroscope_ready']
            )

        if 'gyroscope_supported' in event:
            gyro_supported_event = cast(
                'HardwareEventDict | '
                'HardwareEventNameOnlyDict | '
                'HardwareEventMoyuDict',
                event,
            )
            self.bluetooth_hardware['gyroscope_supported'] = (
                gyro_supported_event['gyroscope_supported']
            )

        self.hardware_received_event.set()

    async def reconcile_gyroscope_state(self) -> None:
        """
        Send enable/disable gyroscope commands based on hardware state.

        Compares the user's gyroscope preference (use_gyroscope) with the
        current hardware state and sends the appropriate command to align them:
        - Enables gyroscope if wanted but disabled (and hardware supports it)
        - Disables gyroscope if not wanted but currently enabled

        """
        if not self.bluetooth_interface or not self.bluetooth_interface.driver:
            return

        use_gyroscope = self.bluetooth_interface.driver.use_gyroscope
        gyro_enabled = self.bluetooth_hardware.get('gyroscope_enabled', False)
        gyro_ready = self.bluetooth_hardware.get('gyroscope_ready', False)

        # Enable gyroscope if wanted but not enabled (and hardware supports it)
        if use_gyroscope and gyro_ready and not gyro_enabled:
            logger.debug('Enabling gyroscope (wanted but disabled)')
            await self.bluetooth_interface.send_command('REQUEST_ENABLE_GYRO')

        # Disable gyroscope if not wanted but currently enabled
        elif not use_gyroscope and gyro_enabled:
            logger.debug('Disabling gyroscope (not wanted but enabled)')
            await self.bluetooth_interface.send_command(
                'REQUEST_DISABLE_GYRO',
            )

    def handle_bluetooth_cube_move(self, move_str: str) -> None:
        """
        Apply move on Bluetooth cube if ready.

        If move is a rotation, it's stored in a mirror algorithm form,
        to correct future moves compensating the rotations. In reality
        the cube does not rotate from his POV and stay in UF orientation.
        """
        if not self.bluetooth_cube:
            return

        move = Move(move_str)

        if move.is_rotation_move:
            self.bluetooth_cube_orientations.insert(0, move.inverted)
        elif self.bluetooth_cube_orientations:
            correction_moves = self.bluetooth_cube_orientations + move
            move = correction_moves.transform(degrip_full_moves)[0]

        self.bluetooth_cube.rotate(move)

    def handle_bluetooth_move(
            self, event: MoveEventDict | RotationEventDict,
    ) -> None:
        """
        Handle a move or rotation event from the Bluetooth cube.

        Processes cube moves based on current state: passes to scramble
        handler during scrambling, records moves during solving, and
        triggers solve completion when cube becomes solved.

        Args:
            event: Move or rotation event containing move notation, clock
                time, and event type.

        """
        move = event['move']
        clock = event['clock']
        rotation = event['event'] == 'rotation'

        timed_move = Move(f'{ move }@{ int(clock / MS_TO_NS_FACTOR) }')

        if self.state in {'start', 'scrambling'}:
            self.handle_scrambled(timed_move)

        elif self.state == 'saving':
            self.handle_save_gestures(timed_move)

        elif self.state == 'inspecting':
            if not rotation:
                self.solve_started_event.set()

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
                    and self.bluetooth_scramble_is_completed
            ):
                self.end_time = clock
                self.solve_completed_event.set()
                logger.info('Bluetooth Stop: %s', self.end_time)

    @property
    def bluetooth_cube_is_solved(self) -> bool:
        """
        Check if the Bluetooth cube is in solved state.

        Returns:
            True if cube is solved, False otherwise or if no cube connected.

        """
        return self.bluetooth_cube.is_solved if self.bluetooth_cube else False

    @property
    def bluetooth_cube_state(self) -> str:
        """Returns state of the bluetooth cube if connected."""
        return self.bluetooth_cube.state if self.bluetooth_cube else ''

    @property
    def bluetooth_scramble_is_completed(self) -> bool:
        """Return if bluetooth scramble is complete."""
        return self.bluetooth_cube_is_solved
