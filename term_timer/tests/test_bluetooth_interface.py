"""Tests for the bluetooth interface helpers."""
import asyncio
import logging
import unittest
from asyncio import Queue
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import patch

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import format_event
from term_timer.exceptions import CubeNotFoundError

if TYPE_CHECKING:
    from bleak import BleakClient
    from bleak.backends.characteristic import BleakGATTCharacteristic

    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import DisconnectEventDict
    from term_timer.bluetooth.annotations import EventDict
    from term_timer.bluetooth.annotations import FaceletsEventDict
    from term_timer.bluetooth.annotations import GyroEventDict
    from term_timer.bluetooth.annotations import MoveEventDict
    from term_timer.bluetooth.drivers.base import Driver

SOLVED = (
    'UUUUUUUUURRRRRRRRRFFFFFFFFF'
    'DDDDDDDDDLLLLLLLLLBBBBBBBBB'
)


class FormatEventTestCase(unittest.TestCase):
    """Tests for the rendering of a cube event in the log."""

    def setUp(self) -> None:
        """Take the wall clock shared by the events under test."""
        self.now = datetime.now()  # noqa: DTZ005

    def test_format_move(self) -> None:
        """A move says which one, and both clocks that timed it."""
        event: MoveEventDict = {
            'event': 'move',
            'clock': 1856234,
            'timestamp': self.now,
            'serial': 412,
            'local_timestamp': self.now,
            'cube_timestamp': 1856234.0,
            'face': 0,
            'direction': 1,
            'move': "R'",
        }

        self.assertEqual(
            format_event(event),
            'MOVE clock=1856234 serial=412 cube_timestamp=1856234.000'
            " face=0 direction=1 move=R'",
        )

    def test_format_facelets_elides_the_state(self) -> None:
        """The facelets string is kept, the state it repeats is not."""
        event: FaceletsEventDict = {
            'event': 'facelets',
            'clock': 12,
            'timestamp': self.now,
            'serial': 41,
            'facelets': SOLVED,
            'state': {
                'CP': list(range(8)),
                'CO': [0] * 8,
                'EP': list(range(12)),
                'EO': [0] * 12,
            },
        }

        self.assertEqual(
            format_event(event),
            f'FACELETS clock=12 serial=41 facelets={ SOLVED }',
        )

    def test_format_gyro_joins_the_nested_payloads(self) -> None:
        """A quaternion is rounded and flattened, not dumped as a dict."""
        event: GyroEventDict = {
            'event': 'gyro',
            'clock': 12,
            'timestamp': self.now,
            'quaternion': {'x': 0.1234, 'y': -0.98, 'z': 0.03, 'w': 0.45},
            'velocity': {'x': 1.0, 'y': 0.0, 'z': -2.5},
        }

        self.assertEqual(
            format_event(event),
            'GYRO clock=12 quaternion=0.123,-0.980,0.030,0.450'
            ' velocity=1.000,0.000,-2.500',
        )

    def test_format_battery(self) -> None:
        """An event nobody wrote a special case for is rendered anyway."""
        event: BatteryEventDict = {
            'event': 'battery',
            'clock': 12,
            'timestamp': self.now,
            'level': 87,
            'charging_state': 0,
        }

        self.assertEqual(
            format_event(event),
            'BATTERY clock=12 level=87 charging_state=0',
        )

    def test_format_disconnect(self) -> None:
        """An event carrying nothing leaves no trailing space behind."""
        event: DisconnectEventDict = {
            'event': 'disconnect',
            'clock': 12,
            'timestamp': self.now,
        }

        self.assertEqual(format_event(event), 'DISCONNECT clock=12')


class EventDriver:
    """A driver returning the events it was built with, and nothing else."""

    def __init__(self, events: list['EventDict']) -> None:
        """
        Hold the events every notification will yield.

        Args:
            events: The events the handler is to receive.

        """
        self.events = events

    async def event_handler(
            self,
            sender: 'BleakGATTCharacteristic',  # noqa: ARG002
            data: bytearray,  # noqa: ARG002
    ) -> list['EventDict']:
        """
        Return the canned events, ignoring what the cube sent.

        Args:
            sender: The characteristic the notification came from.
            data: The raw bytes of the notification.

        Returns:
            The events the driver was built with.

        """
        return self.events


class NotificationHandlerLogTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for what a notification leaves in the log."""

    def setUp(self) -> None:
        """Take the wall clock shared by the events under test."""
        self.now = datetime.now()  # noqa: DTZ005

    async def test_notification_handler_logs_every_event(self) -> None:
        """
        Every cube event is logged, session in debug mode or not.

        The handler used to log behind a `if DEBUG:` guard, which left
        the only trace of the cube talking out of a log written outside
        of a debug run. The events are the object of that log, so they
        are emitted unconditionally and it is the logging configuration,
        alone, that decides whether they are written.
        """
        moved: MoveEventDict = {
            'event': 'move',
            'clock': 1856234,
            'timestamp': self.now,
            'serial': 412,
            'local_timestamp': self.now,
            'cube_timestamp': 1856234.0,
            'face': 0,
            'direction': 1,
            'move': "R'",
        }
        battery: BatteryEventDict = {
            'event': 'battery',
            'clock': 12,
            'timestamp': self.now,
            'level': 87,
            'charging_state': 0,
        }

        queue: Queue[list[EventDict] | None] = Queue()
        interface = BluetoothInterface(queue)
        interface.driver = cast(
            'Driver', EventDriver([moved, battery]),
        )

        with self.assertLogs(
                'term_timer.bluetooth.interface', logging.DEBUG,
        ) as captured:
            await interface.notification_handler(
                cast('BleakGATTCharacteristic', None), bytearray(b'\x00'),
            )

        self.assertEqual(
            captured.output,
            [
                (
                    'DEBUG:term_timer.bluetooth.interface:'
                    'Event MOVE clock=1856234 serial=412'
                    " cube_timestamp=1856234.000 face=0 direction=1 move=R'"
                ),
                (
                    'DEBUG:term_timer.bluetooth.interface:'
                    'Event BATTERY clock=12 level=87 charging_state=0'
                ),
            ],
        )
        self.assertEqual(queue.get_nowait(), [moved, battery])


class TeardownDriver:
    """A driver exposing only the characteristic to unsubscribe from."""

    state_characteristic_uid = 'state-characteristic'


class TeardownClient:
    """A BleakClient stub with a controllable teardown duration."""

    def __init__(self, *,
                 stop_notify_delay: float = 0.0,
                 disconnect_delay: float = 0.0,
                 is_connected: bool = True) -> None:
        """
        Hold how long each step of the teardown is to take.

        Args:
            stop_notify_delay: Seconds `stop_notify` waits before returning.
            disconnect_delay: Seconds `disconnect` waits before returning.
            is_connected: Whether the link is still up.

        """
        self.stop_notify_delay = stop_notify_delay
        self.disconnect_delay = disconnect_delay
        self.is_connected = is_connected
        self.stop_notify_calls: list[str] = []
        self.disconnect_calls = 0

    async def stop_notify(self, characteristic: str) -> None:
        """
        Record the unsubscription, then wait for its configured delay.

        Args:
            characteristic: The characteristic to stop listening to.

        """
        self.stop_notify_calls.append(characteristic)
        await asyncio.sleep(self.stop_notify_delay)

    async def disconnect(self) -> None:
        """Record the disconnection, then wait for its configured delay."""
        self.disconnect_calls += 1
        await asyncio.sleep(self.disconnect_delay)


class BluetoothTeardownTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for what leaving the interface does, and leaves in the log."""

    logger_name = 'term_timer.bluetooth.interface'

    @staticmethod
    def build_interface(client: TeardownClient) -> BluetoothInterface:
        """
        Build an interface sitting on the given client.

        Args:
            client: The client stub the teardown is to run against.

        Returns:
            The interface, its queue empty and its driver connected.

        """
        interface = BluetoothInterface(Queue())
        interface.client = cast('BleakClient', client)
        interface.driver = cast('Driver', TeardownDriver())

        return interface

    async def test_teardown_logs_the_duration_of_both_steps(self) -> None:
        """
        A healthy teardown says how long each of its two steps took.

        Both used to be silent on success, and the disconnect logged the
        very same line whether it had completed or been cut short at
        0.5s. The duration is what tells the two apart.
        """
        client = TeardownClient()
        interface = self.build_interface(client)

        with self.assertLogs(self.logger_name, level='DEBUG') as logs:
            await interface.__aexit__(None, None, None)

        self.assertEqual(client.stop_notify_calls, ['state-characteristic'])
        self.assertEqual(client.disconnect_calls, 1)

        output = '\n'.join(logs.output)
        self.assertIn('Notifications stopped in', output)
        self.assertIn('Disconnected in', output)
        self.assertNotIn('WARNING', output)

    async def test_slow_disconnect_warns_and_gives_the_hand_back(self) -> None:
        """
        A disconnect that never completes warns, and exits anyway.

        The timeout is a guard against a hung D-Bus call, so hitting it
        is an event worth a warning, where the old 0.5s bound was hit on
        every single exit and logged in debug.
        """
        client = TeardownClient(disconnect_delay=5.0)
        interface = self.build_interface(client)

        with patch(
                'term_timer.bluetooth.interface.'
                'BLUETOOTH_DISCONNECT_TIMEOUT', 0.01,
        ), self.assertLogs(self.logger_name, level='WARNING') as logs:
            await asyncio.wait_for(
                interface.__aexit__(None, None, None), 1.0,
            )

        self.assertIn('Disconnect timed out', logs.output[0])

    async def test_stuck_notifications_still_disconnect(self) -> None:
        """
        Notifications that never stop no longer hang the session exit.

        `stop_notify` was awaited unbounded, on the very path a session
        ends by: a link gone silent kept the application inside its
        `finally` forever, with nothing written anywhere.
        """
        client = TeardownClient(stop_notify_delay=5.0)
        interface = self.build_interface(client)

        with patch(
                'term_timer.bluetooth.interface.'
                'BLUETOOTH_DISCONNECT_TIMEOUT', 0.01,
        ), self.assertLogs(self.logger_name, level='WARNING') as logs:
            await asyncio.wait_for(
                interface.__aexit__(None, None, None), 1.0,
            )

        self.assertIn('Notifications not stopped', logs.output[0])
        self.assertEqual(client.disconnect_calls, 1)

    async def test_link_already_down_is_not_talked_to(self) -> None:
        """A dead link is left alone, and the queue with it."""
        client = TeardownClient(is_connected=False)
        interface = self.build_interface(client)

        await interface.__aexit__(None, None, None)

        self.assertEqual(client.stop_notify_calls, [])
        self.assertEqual(client.disconnect_calls, 0)
        self.assertTrue(interface.queue.empty())

    async def test_teardown_leaves_the_sentinel_to_its_caller(self) -> None:
        """
        Leaving the interface posts nothing on the queue.

        The queue belongs to the consumer, so the sentinel belongs to
        whoever waits for it. Posted from here it doubled the one the
        caller posts, and it landed in a queue nobody reads whenever the
        caller runs no consumer at all.
        """
        client = TeardownClient()
        interface = self.build_interface(client)

        await interface.__aexit__(None, None, None)

        self.assertEqual(client.disconnect_calls, 1)
        self.assertTrue(interface.queue.empty())


class ConnectingClient:
    """A BleakClient stub connecting to a device carrying no service."""

    def __init__(self) -> None:
        """Start disconnected, with no service to offer a driver."""
        self.is_connected = False
        self.services: list[object] = []

    async def connect(self) -> None:
        """Mark the link as up, as bleak does on success."""
        self.is_connected = True


class BluetoothLinkLostTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for a BLE link dropping on its own, under the application."""

    logger_name = 'term_timer.bluetooth.interface'

    @staticmethod
    def make_disconnect_event() -> 'DisconnectEventDict':
        """
        Build the event a cube announcing its disconnection produces.

        Returns:
            The payload the drivers emit, to compare the callback with.

        """
        return {
            'event': 'disconnect',
            'clock': 0,
            'timestamp': datetime.now(tz=UTC),
        }

    async def test_the_client_is_built_with_the_callback(self) -> None:
        """
        Bleak is given someone to call when the link drops.

        Built without it, a cube going out of range or flat sent no
        packet, so no driver ever emitted the disconnection, and the
        session stayed parked on a move that could not come.
        """
        built: list[dict[str, object]] = []

        def build_client(address: str, **kwargs: object) -> ConnectingClient:
            """
            Record how the client was built, and return a stub.

            Args:
                address: The device address bleak was pointed at.
                kwargs: Every other argument of the construction.

            Returns:
                A client stub offering no service, so no driver.

            """
            built.append({'address': address, **kwargs})
            return ConnectingClient()

        interface = BluetoothInterface(Queue())

        with patch(
                'term_timer.bluetooth.interface.BleakClient', build_client,
        ), self.assertRaises(CubeNotFoundError):
            await interface.__aenter__('AA:BB:CC:DD:EE:FF', use_gyroscope=False)

        self.assertEqual(len(built), 1)
        self.assertEqual(
            built[0]['disconnected_callback'], interface.handle_disconnection,
        )

    async def test_a_lost_link_posts_the_disconnection(self) -> None:
        """
        The link dropping produces the event a cube would have sent.

        The same payload on the same queue is the whole point: the
        consumer, the lost event and the phases behind it already know
        what to do with it, whatever made the cube go away.
        """
        interface = BluetoothInterface(Queue())

        with self.assertLogs(self.logger_name, level='WARNING') as logs:
            interface.handle_disconnection(cast('BleakClient', None))

        self.assertIn('Bluetooth link lost', logs.output[0])

        posted = interface.queue.get_nowait()
        expected = self.make_disconnect_event()

        self.assertIsNotNone(posted)
        posted = cast('list[EventDict]', posted)
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]['event'], expected['event'])
        self.assertEqual(posted[0]['clock'], expected['clock'])

    async def test_our_own_disconnection_is_not_a_loss(self) -> None:
        """
        Leaving the interface posts nothing, though bleak calls back.

        Bleak calls the callback on every disconnection, ours included.
        Unguarded, every normal session end would announce a cube loss:
        a second disconnection sound, a consumer returning on its own,
        and a phase still waiting given a disconnection error.
        """
        client = TeardownClient()
        interface = BluetoothInterface(Queue())
        interface.client = cast('BleakClient', client)
        interface.driver = cast('Driver', TeardownDriver())

        await interface.__aexit__(None, None, None)

        with self.assertLogs(self.logger_name, level='DEBUG') as logs:
            interface.handle_disconnection(cast('BleakClient', client))

        self.assertIn('Link closed by the application', logs.output[0])
        self.assertTrue(interface.queue.empty())
