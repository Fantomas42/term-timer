"""Tests for the bluetooth interface helpers."""
import asyncio
import logging
import unittest
from asyncio import Queue
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import AsyncMock
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


class RaisingDriver:
    """A driver whose decoding always fails."""

    async def event_handler(  # noqa: PLR6301
            self,
            sender: 'BleakGATTCharacteristic',  # noqa: ARG002
            data: bytearray,  # noqa: ARG002
    ) -> list['EventDict']:
        """
        Fail the way an unguarded field indexation would.

        Args:
            sender: The characteristic the notification came from.
            data: The raw bytes of the notification.

        Raises:
            ValueError: Always, as `list.index` does out of domain.

        """
        msg = '6 is not in list'
        raise ValueError(msg)


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

    async def test_notification_handler_survives_a_decoding_failure(
            self) -> None:
        """
        A driver raising never breaks the notification chain.

        bleak drops a callback that raises, so a single decoding bug
        would silence the cube for the rest of the session, with a link
        still up. The notification is lost, the chain is not.
        """
        queue: Queue[list[EventDict] | None] = Queue()
        interface = BluetoothInterface(queue)
        interface.driver = cast('Driver', RaisingDriver())

        with self.assertLogs(
                'term_timer.bluetooth.interface', logging.ERROR,
        ) as captured:
            await interface.notification_handler(
                cast('BleakGATTCharacteristic', None), bytearray(b'\x00\x01'),
            )

        self.assertIn(
            'Decoding of a 2 bytes notification failed',
            captured.output[0],
        )
        self.assertIn('ValueError: 6 is not in list', captured.output[0])
        self.assertTrue(queue.empty())

    async def test_notification_handler_keeps_decoding_after_a_failure(
            self) -> None:
        """A notification failing does not stop the ones after it."""
        battery: BatteryEventDict = {
            'event': 'battery',
            'clock': 12,
            'timestamp': self.now,
            'level': 87,
            'charging_state': 0,
        }

        queue: Queue[list[EventDict] | None] = Queue()
        interface = BluetoothInterface(queue)
        interface.driver = cast('Driver', RaisingDriver())

        with self.assertLogs('term_timer.bluetooth.interface', logging.ERROR):
            await interface.notification_handler(
                cast('BleakGATTCharacteristic', None), bytearray(b'\x00'),
            )

        interface.driver = cast('Driver', EventDriver([battery]))

        await interface.notification_handler(
            cast('BleakGATTCharacteristic', None), bytearray(b'\x00'),
        )

        self.assertEqual(queue.get_nowait(), [battery])


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


class TimingOutClient:
    """A BleakClient stub whose connection attempt times out."""

    def __init__(self) -> None:
        """Start disconnected, like any client about to fail."""
        self.is_connected = False

    async def connect(self) -> None:  # noqa: PLR6301
        """
        Raise the plain TimeoutError bleak surfaces on a stuck link.

        Raises:
            TimeoutError: Always, as bleak does past its own timeout.

        """
        raise TimeoutError


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

    async def test_a_connection_timeout_is_a_cube_not_found(self) -> None:
        """
        A connection that never completes is treated like one refused.

        Bleak raises a plain TimeoutError here, not a BleakError, so it
        needs its own arm alongside it to land on the same outcome.
        """
        interface = BluetoothInterface(Queue())

        with patch(
                'term_timer.bluetooth.interface.BleakClient',
                lambda *args, **kwargs: TimingOutClient(),  # noqa: ARG005
        ), self.assertRaises(CubeNotFoundError):
            await interface.__aenter__(
                'AA:BB:CC:DD:EE:FF', use_gyroscope=False,
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


class RecordingPublisher:
    """A publisher recording what the interface hands it."""

    def __init__(self, queue: 'Queue[list[EventDict] | None] | None' = None,
                 *, failing: bool = False) -> None:
        """
        Hold what is published, and when.

        Args:
            queue: The queue of the interface under test, watched to
                tell whether the publication came before the consumer
                was served.
            failing: Whether every publication is to blow up.

        """
        self.queue = queue
        self.failing = failing
        self.events: list[EventDict] = []
        self.links: list[tuple[bool, str]] = []
        self.queue_sizes: list[int] = []

    def publish_events(self, events: list['EventDict']) -> None:
        """
        Record a batch of hardware events.

        Args:
            events: The events the interface is emitting.

        Raises:
            RuntimeError: When built to fail, standing for anything a
                publication can hit.

        """
        if self.queue is not None:
            self.queue_sizes.append(self.queue.qsize())

        if self.failing:
            msg = 'Publication exploded'
            raise RuntimeError(msg)

        self.events.extend(events)

    def publish_link(self, *, connected: bool, reason: str) -> None:
        """
        Record a change of the link state.

        Args:
            connected: Whether the cube is reachable from now on.
            reason: What made the link change.

        """
        self.links.append((connected, reason))


class ServiceStub:
    """A GATT service offering the one uuid a driver claims."""

    def __init__(self, uuid: str) -> None:
        """
        Hold the uuid the driver lookup matches on.

        Args:
            uuid: The service uuid advertised to the interface.

        """
        self.uuid = uuid


class PublishedDriver:
    """A driver claiming a service, and doing nothing with the link."""

    service_uid = 'published-service'
    state_characteristic_uid = 'state-characteristic'

    def __init__(self, client: 'BleakClient', *,
                 use_gyroscope: bool,
                 advertisement: object | None = None) -> None:
        """
        Hold what the interface builds a driver with.

        Args:
            client: The connected client the driver talks through.
            use_gyroscope: Whether the gyroscope data is wanted.
            advertisement: The advertisement the interface found, unused
                by this stub.

        """
        self.client = client
        self.use_gyroscope = use_gyroscope
        self.advertisement = advertisement


class PublishedClient:
    """A BleakClient stub whose device offers the driver's service."""

    def __init__(self) -> None:
        """Start disconnected, with the service a driver claims."""
        self.is_connected = False
        self.services: list[object] = [ServiceStub('published-service')]
        self.notified: list[str] = []

    async def connect(self) -> None:
        """Mark the link as up, as bleak does on success."""
        self.is_connected = True

    async def start_notify(self, characteristic: str,
                           handler: object) -> None:  # noqa: ARG002
        """
        Record the subscription the interface asks for.

        Args:
            characteristic: The characteristic listened to.
            handler: The callback bleak is to call, unused here.

        """
        self.notified.append(characteristic)


class EventPublicationTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for what the interface broadcasts beside its queue."""

    logger_name = 'term_timer.bluetooth.interface'

    @staticmethod
    def make_events() -> list['EventDict']:
        """
        Build the batch a notification is to carry.

        Returns:
            A move and a battery event, in that order.

        """
        now = datetime.now(tz=UTC)
        moved: MoveEventDict = {
            'event': 'move',
            'clock': 1856234,
            'timestamp': now,
            'serial': 412,
            'local_timestamp': now,
            'cube_timestamp': 1856234.0,
            'face': 0,
            'direction': 1,
            'move': "R'",
        }
        battery: BatteryEventDict = {
            'event': 'battery',
            'clock': 12,
            'timestamp': now,
            'level': 87,
            'charging_state': 0,
        }

        return [moved, battery]

    async def test_a_notification_is_published_then_queued(self) -> None:
        """
        What reaches the consumer was broadcast first, and identical.

        The order is the whole point of a single emission path: a
        subscriber sees the cube move at the same instant as the
        application, never after it acted on it.
        """
        events = self.make_events()
        queue: Queue[list[EventDict] | None] = Queue()
        interface = BluetoothInterface(queue)
        interface.driver = cast('Driver', EventDriver(events))
        publisher = RecordingPublisher(queue)

        with patch(f'{ self.logger_name }.PUBLISHER', publisher):
            await interface.notification_handler(
                cast('BleakGATTCharacteristic', None), bytearray(b'\x00'),
            )

        self.assertEqual(publisher.events, events)
        self.assertEqual(publisher.queue_sizes, [0])
        self.assertEqual(queue.get_nowait(), events)

    async def test_a_lost_link_is_published_too(self) -> None:
        """
        The disconnection bleak signals is broadcast like any event.

        It comes from a callback, outside any coroutine, which is the
        only reason it takes another path than the notifications.
        """
        interface = BluetoothInterface(Queue())
        publisher = RecordingPublisher(interface.queue)

        with patch(f'{ self.logger_name }.PUBLISHER', publisher), \
             self.assertLogs(self.logger_name, level='WARNING'):
            interface.handle_disconnection(cast('BleakClient', None))

        self.assertEqual(len(publisher.events), 1)
        self.assertEqual(publisher.events[0]['event'], 'disconnect')
        self.assertEqual(publisher.queue_sizes, [0])
        self.assertFalse(interface.queue.empty())

    async def test_a_failing_publication_never_reaches_the_consumer(
            self) -> None:
        """
        A publisher blowing up costs a debug line, and nothing else.

        This is the guarantee the whole stream rests on: a subscriber,
        a socket or a serialisation is never allowed to take a timed
        session down with it.
        """
        events = self.make_events()
        queue: Queue[list[EventDict] | None] = Queue()
        interface = BluetoothInterface(queue)
        interface.driver = cast('Driver', EventDriver(events))
        publisher = RecordingPublisher(failing=True)

        with patch(f'{ self.logger_name }.PUBLISHER', publisher), \
             self.assertLogs(self.logger_name, level='DEBUG') as logs:
            await interface.notification_handler(
                cast('BleakGATTCharacteristic', None), bytearray(b'\x00'),
            )

        self.assertEqual(queue.get_nowait(), events)
        self.assertIn('Cannot publish events', '\n'.join(logs.output))

    def test_a_failing_publication_never_stops_the_callback(self) -> None:
        """A link lost under a broken publisher still posts its event."""
        interface = BluetoothInterface(Queue())
        publisher = RecordingPublisher(failing=True)

        with patch(f'{ self.logger_name }.PUBLISHER', publisher), \
             self.assertLogs(self.logger_name, level='DEBUG'):
            interface.handle_disconnection(cast('BleakClient', None))

        self.assertFalse(interface.queue.empty())

    async def test_an_idle_publisher_changes_nothing(self) -> None:
        """
        The real singleton, bound to nothing, is a no-op on the path.

        Every existing session runs with publication off, so the queue
        must behave exactly as it did before there was a publisher.
        """
        events = self.make_events()
        queue: Queue[list[EventDict] | None] = Queue()
        interface = BluetoothInterface(queue)
        interface.driver = cast('Driver', EventDriver(events))

        await interface.notification_handler(
            cast('BleakGATTCharacteristic', None), bytearray(b'\x00'),
        )

        self.assertEqual(queue.get_nowait(), events)

    async def test_the_connection_is_published(self) -> None:
        """
        A cube arriving is announced, which no driver event does.

        A cube says it is leaving and never that it is there, so the
        interface is the only one who can tell a subscriber that the
        stream it just joined has a cube behind it.
        """
        client = PublishedClient()
        interface = BluetoothInterface(Queue())
        publisher = RecordingPublisher()

        with patch(
                'term_timer.bluetooth.interface.BleakClient',
                lambda *args, **kwargs: client,  # noqa: ARG005
        ), patch(
            'term_timer.bluetooth.interface.DRIVERS', [PublishedDriver],
        ), patch(f'{ self.logger_name }.PUBLISHER', publisher):
            await interface.__aenter__(
                'AA:BB:CC:DD:EE:FF', use_gyroscope=False,
            )

        self.assertEqual(client.notified, ['state-characteristic'])
        self.assertEqual(publisher.links, [(True, 'opened')])

    async def test_a_connection_that_fails_is_not_published(self) -> None:
        """A cube that was never there never announced itself."""
        interface = BluetoothInterface(Queue())
        publisher = RecordingPublisher()

        with patch(
                'term_timer.bluetooth.interface.BleakClient',
                lambda *args, **kwargs: ConnectingClient(),  # noqa: ARG005
        ), patch(
            f'{ self.logger_name }.PUBLISHER', publisher,
        ), self.assertRaises(CubeNotFoundError):
            await interface.__aenter__(
                'AA:BB:CC:DD:EE:FF', use_gyroscope=False,
            )

        self.assertEqual(publisher.links, [])

    async def test_the_disconnection_we_asked_for_is_published(self) -> None:
        """
        Leaving the interface says the link is closed, not lost.

        A subscriber does not wait for the same thing after a session
        that ended and after a cube that went out of range.
        """
        client = TeardownClient()
        interface = BluetoothInterface(Queue())
        interface.client = cast('BleakClient', client)
        interface.driver = cast('Driver', TeardownDriver())
        publisher = RecordingPublisher()

        with patch(f'{ self.logger_name }.PUBLISHER', publisher):
            await interface.__aexit__(None, None, None)

        self.assertEqual(publisher.links, [(False, 'closed')])

    async def test_a_link_already_down_announces_nothing(self) -> None:
        """A link nobody holds any more has no closing to announce."""
        client = TeardownClient(is_connected=False)
        interface = BluetoothInterface(Queue())
        interface.client = cast('BleakClient', client)
        interface.driver = cast('Driver', TeardownDriver())
        publisher = RecordingPublisher()

        with patch(f'{ self.logger_name }.PUBLISHER', publisher):
            await interface.__aexit__(None, None, None)

        self.assertEqual(publisher.links, [])


class ScanDevice:
    """A BLE device stub carrying only what scan() reads."""

    def __init__(self, name: str, address: str) -> None:
        """
        Hold the name and address a scan would report.

        Args:
            name: The advertised device name, matched against PREFIX.
            address: The device address, a MAC on every platform but
                macOS.

        """
        self.name = name
        self.address = address


class ScanAdvertisement:
    """An advertisement stub carrying only its manufacturer data."""

    def __init__(self, manufacturer_data: dict[int, bytes]) -> None:
        """
        Hold the company id keyed payloads a scan would report.

        Args:
            manufacturer_data: The payloads, by company id.

        """
        self.manufacturer_data = manufacturer_data


class ScanTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the advertisement data a scan captures alongside a cube."""

    logger_name = 'term_timer.bluetooth.interface'

    discover_target = 'term_timer.bluetooth.interface.BleakScanner.discover'

    async def test_scan_records_the_advertisement_of_the_selected_device(
            self) -> None:
        """Test last_advertisement is set to the winning candidate's."""
        device = ScanDevice('GAN12 ui', 'AA:BB:CC:DD:EE:FF')
        advertisement = ScanAdvertisement({0x0001: bytes(range(9))})
        interface = BluetoothInterface(Queue())
        devices = {device.address: (device, advertisement)}

        with patch(self.discover_target, AsyncMock(return_value=devices)):
            result = await interface.scan()

        self.assertIs(result, device)
        self.assertIs(interface.last_advertisement, advertisement)

    async def test_scan_ignores_a_device_without_a_known_prefix(
            self) -> None:
        """Test a name matching no PREFIX leaves the advertisement unset."""
        device = ScanDevice('Unknown Device', 'AA:BB:CC:DD:EE:FF')
        advertisement = ScanAdvertisement({})
        interface = BluetoothInterface(Queue())
        devices = {device.address: (device, advertisement)}

        with patch(self.discover_target, AsyncMock(return_value=devices)):
            result = await interface.scan()

        self.assertIsNone(result)
        self.assertIsNone(interface.last_advertisement)

    async def test_a_configured_cube_takes_its_advertisement_with_it(
            self) -> None:
        """Test the early return on a known cube sets its own advertisement."""
        known = ScanDevice('GAN12 ui', 'AA:BB:CC:DD:EE:FF')
        other = ScanDevice('GAN12 ui', '11:22:33:44:55:66')
        known_advertisement = ScanAdvertisement({0x0001: bytes(range(9))})
        other_advertisement = ScanAdvertisement({})
        interface = BluetoothInterface(Queue())
        devices = {
            other.address: (other, other_advertisement),
            known.address: (known, known_advertisement),
        }

        with patch(self.discover_target, AsyncMock(return_value=devices)):
            result = await interface.scan(known_addresses=(known.address,))

        self.assertIs(result, known)
        self.assertIs(interface.last_advertisement, known_advertisement)

    async def test_scan_logs_the_manufacturer_data_and_its_decoding(
            self) -> None:
        """Test the raw payload and both decode attempts reach the log."""
        device = ScanDevice('GAN12 ui', 'AA:BB:CC:DD:EE:FF')
        mac_payload = bytes(
            [0x00, 0x00, 0x00, 0x22, 0xFB, 0x9D, 0x50, 0x6C, 0x54],
        )
        advertisement = ScanAdvertisement({0x0001: mac_payload})
        interface = BluetoothInterface(Queue())
        devices = {device.address: (device, advertisement)}

        with patch(
                self.discover_target, AsyncMock(return_value=devices),
        ), self.assertLogs(self.logger_name, level='DEBUG') as logs:
            await interface.scan()

        output = '\n'.join(logs.output)
        self.assertIn('manufacturer_data=', output)
        self.assertIn('54:6C:50:9D:FB:22', output)
