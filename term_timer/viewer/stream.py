"""Reading of the ZeroMQ event stream the viewer is fed by."""
import json
import logging
import threading
from collections.abc import Callable
from typing import Any

import zmq

from term_timer.constants import STREAM_POLL_TIMEOUT

logger = logging.getLogger(__name__)

Envelope = dict[str, Any]
Handler = Callable[[Envelope], None]

# What the viewer listens to. ZeroMQ filters on the prefix of the topic
# frame, so one string covers the whole hardware plane and leaves the
# session one, which the viewer has no use for, on the wire.
CUBE_PREFIX = 'cube.'


class EventStream:
    """
    A subscription to the event stream, read in a thread of its own.

    The subscriber connects and the publisher binds, which is what makes
    the viewer independent of the order the two are started in: a stream
    opened before term-timer waits, and one whose publisher goes away
    reconnects on its own when it comes back.

    Nothing here knows what a cube is: frames come in, envelopes go out,
    and what they mean is the business of the handler.
    """

    def __init__(
            self,
            endpoint: str,
            prefixes: tuple[str, ...] = (CUBE_PREFIX,),
    ) -> None:
        """
        Prepare a subscription, connecting nothing yet.

        Args:
            endpoint: ZeroMQ endpoint of the publisher to connect to.
            prefixes: Topic prefixes to subscribe to.

        """
        self.endpoint = endpoint
        self.prefixes = prefixes
        self.socket: zmq.Socket[bytes] | None = None
        self.thread: threading.Thread | None = None
        self.running = False

    def open(self) -> None:
        """Connect the subscriber and start filtering on the prefixes."""
        if self.socket is not None:
            return

        socket: zmq.Socket[bytes] = zmq.Context.instance().socket(zmq.SUB)
        # A viewer that goes away must never hold the process back on
        # what it did not read
        socket.setsockopt(zmq.LINGER, 0)

        for prefix in self.prefixes:
            socket.setsockopt(zmq.SUBSCRIBE, prefix.encode('utf-8'))

        socket.connect(self.endpoint)

        self.socket = socket
        logger.info('Listening to %s', self.endpoint)

    def close(self) -> None:
        """Close the subscriber, whatever it still had to read."""
        socket, self.socket = self.socket, None

        if socket is not None:
            socket.close()

    @staticmethod
    def decode(frames: list[bytes]) -> Envelope | None:
        """
        Read the envelope a pair of frames carries.

        Args:
            frames: The frames of one message, topic then payload.

        Returns:
            The envelope, or nothing when the message is not one.

        """
        if len(frames) != 2:
            logger.debug('Dropping a message of %d frames', len(frames))
            return None

        try:
            message = json.loads(frames[1])
        except (ValueError, UnicodeDecodeError) as error:
            logger.debug('Cannot read a message: %s', error)
            return None

        if not isinstance(message, dict):
            logger.debug('Dropping a message that is not an envelope')
            return None

        return message

    def receive(self, handler: Handler) -> bool:
        """
        Wait for one message, and hand its envelope over.

        Args:
            handler: What the envelope is given to.

        Returns:
            True when a message was read, False when the wait timed out.

        """
        socket = self.socket
        if socket is None:
            return False

        if not socket.poll(STREAM_POLL_TIMEOUT):
            return False

        message = self.decode(socket.recv_multipart())

        if message is not None:
            handler(message)

        return True

    def listen(self, handler: Handler) -> None:
        """
        Read the stream until the subscription is stopped.

        A socket closed under a reader is what stopping looks like from
        here, so the error it raises ends the loop instead of reaching
        the thread.

        Args:
            handler: What every envelope is given to.

        """
        # A socket taken away is the other way the loop ends: closing
        # is what stopping looks like from a reader that is waiting
        while self.running and self.socket is not None:
            try:
                self.receive(handler)
            except zmq.ZMQError as error:
                logger.debug('End of the stream: %s', error)
                return
            except Exception:
                logger.exception('Cannot handle a message')

    def start(self, handler: Handler) -> None:
        """
        Open the subscription and read it in a thread of its own.

        The window owns the main thread, so the stream gets one for
        itself: the moves reach the viewer the moment they arrive,
        which is what its animation reads its cadence from.

        Args:
            handler: What every envelope is given to.

        """
        self.open()
        self.running = True

        self.thread = threading.Thread(
            target=self.listen,
            args=(handler,),
            name='cube-stream',
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        """Stop reading, wait for the thread, and close the socket."""
        self.running = False

        thread, self.thread = self.thread, None
        if thread is not None:
            thread.join(timeout=1.0)

        self.close()
