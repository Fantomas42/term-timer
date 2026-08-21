"""
Tests for the ZeroMQ event publisher.

Everything runs on an "ipc" endpoint of a temporary directory, with real
sockets and no cube anywhere: what is checked is the envelope, the topic
mapping, the prefix filtering, and above all that nothing a publication
can hit ever reaches the caller.
"""
import json
import tempfile
import time
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import zmq
from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import DisconnectEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDictNoState
from term_timer.bluetooth.annotations import GyroEventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.constants import PROTOCOL_VERSION
from term_timer.publisher import CUBE_TOPICS
from term_timer.publisher import END_TOPIC
from term_timer.publisher import TOPICS
from term_timer.publisher import EventPublisher

# Time left to a subscription to reach the publisher. A PUB socket drops
# what it sends before its subscribers are known, the "slow joiner" of
# ZeroMQ, which bites the test itself first
HANDSHAKE_DELAY = 0.3

# Time waited for a first message, then for the next one before calling
# the stream idle
RECEIVE_TIMEOUT = 1000
DRAIN_TIMEOUT = 100

TIMESTAMP = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)

Message = tuple[str, dict[str, Any]]


def move_event(move: str = 'R', serial: int = 42) -> MoveEventDict:
    """
    Build a move event as a driver produces it.

    Args:
        move: Notation of the move.
        serial: Monotonic move counter of the cube.

    Returns:
        The event, ready to be published.

    """
    return {
        'event': 'move',
        'clock': 128734,
        'timestamp': TIMESTAMP,
        'serial': serial,
        'local_timestamp': TIMESTAMP,
        'cube_timestamp': 14872.0,
        'face': 0,
        'direction': 0,
        'move': move,
    }


def gyro_event() -> GyroEventDict:
    """
    Build a gyroscope event as a driver produces it.

    Returns:
        The event, ready to be published.

    """
    return {
        'event': 'gyro',
        'clock': 128735,
        'timestamp': TIMESTAMP,
        'quaternion': {'x': 0.1, 'y': 0.2, 'z': 0.3, 'w': 0.9},
        'velocity': {'x': 0.0, 'y': 0.0, 'z': 0.0},
    }


def facelets_event() -> FaceletsEventDictNoState:
    """
    Build a facelets event as a driver produces it.

    Returns:
        The event, ready to be published.

    """
    return {
        'event': 'facelets',
        'clock': 128736,
        'timestamp': TIMESTAMP,
        'serial': 1,
        'facelets': VCube(size=3).state,
    }


def battery_event() -> BatteryEventDict:
    """
    Build a battery event as a driver produces it.

    Returns:
        The event, ready to be published.

    """
    return {
        'event': 'battery',
        'clock': 0,
        'timestamp': TIMESTAMP,
        'level': 80,
        'charging_state': 0,
    }


def disconnect_event() -> DisconnectEventDict:
    """
    Build a disconnection event as the interface produces it.

    Returns:
        The event, ready to be published.

    """
    return {
        'event': 'disconnect',
        'clock': 0,
        'timestamp': TIMESTAMP,
    }


class PublisherTestCase(unittest.TestCase):
    """Base case wiring a publisher and its subscribers on a temp path."""

    def setUp(self) -> None:
        """Prepare an endpoint of its own and an idle publisher."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        self.directory = Path(directory.name)
        self.socket_file = self.directory / 'cube.ipc'
        self.endpoint = f'ipc://{ self.socket_file }'
        self.missing = f'ipc://{ self.directory / "missing" / "cube.ipc" }'

        activation = patch(
            'term_timer.publisher.PUBLISHER_ACTIVE', new=True,
        )
        activation.start()
        self.addCleanup(activation.stop)

        self.context = zmq.Context.instance()
        self.publisher = EventPublisher()
        self.addCleanup(self.publisher.stop)

    def start(self, source: str = 'solve') -> None:
        """
        Start the publisher on the temporary endpoint.

        Args:
            source: Name of the emitting command.

        """
        self.publisher.start(source, [self.endpoint])

    def subscribe(self, topic: bytes = b'') -> 'zmq.Socket[bytes]':
        """
        Connect a subscriber and let the handshake happen.

        Args:
            topic: Topic prefix subscribed to, empty for everything.

        Returns:
            The connected subscriber socket.

        """
        socket: zmq.Socket[bytes] = self.context.socket(zmq.SUB)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.SUBSCRIBE, topic)
        socket.connect(self.endpoint)
        self.addCleanup(socket.close)

        time.sleep(HANDSHAKE_DELAY)

        return socket

    @staticmethod
    def drain(socket: 'zmq.Socket[bytes]') -> list[Message]:
        """
        Read every message waiting, in order.

        Args:
            socket: Subscriber to read from.

        Returns:
            The decoded messages, as topic and envelope pairs.

        """
        messages: list[Message] = []
        timeout = RECEIVE_TIMEOUT

        while socket.poll(timeout):
            topic, payload = socket.recv_multipart()
            messages.append((topic.decode('utf-8'), json.loads(payload)))
            timeout = DRAIN_TIMEOUT

        return messages

    def receive(self, socket: 'zmq.Socket[bytes]') -> Message:
        """
        Read the one message expected, failing when it is not alone.

        Args:
            socket: Subscriber to read from.

        Returns:
            The decoded message, as a topic and envelope pair.

        """
        messages = self.drain(socket)

        if len(messages) != 1:
            self.fail(f'Expected one message, got { len(messages) }')

        return messages[0]

    @staticmethod
    def topics(messages: list[Message]) -> list[str]:
        """
        List the topics of a batch of messages.

        Args:
            messages: Messages read from a subscriber.

        Returns:
            The topics, in the order they were received.

        """
        return [topic for topic, _ in messages]


class TopicsTestCase(unittest.TestCase):
    """The naming rules the subscription filtering relies on."""

    def test_no_topic_is_a_prefix_of_another(self) -> None:
        """A subscription to a topic never catches another one."""
        for topic in TOPICS:
            for other in TOPICS:
                if other == topic:
                    continue

                self.assertFalse(
                    other.startswith(topic),
                    f'{ other } is caught by a subscription to { topic }',
                )

    def test_topics_are_unique(self) -> None:
        """No topic is declared twice."""
        self.assertEqual(len(TOPICS), len(set(TOPICS)))

    def test_cube_topics_are_all_namespaced(self) -> None:
        """Every hardware event lands in the cube namespace."""
        for topic in CUBE_TOPICS.values():
            self.assertTrue(topic.startswith('cube.'))


class EnvelopeTestCase(PublisherTestCase):
    """The envelope every message carries."""

    def test_envelope_is_complete(self) -> None:
        """A message describes itself entirely."""
        self.start('train')
        socket = self.subscribe()

        self.publisher.publish('cube.move', {'move': "R'"})

        topic, envelope = self.receive(socket)

        self.assertEqual(topic, 'cube.move')
        self.assertEqual(envelope['v'], PROTOCOL_VERSION)
        self.assertEqual(envelope['seq'], 0)
        self.assertEqual(envelope['src'], 'train')
        self.assertEqual(envelope['sid'], self.publisher.session_id)
        self.assertEqual(envelope['topic'], 'cube.move')
        self.assertEqual(envelope['data'], {'move': "R'"})
        self.assertAlmostEqual(envelope['ts'], time.time(), delta=5)

    def test_sequence_is_monotonic_without_hole(self) -> None:
        """Counting starts at zero and never skips a published message."""
        self.start()
        socket = self.subscribe()

        for index in range(5):
            self.publisher.publish('cube.move', {'move': 'R', 'i': index})

        messages = self.drain(socket)

        self.assertEqual(len(messages), 5)
        self.assertEqual(
            [envelope['seq'] for _, envelope in messages],
            [0, 1, 2, 3, 4],
        )

    def test_session_id_is_stable_across_messages(self) -> None:
        """The session identifier names the process, not the message."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish('cube.reset', {})
        self.publisher.publish('cube.reset', {})

        messages = self.drain(socket)
        identifiers = {envelope['sid'] for _, envelope in messages}

        self.assertEqual(len(messages), 2)
        self.assertEqual(len(identifiers), 1)
        self.assertTrue(identifiers.pop())

    def test_payload_keeps_non_ascii_characters(self) -> None:
        """An accented payload travels as it is written."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish('session.state', {'state': 'inspecté'})

        _, envelope = self.receive(socket)

        self.assertEqual(envelope['data']['state'], 'inspecté')


class PublishEventsTestCase(PublisherTestCase):
    """The mapping from driver events to hardware topics."""

    def test_one_message_per_event_in_order(self) -> None:
        """A batch of events is published event by event."""
        self.start()
        socket = self.subscribe()

        events: list[EventDict] = [
            facelets_event(), move_event(), gyro_event(),
        ]
        self.publisher.publish_events(events)

        self.assertEqual(
            self.topics(self.drain(socket)),
            ['cube.facelets', 'cube.move', 'cube.gyro'],
        )

    def test_move_history_has_its_own_topic(self) -> None:
        """Caught up moves are told apart from live ones."""
        self.start()
        socket = self.subscribe()

        event = move_event()
        event['event'] = 'move_history'
        self.publisher.publish_events([event])

        topic, _ = self.receive(socket)

        self.assertEqual(topic, 'cube.history')

    def test_event_data_keeps_the_driver_field_names(self) -> None:
        """A payload is the event itself, timestamps aside."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish_events([move_event(move='U', serial=7)])

        _, envelope = self.receive(socket)

        self.assertEqual(
            envelope['data'],
            {
                'clock': 128734,
                'timestamp': TIMESTAMP.timestamp(),
                'serial': 7,
                'local_timestamp': TIMESTAMP.timestamp(),
                'cube_timestamp': 14872.0,
                'face': 0,
                'direction': 0,
                'move': 'U',
            },
        )

    def test_event_name_is_dropped_from_the_data(self) -> None:
        """The topic already tells what the event is."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish_events([battery_event()])

        _, envelope = self.receive(socket)

        self.assertNotIn('event', envelope['data'])
        self.assertEqual(envelope['data']['level'], 80)

    def test_disconnect_becomes_a_link_state(self) -> None:
        """A lost link is published as the state of the link."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish_events([disconnect_event()])

        topic, envelope = self.receive(socket)

        self.assertEqual(topic, 'cube.link')
        self.assertFalse(envelope['data']['connected'])
        self.assertEqual(envelope['data']['reason'], 'lost')

    def test_unknown_event_is_skipped(self) -> None:
        """An event with no topic never stops the batch."""
        self.start()
        socket = self.subscribe()

        unknown: Any = {
            'event': 'rotation', 'clock': 0, 'timestamp': TIMESTAMP,
        }
        self.publisher.publish_events([unknown, battery_event()])

        self.assertEqual(self.topics(self.drain(socket)), ['cube.battery'])


class PublishLinkTestCase(PublisherTestCase):
    """The state of the link, which no driver event carries."""

    def test_a_connection_is_published(self) -> None:
        """A cube arriving is announced, though it never says so."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish_link(connected=True, reason='opened')

        topic, envelope = self.receive(socket)

        self.assertEqual(topic, 'cube.link')
        self.assertTrue(envelope['data']['connected'])
        self.assertEqual(envelope['data']['reason'], 'opened')

    def test_a_closed_link_is_told_apart_from_a_lost_one(self) -> None:
        """The reason is what a subscriber decides on, not the topic."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish_link(connected=False, reason='closed')
        self.publisher.publish_events([disconnect_event()])

        reasons = [
            envelope['data']['reason']
            for _, envelope in self.drain(socket)
        ]

        self.assertEqual(reasons, ['closed', 'lost'])

    def test_link_is_published_on_the_same_topic_as_the_event(self) -> None:
        """
        Both spellings of the link land on one topic.

        A subscriber filtering on it must see the whole life of the
        link, whether the news comes from the interface or from a
        driver event.
        """
        self.start()
        socket = self.subscribe(b'cube.link')

        self.publisher.publish_link(connected=True, reason='opened')
        self.publisher.publish_events([disconnect_event(), battery_event()])

        self.assertEqual(
            self.topics(self.drain(socket)), ['cube.link', 'cube.link'],
        )


class PublishEndTestCase(PublisherTestCase):
    """The farewell, the one message a falling silence cannot replace."""

    def test_stopping_says_goodbye(self) -> None:
        """A stream that ends says so before it closes."""
        self.start()
        socket = self.subscribe()

        self.publisher.stop()

        topic, envelope = self.receive(socket)

        self.assertEqual(topic, END_TOPIC)
        self.assertEqual(envelope['data']['reason'], 'closed')

    def test_the_reason_travels(self) -> None:
        """A session cut short is not a session over."""
        self.start()
        socket = self.subscribe()

        self.publisher.stop('interrupted')

        _, envelope = self.receive(socket)

        self.assertEqual(envelope['data']['reason'], 'interrupted')

    def test_the_farewell_is_the_last_message(self) -> None:
        """Nothing of the session comes after it."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish_events([move_event()])
        self.publisher.stop()

        self.assertEqual(
            self.topics(self.drain(socket)), ['cube.move', END_TOPIC],
        )

    def test_the_farewell_carries_the_session_it_ends(self) -> None:
        """The envelope is the one of the stream it closes."""
        self.start('train')
        socket = self.subscribe()

        session_id = self.publisher.session_id
        self.publisher.publish_events([move_event()])
        self.publisher.stop()

        _, envelope = self.drain(socket)[-1]

        self.assertEqual(envelope['src'], 'train')
        self.assertEqual(envelope['sid'], session_id)
        self.assertEqual(envelope['seq'], 1)

    def test_an_idle_publisher_says_nothing(self) -> None:
        """A session that never published has no stream to close."""
        self.publisher.stop()

        self.assertEqual(self.publisher.sequence, 0)

    def test_a_second_stop_says_nothing_more(self) -> None:
        """The farewell is said once, whatever the way out."""
        self.start()
        socket = self.subscribe()

        self.publisher.stop()
        self.publisher.stop()

        self.assertEqual(self.topics(self.drain(socket)), [END_TOPIC])

    def test_a_subscriber_filters_the_farewell_on_its_own(self) -> None:
        """The topic is reachable without subscribing to everything."""
        self.start()
        socket = self.subscribe(b'session.end')

        self.publisher.publish_events([move_event()])
        self.publisher.stop()

        self.assertEqual(self.topics(self.drain(socket)), [END_TOPIC])


class SubscriptionTestCase(PublisherTestCase):
    """What subscribers see, alone or together."""

    def test_two_subscribers_receive_the_same_thing(self) -> None:
        """Neither subscriber knows the other one is there."""
        self.start()
        first = self.subscribe()
        second = self.subscribe()

        self.publisher.publish_events([move_event()])

        self.assertEqual(self.drain(first), self.drain(second))

    def test_prefix_filtering_isolates_the_streams(self) -> None:
        """A subscription to the hardware ignores the session."""
        self.start()
        socket = self.subscribe(b'cube.')

        self.publisher.publish('session.state', {'state': 'solving'})
        self.publisher.publish('cube.move', {'move': 'R'})

        self.assertEqual(self.topics(self.drain(socket)), ['cube.move'])

    def test_late_subscriber_misses_what_it_did_not_see(self) -> None:
        """The sequence is what tells a late subscriber it arrived late."""
        self.start()

        self.publisher.publish('cube.move', {'move': 'R'})

        socket = self.subscribe()
        self.publisher.publish('cube.move', {'move': 'U'})

        _, envelope = self.receive(socket)

        self.assertEqual(envelope['seq'], 1)


class LifecycleTestCase(PublisherTestCase):
    """Starting, stopping, and everything that may go wrong doing so."""

    def test_publisher_starts_inactive(self) -> None:
        """A publisher binds nothing until it is started."""
        self.assertFalse(self.publisher.active)

    def test_start_binds_and_activates(self) -> None:
        """Starting binds the endpoint it is given."""
        self.start()

        self.assertTrue(self.publisher.active)
        self.assertEqual(self.publisher.endpoints, [self.endpoint])
        self.assertTrue(self.socket_file.exists())

    def test_start_is_a_no_op_when_publication_is_disabled(self) -> None:
        """Publication off, nothing is bound at all."""
        with patch('term_timer.publisher.PUBLISHER_ACTIVE', new=False):
            self.start()

        self.assertFalse(self.publisher.active)
        self.assertFalse(self.socket_file.exists())

    def test_start_is_a_no_op_when_no_endpoint_is_configured(self) -> None:
        """Publication on but no endpoint named, nothing is bound."""
        self.publisher.start('solve', [])

        self.assertFalse(self.publisher.active)
        self.assertEqual(self.publisher.endpoints, [])

    def test_start_twice_keeps_the_first_socket(self) -> None:
        """A second start never rebinds an endpoint already taken."""
        self.start()
        socket = self.publisher.socket

        self.publisher.start('train', [self.endpoint])

        self.assertIs(self.publisher.socket, socket)
        self.assertEqual(self.publisher.source, 'solve')

    def test_start_keeps_the_source_named_beforehand(self) -> None:
        """
        A source given early survives a start naming none.

        Only the command layer knows which command runs, and it knows
        it long before a cube opens the stream: it names the publisher
        once, and whoever connects the cube starts it without having to
        carry that name down to the Bluetooth interface.
        """
        self.publisher.source = 'ghost'

        self.publisher.start('', [self.endpoint])
        socket = self.subscribe()

        self.publisher.publish('cube.move', {'move': 'R'})

        _, envelope = self.receive(socket)

        self.assertEqual(envelope['src'], 'ghost')

    def test_start_overrides_the_source_when_given_one(self) -> None:
        """A start naming itself wins over what was declared before."""
        self.publisher.source = 'ghost'

        self.publisher.start('bt-info', [self.endpoint])

        self.assertEqual(self.publisher.source, 'bt-info')

    def test_start_uses_the_configured_endpoints_by_default(self) -> None:
        """Given no endpoint, the configured ones are bound."""
        with patch(
                'term_timer.publisher.PUBLISHER_ENDPOINTS',
                new=[self.endpoint],
        ):
            self.publisher.start('solve')

        self.assertEqual(self.publisher.endpoints, [self.endpoint])

    def test_start_skips_an_endpoint_it_cannot_bind(self) -> None:
        """One endpoint down, the stream lives on the others."""
        self.publisher.start('solve', [self.missing, self.endpoint])
        socket = self.subscribe()

        self.publisher.publish('cube.move', {'move': 'R'})

        self.assertTrue(self.publisher.active)
        self.assertEqual(self.publisher.endpoints, [self.endpoint])
        self.assertEqual(len(self.drain(socket)), 1)

    def test_start_stays_inactive_when_no_endpoint_binds(self) -> None:
        """No endpoint at all leaves the session running, unpublished."""
        self.publisher.start('solve', [self.missing, 'bogus://cube'])

        self.assertFalse(self.publisher.active)
        self.assertEqual(self.publisher.endpoints, [])

    def test_stop_closes_and_removes_the_socket_file(self) -> None:
        """Stopping leaves nothing behind on the filesystem."""
        # A tcp endpoint alongside the socket file: only the second one
        # leaves a file to clean up
        self.publisher.start('solve', [self.endpoint, 'tcp://127.0.0.1:*'])

        self.publisher.stop()

        self.assertFalse(self.publisher.active)
        self.assertEqual(self.publisher.endpoints, [])
        self.assertFalse(self.socket_file.exists())

    def test_stop_is_a_no_op_when_never_started(self) -> None:
        """Stopping an idle publisher is silent."""
        self.publisher.stop()

        self.assertFalse(self.publisher.active)

    def test_stop_twice_does_not_raise(self) -> None:
        """A second stop has nothing left to close."""
        self.start()

        self.publisher.stop()
        self.publisher.stop()

        self.assertFalse(self.publisher.active)


class SilenceTestCase(PublisherTestCase):
    """Nothing a publication may hit ever reaches the caller."""

    def test_publish_before_start_is_silent(self) -> None:
        """Publishing with no socket costs nothing and counts nothing."""
        self.publisher.publish('cube.move', {'move': 'R'})

        self.assertEqual(self.publisher.sequence, 0)

    def test_publish_events_before_start_is_silent(self) -> None:
        """A batch of events with no socket is dropped as a whole."""
        self.publisher.publish_events([move_event()])

        self.assertEqual(self.publisher.sequence, 0)

    def test_publish_after_stop_is_silent(self) -> None:
        """Publishing after the close is a return, not an error."""
        self.start()
        self.publisher.publish('cube.move', {'move': 'R'})
        self.publisher.stop()

        self.publisher.publish('cube.move', {'move': 'U'})

        # The move, then the farewell of the stop: what comes after it
        # is what leaves no trace
        self.assertEqual(self.publisher.sequence, 2)

    def test_publish_without_subscriber_does_not_block(self) -> None:
        """Nobody listening is the normal case, and it is free."""
        self.start()

        started = time.monotonic()
        for _ in range(100):
            self.publisher.publish_events([gyro_event()])

        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(self.publisher.sequence, 100)

    def test_serialization_failure_does_not_raise(self) -> None:
        """An unserialisable payload leaves a hole, and nothing more."""
        self.start()
        socket = self.subscribe()

        self.publisher.publish('cube.move', {'move': object()})
        self.publisher.publish('cube.move', {'move': 'R'})

        _, envelope = self.receive(socket)

        self.assertEqual(envelope['seq'], 1)

    def test_send_failure_does_not_raise(self) -> None:
        """A socket dying under the publisher stays its own problem."""
        self.start()

        if self.publisher.socket is None:
            self.fail('The publisher did not bind')

        self.publisher.socket.close()
        self.publisher.publish('cube.move', {'move': 'R'})

        self.assertEqual(self.publisher.sequence, 1)

    def test_encode_refuses_what_it_does_not_know(self) -> None:
        """An unknown type is refused rather than guessed."""
        with self.assertRaises(TypeError):
            EventPublisher.encode(object())

    def test_encode_turns_a_datetime_into_an_epoch(self) -> None:
        """Timestamps travel as the replay captures spell them."""
        self.assertEqual(
            EventPublisher.encode(TIMESTAMP), TIMESTAMP.timestamp(),
        )


class ExclusivityTestCase(PublisherTestCase):
    """
    What two sessions publishing at once do to each other.

    ZeroMQ hands an ipc endpoint to whoever binds last, silently, so
    the exclusivity tested here is the one the lock file adds. The
    locks are held per open file, not per process, so a second
    publisher of this very process is refused exactly as a second
    term-timer would be.
    """

    def setUp(self) -> None:
        """Add a second publisher, the one arriving late."""
        super().setUp()

        self.intruder = EventPublisher()
        self.addCleanup(self.intruder.stop)

    def test_a_second_session_cannot_take_an_ipc_endpoint(self) -> None:
        """An endpoint already published on is refused, not stolen."""
        self.start()

        self.intruder.start('ghost', [self.endpoint])

        self.assertFalse(self.intruder.active)
        self.assertEqual(self.intruder.endpoints, [])

    def test_the_first_session_keeps_its_endpoint(self) -> None:
        """Being intruded upon changes nothing for the first session."""
        self.start()
        socket = self.subscribe()

        self.intruder.start('ghost', [self.endpoint])
        self.publisher.publish('cube.move', {'move': 'R'})

        topic, envelope = self.receive(socket)

        self.assertTrue(self.publisher.active)
        self.assertTrue(self.socket_file.exists())
        self.assertEqual(topic, 'cube.move')
        self.assertEqual(envelope['src'], 'solve')

    def test_a_second_session_keeps_the_endpoints_left(self) -> None:
        """One endpoint taken, the other still opens the stream."""
        self.start()
        spare = f'ipc://{ self.directory / "spare.ipc" }'

        self.intruder.start('ghost', [self.endpoint, spare])

        self.assertTrue(self.intruder.active)
        self.assertEqual(self.intruder.endpoints, [spare])

    def test_stopping_hands_the_endpoint_back(self) -> None:
        """A session gone releases what it had reserved."""
        self.start()
        self.publisher.stop()

        self.intruder.start('ghost', [self.endpoint])

        self.assertTrue(self.intruder.active)
        self.assertEqual(self.intruder.endpoints, [self.endpoint])

    def test_a_refused_endpoint_frees_its_lock(self) -> None:
        """
        A publisher binding nothing keeps no reservation.

        Nothing is published, so nothing is reserved: the endpoints it
        could not use must be left to whoever comes next.
        """
        self.start()

        self.intruder.start('ghost', [self.endpoint])

        self.assertEqual(self.intruder.locks, {})

    def test_a_lock_is_handed_back_when_the_bind_fails(self) -> None:
        """
        A reservation is worth nothing without the bind that follows it.

        The endpoint is locked before it is bound, so a bind failing
        afterwards would leave the session holding an endpoint it
        publishes nothing on, and the next one out of it for good.
        """
        # A directory where the socket file goes: the lock file next to
        # it opens fine, and only the bind that follows fails. Another
        # endpoint binds alongside, so the session lives on holding the
        # reservation of the one it could not use
        blocked = self.directory / 'taken.ipc'
        blocked.mkdir()
        endpoint = f'ipc://{ blocked }'

        self.publisher.start('solve', [endpoint, self.endpoint])

        self.assertTrue(self.publisher.active)
        self.assertEqual(list(self.publisher.locks), [self.endpoint])

        blocked.rmdir()

        self.assertEqual(self.intruder.reserve(endpoint), '')

    def test_a_tcp_endpoint_is_not_locked(self) -> None:
        """Only ipc needs a lock, the system refuses a taken port."""
        self.publisher.start('solve', ['tcp://127.0.0.1:*'])

        self.assertTrue(self.publisher.active)
        self.assertEqual(self.publisher.locks, {})

    def test_a_lock_file_is_left_behind_on_purpose(self) -> None:
        """Deleting a lock file is a race, so it survives the session."""
        self.start()
        self.publisher.stop()

        self.assertTrue(
            Path(f'{ self.socket_file }.lock').exists(),
        )

    def test_a_stale_socket_file_is_not_an_endpoint_taken(self) -> None:
        """A session killed outright blocks nothing on its way out."""
        self.socket_file.touch()
        Path(f'{ self.socket_file }.lock').touch()

        self.start()

        self.assertTrue(self.publisher.active)


class ReportTestCase(PublisherTestCase):
    """What a session says on screen about its own publication."""

    def setUp(self) -> None:
        """Watch the console the publisher writes to."""
        super().setUp()

        self.console = patch(
            'term_timer.interface.console.console',
        ).start()
        self.addCleanup(patch.stopall)

    def messages(self) -> list[str]:
        """
        List what has been printed on screen.

        Returns:
            The messages, in the order they were displayed.

        """
        return [
            str(call.args[0])
            for call in self.console.print.call_args_list
        ]

    def test_a_working_publication_says_nothing(self) -> None:
        """Nothing to warn about, nothing on screen."""
        self.start()

        self.assertEqual(self.messages(), [])

    def test_a_missing_configuration_is_told(self) -> None:
        """Publication on and no endpoint named is said out loud."""
        self.publisher.start('solve', [])

        self.assertIn('no endpoint is configured', self.messages()[0])

    def test_a_refused_endpoint_is_told(self) -> None:
        """An endpoint another session holds is named on screen."""
        intruder = EventPublisher()
        self.addCleanup(intruder.stop)
        intruder.start('ghost', [self.endpoint])

        self.publisher.start('solve', [self.endpoint])

        self.assertIn(
            'already published by another session', self.messages()[0],
        )
        self.assertIn(self.endpoint, self.messages()[0])

    def test_a_session_publishing_nothing_is_told(self) -> None:
        """The silence of a session is never silent itself."""
        self.publisher.start('solve', [self.missing])

        self.assertIn('publishes no event at all', self.messages()[-1])

    def test_a_partial_publication_is_told(self) -> None:
        """One endpoint down out of two is worth saying too."""
        self.publisher.start('solve', [self.missing, self.endpoint])

        self.assertTrue(self.publisher.active)
        self.assertEqual(len(self.messages()), 1)
        self.assertIn(self.missing, self.messages()[0])
