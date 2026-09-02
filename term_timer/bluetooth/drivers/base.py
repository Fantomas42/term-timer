"""Base driver class for Bluetooth cube communication."""
import logging
import time
from collections.abc import Iterator
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from typing import ClassVar

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.constants import CRC16_INIT
from term_timer.bluetooth.constants import CRC16_POLYNOMIAL
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

    # Whether a single notification can carry several chained messages.
    # V2 and V3 both declare isCycle: 1, V1 and Moyu do not.
    chained: ClassVar[bool] = False

    # Byte every chained message must start with, when the protocol
    # declares one. V2 prefixes each message with a head of 0x55, V3
    # starts directly with its bleProtoId.
    head_magic: ClassVar[int | None] = None

    # Trailing bytes of a notification that belong to the frame, not to
    # a message. V3 declares isCRC16: 1 and closes its frames with two
    # bytes of CRC.
    crc_reserve: ClassVar[int] = 0

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

    @classmethod
    def is_message_valid(cls, msg: GanProtocolMessage) -> bool:  # noqa: ARG003
        """
        Tell whether a message is worth decoding.

        Returns:
            True when the message header matches what the protocol
            declares, False when it must be discarded silently.

        """
        return True

    @staticmethod
    def compute_crc(payload: bytes) -> int:
        """
        Compute the CRC-16/CCITT-FALSE of the payload of a frame.

        Bit by bit, most significant first, without reflection nor final
        XOR, exactly as the codec of the application does.

        Returns:
            The checksum of the payload, on 16 bits.

        """
        crc = CRC16_INIT

        for byte in payload:
            crc ^= byte << 8

            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ CRC16_POLYNOMIAL) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF

        return crc

    def check_crc(self, plain: bytes) -> None:
        """
        Warn when the checksum closing the frame does not match.

        The application computes the CRC and reports it without ever
        enforcing it, and so do we: a frame is never rejected, the
        warning only tells a corrupted frame apart from a faulty
        decryption. The stored field is read little endian, the V3
        descriptor being globally isBigEndia: 0.
        """
        if not self.crc_reserve or len(plain) <= self.crc_reserve:
            return

        payload = plain[:-self.crc_reserve]
        declared = int.from_bytes(plain[-self.crc_reserve:], 'little')
        computed = self.compute_crc(payload)

        if declared != computed:
            logger.warning(
                'CRC mismatch on a %d bytes frame: '
                'it carries "0x%04X" where its %d bytes of payload '
                'give "0x%04X"',
                len(plain), declared, len(payload), computed,
            )

    def split_messages(self, plain: bytes) -> Iterator[int]:
        """
        Yield the offset, in bytes, of each message of a notification.

        A protocol declaring isCycle packs as many messages as fit into
        one notification, each one being a TLV whose dataLength byte
        closes its header. The codec walks them until the next byte is
        null, which is what this reproduces.

        Yields:
            The offset of each chained message, the first one included.

        """
        yield 0

        if not self.chained:
            return

        header = self.payload_offset // 8
        limit = len(plain) - self.crc_reserve
        offset = 0

        while offset + header <= limit:
            # The dataLength byte closes the header of the message.
            offset += header + plain[offset + header - 1]

            if offset + header > limit or plain[offset] == 0:
                return

            if self.head_magic is not None and plain[offset] != self.head_magic:
                logger.debug(
                    'Chained message at offset %d starts with "0x%02X" '
                    'instead of the head "0x%02X" of the protocol',
                    offset, plain[offset], self.head_magic,
                )
                return

            # No chained frame has ever been observed on the wire: this
            # line is the oracle telling whether one exists at all.
            logger.debug(
                'Chained message "0x%02X" found at offset %d '
                'of a %d bytes frame',
                plain[offset], offset, len(plain),
            )

            yield offset

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

        self.check_crc(plain)

        for offset in self.split_messages(plain):
            # The message is given the frame up to its end, and not up
            # to its declared dataLength : every absolute offset of the
            # handlers stays valid, and no handler can read into the
            # void when a dataLength underestimates what it reads, as
            # the Gen4 gyroscope does.
            await self.handle_message(
                plain[offset:], clock, timestamp, events,
            )

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
