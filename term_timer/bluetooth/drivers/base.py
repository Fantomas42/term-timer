"""Base driver class for Bluetooth cube communication."""
import logging
import time
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from typing import ClassVar

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.message import GanProtocolMessage

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import MessageHandler

logger = logging.getLogger(__name__)


class Driver:
    """
    Base class for Bluetooth smart cube communication drivers.

    Defines the interface for cube-specific protocol implementations.
    Subclasses must implement encryption, command handling, and event
    processing for their specific cube model.
    """

    service_uid: ClassVar[str] = ''
    state_characteristic_uid: ClassVar[str] = ''
    command_characteristic_uid: ClassVar[str] = ''
    init_commands: ClassVar[list[str]] = [
        'REQUEST_FACELETS',
        'REQUEST_HARDWARE',
        'REQUEST_BATTERY',
    ]

    # Width of the header, in bits, before the payload of a message.
    # V1 : bleProtoId on 4 bits, no dataLength.
    # V2 : head(8) + bleProtoId(8) + dataLength(8).
    # V3 : bleProtoId(8) + dataLength(8).
    payload_offset: ClassVar[int] = 8

    # Opcode -> name of the method decoding it. Redefined *entirely* by
    # each generation : the opcode spaces do not overlap from one
    # generation to the next, and 0x02 means "facelets" in V2 but
    # "cube solved" in V3. Only the *methods* are inherited.
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {}

    def __init__(self, client: BleakClient,
                 *, use_gyroscope: bool) -> None:
        """
        Initialize driver with BleakClient and encryption.

        Args:
            client: The BLE client connection to the cube.
            use_gyroscope: Whether the driver should use gyroscope data.

        """
        self.client: BleakClient = client
        self.use_gyroscope = use_gyroscope

        self.events: list[EventDict] = []
        self.cypher: GanGen2CubeEncrypter = self.init_cypher()

    def init_cypher(self) -> GanGen2CubeEncrypter:
        """Initialize encryption handler for cube communication."""
        raise NotImplementedError

    def send_command_handler(self, command: str) -> bytes | bool:
        """Build command bytes for cube-specific protocol."""
        raise NotImplementedError

    @staticmethod
    def read_event_code(msg: GanProtocolMessage) -> int:
        """
        Read the opcode identifying the message.

        Returns:
            The opcode of the message, as declared by the protocol.

        """
        return msg.get_bit_word(0, 8)

    @staticmethod
    def is_message_valid(msg: GanProtocolMessage) -> bool:  # noqa: ARG004
        """
        Tell whether a message is worth decoding.

        Returns:
            True when the message header matches what the protocol
            declares, False when it must be discarded silently.

        """
        return True

    async def event_handler(self, sender: BleakGATTCharacteristic,  # noqa: ARG002
                            data: bytearray) -> list[EventDict]:
        """
        Process incoming notification data from cube.

        Returns:
            List of event dictionaries parsed from cube notifications.

        """
        clock = time.perf_counter_ns()
        timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017

        events: list[EventDict] = []

        plain = self.cypher.decrypt(data)

        await self.handle_message(plain, clock, timestamp, events)

        return events

    async def handle_message(self, chunk: bytes, clock: int,
                             timestamp: datetime,
                             events: list[EventDict]) -> None:
        """
        Decode one message of a notification and collect its events.

        The handler is resolved by name so that the late binding is kept:
        a handler redefined by a subclass is the one being called, even
        when the dispatch table comes from its parent.

        Args:
            chunk: The decrypted message, from its header to the end.
            clock: Monotonic clock of the notification, in nanoseconds.
            timestamp: Wall clock of the notification.
            events: Store the decoded events are appended to.

        """
        msg = GanProtocolMessage(chunk)

        if not self.is_message_valid(msg):
            return

        event = self.read_event_code(msg)
        handler_name = self.MESSAGE_HANDLERS.get(event)

        if handler_name is None:
            logger.debug(
                'Unknown event type "0x%02X": %s', event, msg,
            )
            return

        handler: MessageHandler = getattr(self, handler_name)

        self.add_event(events, await handler(msg, clock, timestamp))

    def add_event(self, store: list[EventDict],
                  event: EventDict | Sequence[EventDict]) -> None:
        """Add event(s) to both local store and global event list."""
        if isinstance(event, Sequence):
            store.extend(event)
            self.events.extend(event)
        else:
            store.append(event)
            self.events.append(event)
