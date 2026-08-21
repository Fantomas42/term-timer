"""ZeroMQ publication of the cube and session event streams."""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import BinaryIO
from typing import Final
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover
    # Windows has neither flock nor the ipc transport the lock protects
    fcntl = None  # type: ignore[assignment]

import zmq

from term_timer.config import PUBLISHER_ACTIVE
from term_timer.config import PUBLISHER_ENDPOINTS
from term_timer.constants import PROTOCOL_VERSION
from term_timer.constants import PUBLISH_HIGH_WATER_MARK
from term_timer.constants import PUBLISH_LINGER

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import EventDict

logger = logging.getLogger(__name__)

# Suffix of the file reserving an ipc endpoint. ZeroMQ answers a
# socket file already in use by unlinking it and binding its own, so a
# second session steals the stream of the first instead of being
# refused: the lock is what gives the ipc transport the refusal the tcp
# transport gets from the system for free.
LOCK_SUFFIX: Final[str] = '.lock'

# State of the link with the cube. Named apart because it is the only
# topic with no driver event of its own: a cube announces its departure
# and never its arrival, so the interface publishes the arrival itself.
LINK_TOPIC: Final[str] = 'cube.link'

# Topic of each event the drivers produce. The mapping is what makes the
# hardware stream identical in a real cube and in a replay, both feeding
# the same interface. An event absent from it is simply not published.
CUBE_TOPICS: Final[dict[str, str]] = {
    'facelets': 'cube.facelets',
    'move': 'cube.move',
    'move_history': 'cube.history',
    'gyro': 'cube.gyro',
    'hardware': 'cube.hardware',
    'battery': 'cube.battery',
    'gyro-config': 'cube.config',
    'reset': 'cube.reset',
    'disconnect': LINK_TOPIC,
}

# Topics carrying what only term-timer knows. Named apart, one by one,
# because each has a single emission point in the application and no
# mapping to build: a driver event is dispatched, a session event is
# published where it happens.
STATE_TOPIC: Final[str] = 'session.state'
SCRAMBLE_TOPIC: Final[str] = 'session.scramble'
SOLVE_TOPIC: Final[str] = 'session.solve'
RECORD_TOPIC: Final[str] = 'session.record'
TRAIN_TOPIC: Final[str] = 'session.train'
DRILL_TOPIC: Final[str] = 'session.drill'
END_TOPIC: Final[str] = 'session.end'

# Declared here so that the namespace is settled in one place, and so
# that the prefix rule below is checked against every topic of the
# protocol, not only the published ones. The two reserved ones wait for
# a live CFOP detection, which does not exist, and for a subscriber
# asking for the rotations built downstream of the driver events.
SESSION_TOPICS: Final[tuple[str, ...]] = (
    STATE_TOPIC,
    SCRAMBLE_TOPIC,
    SOLVE_TOPIC,
    RECORD_TOPIC,
    TRAIN_TOPIC,
    DRILL_TOPIC,
    END_TOPIC,
    'session.step',
    'session.rotation',
)

# Every topic of the protocol. ZeroMQ filters subscriptions by prefix,
# so no topic may be a prefix of another: "cube.history" rather than
# "cube.move_history", which a subscriber to "cube.move" would catch.
TOPICS: Final[tuple[str, ...]] = (
    *CUBE_TOPICS.values(),
    *SESSION_TOPICS,
)


class EventPublisher:
    """
    Publisher broadcasting the event streams over a ZeroMQ PUB socket.

    A PUB socket drops what it cannot send instead of blocking, so
    publishing costs a serialisation and a non-blocking write, with no
    sending task, no per-client queue and no dead client to reap. A
    subscriber that never shows up, arrives late or dies mid-session is
    a non-event for the process that times the solves.

    Publication is never critical: a bind that fails, an endpoint
    already taken or a payload that cannot be serialised is logged and
    forgotten. No method raises, so no call site needs to guard.
    """

    def __init__(self) -> None:
        """Build an idle publisher, binding nothing until started."""
        self.socket: zmq.Socket[bytes] | None = None
        self.endpoints: list[str] = []
        self.locks: dict[str, BinaryIO] = {}
        self.source = ''
        self.session_id = ''
        self.sequence = 0

    @property
    def active(self) -> bool:
        """Tell whether the publisher is bound and publishing."""
        return self.socket is not None

    def start(self, source: str = '',
              endpoints: list[str] | None = None) -> None:
        """
        Bind the publication endpoints and open the stream.

        Each endpoint is bound independently: one that fails is
        reported and skipped, the others keep the stream alive. When
        none binds, or when none is configured at all, the publisher
        stays idle and every later publication is a no-op.

        An endpoint another session already publishes on is refused
        rather than taken over, and every refusal is said on screen:
        a session that does not publish what it is asked to publish is
        otherwise indistinguishable from one that does.

        Args:
            source: Name of the emitting command, carried by every
                message so that a subscriber knows who talks. Empty
                keeps the name already given, the command layer naming
                itself long before a cube opens the stream.
            endpoints: Endpoints to bind, defaulting to the configured
                ones.

        """
        if not PUBLISHER_ACTIVE:
            logger.debug('Event publication is disabled')
            return

        if self.socket is not None:
            return

        targets = PUBLISHER_ENDPOINTS if endpoints is None else endpoints
        if not targets:
            message = (
                'Publication is on, but no endpoint is configured: '
                'name them in the publisher section of the config file'
            )
            logger.warning(message)
            self.notify(message, 'warning')
            return

        socket: zmq.Socket[bytes] = zmq.Context.instance().socket(zmq.PUB)
        socket.setsockopt(zmq.SNDHWM, PUBLISH_HIGH_WATER_MARK)
        # Closing must never hold the process back, even with messages
        # still queued for a subscriber that stopped reading
        socket.setsockopt(zmq.LINGER, 0)

        bound: list[str] = []
        refused: list[str] = []

        for endpoint in targets:
            reason = self.reserve(endpoint)

            if reason:
                logger.warning(
                    'Cannot publish on %s: %s', endpoint, reason,
                )
                refused.append(f'{ endpoint } ({ reason })')
                continue

            try:
                socket.bind(endpoint)
            except (zmq.ZMQError, OSError) as error:
                logger.warning(
                    'Cannot publish on %s: %s', endpoint, error,
                )
                refused.append(
                    f'{ endpoint } ({ error.strerror or error })',
                )
                # Reserved just above for a bind that did not happen:
                # holding it would keep the next session out of an
                # endpoint this one publishes nothing on
                self.release(endpoint)
            else:
                bound.append(endpoint)

        if refused:
            self.notify(
                f'Cannot publish on { ", ".join(refused) }',
                'caution',
            )

        if not bound:
            logger.warning('No publication endpoint available')
            self.notify(
                'This session publishes no event at all',
                'warning',
            )
            socket.close()
            self.release()
            return

        self.socket = socket
        self.endpoints = bound
        self.source = source or self.source
        self.session_id = uuid4().hex[:8]
        self.sequence = 0

        logger.info('Publishing events on %s', ', '.join(bound))

    def stop(self, reason: str = 'closed') -> None:
        """
        Say goodbye, close the socket and clean up the socket files.

        The farewell is published before anything is closed, and the
        socket is the only one closed with a delay: every other message
        a subscriber misses is made up for by the next one, while this
        one has no next one.

        Args:
            reason: What ends the session, ``closed`` when the command
                is over, ``interrupted`` on a Ctrl+C and ``crashed``
                when an error carried the process away.

        """
        # Said while the socket is still the current one: publishing
        # is what it is for, and it is about to stop being it
        if self.socket is not None:
            self.publish_end(reason)

        socket, self.socket = self.socket, None

        if socket is not None:
            socket.close(linger=PUBLISH_LINGER)

        for endpoint in self.endpoints:
            transport, _, address = endpoint.partition('://')
            if transport == 'ipc':
                Path(address).unlink(missing_ok=True)

        # Released last, so that no session can take an endpoint back
        # while its socket file is still being deleted here
        self.release()

        self.endpoints = []

    @staticmethod
    def notify(message: str, style: str) -> None:
        """
        Say on screen what the publication cannot do.

        A publication that does not happen is invisible by design:
        nothing raises, nothing blocks, and the log is read long after
        the session. The screen is the only place where "this session
        publishes nothing" can be read while it still matters.

        Args:
            message: What to display.
            style: Style of the console theme to display it with.

        """
        # Imported here and not above: the console lives in the
        # interface package, whose __init__ reaches the Bluetooth
        # interface, which imports this module
        from term_timer.interface.console import console  # noqa: PLC0415

        console.print(message, style=style)

    def reserve(self, endpoint: str) -> str:
        """
        Reserve an endpoint for this session alone.

        Only an ``ipc`` endpoint needs it: a ``tcp`` port already taken
        is refused by the system, while ZeroMQ unlinks the socket file
        of a busy ``ipc`` endpoint and binds its own, handing the
        stream to whoever binds last. Worse, the session robbed that
        way deletes the socket file on its way out — the one of the
        thief — leaving a publisher no client can ever reach again.

        A lock file held next to the socket for the whole session gives
        the ipc transport the same refusal. The kernel releases it
        however the process dies, so a session killed outright leaves
        nothing to clean up by hand.

        Args:
            endpoint: Endpoint about to be bound.

        Returns:
            What forbids binding the endpoint, empty when it is free.

        """
        transport, _, address = endpoint.partition('://')

        if transport != 'ipc' or fcntl is None:
            return ''

        try:
            # Kept open for the whole session: closing the file is what
            # releases the lock, so a context manager would hand the
            # endpoint back the moment it was taken
            handle = Path(  # noqa: SIM115
                f'{ address }{ LOCK_SUFFIX }',
            ).open('ab')
        except OSError as error:
            return str(error.strerror or error)

        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return 'already published by another session'

        self.locks[endpoint] = handle

        return ''

    def release(self, endpoint: str = '') -> None:
        """
        Release the endpoints this session had reserved.

        The lock files are left behind on purpose: deleting one is a
        race of its own, another session having possibly opened it
        already and being about to lock a file nobody else can see any
        more. They are empty, and the next session locks the same ones.

        Args:
            endpoint: The single endpoint to hand back, all of them
                when empty.

        """
        released = (
            [endpoint] if endpoint else list(self.locks)
        )

        for name in released:
            handle = self.locks.pop(name, None)

            if handle is not None:
                handle.close()

    @staticmethod
    def encode(value: Any) -> float:  # noqa: ANN401
        """
        Encode what the JSON serialiser does not handle by itself.

        Event timestamps are the only such value: they become epoch
        floats, the spelling the replay captures already use.

        Args:
            value: Value the serialiser could not encode.

        Returns:
            The JSON-friendly counterpart of the value.

        Raises:
            TypeError: For any other value, so that the publisher logs
                it instead of shipping a broken message.

        """
        if isinstance(value, datetime):
            return value.timestamp()

        msg = f'Cannot serialize { type(value).__name__ }'
        raise TypeError(msg)

    @staticmethod
    def event_data(event: 'EventDict') -> dict[str, Any]:
        """
        Build the payload of a hardware event.

        The field names of the drivers are kept as they are: they are
        the ones the replay captures use, which is what will make a
        recording client a matter of writing down what it receives.

        Args:
            event: Event produced by a driver or by a replay.

        Returns:
            The event without its name, which the topic already tells.

        """
        data: dict[str, Any] = {
            key: value
            for key, value in event.items()
            if key != 'event'
        }

        if event['event'] == 'disconnect':
            # A link topic answers "is the cube there", which a subscriber
            # cannot deduce from the name of a one-shot event
            data['connected'] = False
            data['reason'] = 'lost'

        return data

    def publish(self, topic: str, data: dict[str, Any]) -> None:
        """
        Publish one message on a topic.

        The envelope makes every message self-describing: a late
        subscriber knows who emits, on which session and how many
        messages it missed, without ever having seen a first one.

        Args:
            topic: Topic of the message, also sent as its own frame so
                that ZeroMQ filters on it.
            data: Payload of the message, always an object so that a
                field can be added later without breaking a subscriber.

        """
        socket = self.socket
        if socket is None:
            return

        sequence = self.sequence
        # Counted even when the send fails: the hole it leaves is what
        # tells a subscriber that a message never reached it
        self.sequence += 1

        try:
            payload = json.dumps(
                {
                    'v': PROTOCOL_VERSION,
                    'seq': sequence,
                    'ts': time.time(),
                    'src': self.source,
                    'sid': self.session_id,
                    'topic': topic,
                    'data': data,
                },
                ensure_ascii=False,
                default=self.encode,
            )

            socket.send_multipart(
                [topic.encode('utf-8'), payload.encode('utf-8')],
                zmq.NOBLOCK,
            )
        except Exception as error:  # noqa: BLE001
            logger.debug('Cannot publish %s: %s', topic, error)

    def publish_link(self, *, connected: bool, reason: str) -> None:
        """
        Publish the state of the link with the cube.

        The topic answers "is the cube there", a question no driver
        event answers: a cube announces its departure, never its
        arrival, and says nothing at all when the link simply drops.

        Args:
            connected: Whether the cube is reachable from now on.
            reason: What made the link change, ``opened`` on a
                connection, ``closed`` when the application let go and
                ``lost`` when the link dropped on its own.

        """
        self.publish(
            LINK_TOPIC,
            {
                'connected': connected,
                'reason': reason,
            },
        )

    def publish_end(self, reason: str) -> None:
        """
        Publish the end of the session, the last message of the stream.

        Nothing else says that the stream is over: a publisher that
        stops falls silent, which a subscriber cannot tell from a
        session where nothing happens. This is the one message a client
        waits for to let go of the state it built.

        The reason is what a client does something with: a session over
        is a session to forget, an interrupted or crashed one is a
        session that may come back.

        Args:
            reason: What ends the session, ``closed``, ``interrupted``
                or ``crashed``.

        """
        self.publish(
            END_TOPIC,
            {
                'reason': reason,
            },
        )

    def publish_events(self, events: list['EventDict']) -> None:
        """
        Publish a batch of hardware events, one message each.

        Args:
            events: Events as the drivers produce them.

        """
        if self.socket is None:
            return

        for event in events:
            name = event['event']
            topic = CUBE_TOPICS.get(name)

            if topic is None:
                logger.debug('No topic for event %s', name)
                continue

            self.publish(topic, self.event_data(event))


PUBLISHER = EventPublisher()
