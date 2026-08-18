"""ZeroMQ publication of the cube and session event streams."""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Final
from uuid import uuid4

import zmq

from term_timer.config import PUBLISHER_ACTIVE
from term_timer.config import PUBLISHER_ENDPOINTS
from term_timer.constants import PROTOCOL_VERSION
from term_timer.constants import PUBLISH_HIGH_WATER_MARK

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import EventDict

logger = logging.getLogger(__name__)

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
    'disconnect': 'cube.link',
}

# Topics carrying what only term-timer knows. Declared here so that the
# namespace is settled in one place, and so that the prefix rule below
# is checked against every topic of the protocol, not only the published
# ones. They are wired to their emission points later.
SESSION_TOPICS: Final[tuple[str, ...]] = (
    'session.state',
    'session.scramble',
    'session.solve',
    'session.record',
    'session.step',
    'session.train',
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
        self.source = ''
        self.session_id = ''
        self.sequence = 0

    @property
    def active(self) -> bool:
        """Tell whether the publisher is bound and publishing."""
        return self.socket is not None

    def start(self, source: str, endpoints: list[str] | None = None) -> None:
        """
        Bind the publication endpoints and open the stream.

        Each endpoint is bound independently: one that fails is logged
        and skipped, the others keep the stream alive. When none binds,
        or when none is configured at all, the publisher stays idle and
        every later publication is a no-op.

        Args:
            source: Name of the emitting command, carried by every
                message so that a subscriber knows who talks.
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
            logger.warning(
                'Publication is on, but no endpoint is configured: '
                'name them in the [publisher] section of the config file',
            )
            return

        socket: zmq.Socket[bytes] = zmq.Context.instance().socket(zmq.PUB)
        socket.setsockopt(zmq.SNDHWM, PUBLISH_HIGH_WATER_MARK)
        # Closing must never hold the process back, even with messages
        # still queued for a subscriber that stopped reading
        socket.setsockopt(zmq.LINGER, 0)

        bound: list[str] = []
        for endpoint in targets:
            try:
                socket.bind(endpoint)
            except (zmq.ZMQError, OSError) as error:
                logger.warning(
                    'Cannot publish on %s: %s', endpoint, error,
                )
            else:
                bound.append(endpoint)

        if not bound:
            logger.warning('No publication endpoint available')
            socket.close()
            return

        self.socket = socket
        self.endpoints = bound
        self.source = source
        self.session_id = uuid4().hex[:8]
        self.sequence = 0

        logger.info('Publishing events on %s', ', '.join(bound))

    def stop(self) -> None:
        """Close the socket and clean up the sockets files left behind."""
        socket, self.socket = self.socket, None

        if socket is not None:
            socket.close()

        for endpoint in self.endpoints:
            transport, _, address = endpoint.partition('://')
            if transport == 'ipc':
                Path(address).unlink(missing_ok=True)

        self.endpoints = []

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
