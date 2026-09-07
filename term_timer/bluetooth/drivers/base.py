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
from cubing_algs.constants import FACES

from term_timer.bluetooth.advertisement import decode_advertised_mac
from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import DisconnectEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.constants import CLOCK_REGISTER_SATURATED
from term_timer.bluetooth.constants import CRC16_INIT
from term_timer.bluetooth.constants import CRC16_POLYNOMIAL
from term_timer.bluetooth.constants import DIRECTIONS
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.message import GanProtocolMessage
from term_timer.bluetooth.salt import get_salt

if TYPE_CHECKING:
    from bleak.backends.scanner import AdvertisementData

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
    # Some protocols pack only an opcode there, others an opcode and a
    # length byte. The byte opening a notification is not counted here:
    # it belongs to the notification, not the message, and is stripped
    # once by strip_head().
    payload_offset: ClassVar[int] = 8

    # Whether a single notification can carry several chained messages.
    chained: ClassVar[bool] = False

    # Whether REQUEST_RESET's outcome is confirmed by the cube. Some
    # protocols answer with a dedicated `reset` event carrying a
    # result; others only echo the state as an unsolicited facelets
    # frame, with no bit left for a result — nothing is inferred for
    # those.
    confirms_reset: ClassVar[bool] = False

    # Byte a notification starts with, when the protocol declares one.
    # It belongs to the *notification* and not to each message: a
    # chained message repeats only its own header, not this byte. It is
    # therefore removed once per notification rather than counted in
    # payload_offset, which lets protocols sharing a message header
    # share it regardless of how they open their frames.
    head_magic: ClassVar[int | None] = None

    # Bytes of checksum closing the last message of a notification,
    # rather than the frame. A protocol whose chained messages do not
    # repeat the head has nothing else saying where the chain ends :
    # the checksum is what terminates it, and a protocol declaring a
    # head_magic without one would read its own checksum as a message.
    crc_terminator: ClassVar[int] = 0

    # Trailing bytes of a notification that belong to the frame, not to
    # a message — a protocol closing its frames with a checksum.
    crc_reserve: ClassVar[int] = 0

    # Bits between the header of a battery message and the level it
    # carries. A protocol may spend them on a charging state or on an
    # index instead; `charging_state_width` tells the two apart.
    battery_level_offset: ClassVar[int] = 0

    # Width, in bits, of that charging state. Left at zero, the level
    # is published with a charging state of 0, the default for a
    # protocol that declares none.
    charging_state_width: ClassVar[int] = 0

    # Opcode -> name of the method decoding it. Redefined *entirely* by
    # each protocol: the opcode spaces do not overlap, and the same
    # opcode can mean different things from one protocol to the next.
    # Only the *methods* are inherited.
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {}

    def __init__(
            self,
            client: BleakClient,
            *,
            use_gyroscope: bool,
            advertisement: 'AdvertisementData | None' = None,
    ) -> None:
        """
        Initialize driver with BleakClient and encryption.

        Args:
            client: The BLE client connection to the cube.
            use_gyroscope: Whether the driver should use gyroscope data.
            advertisement: The advertisement the scan found before
                connecting, or None when the connection skipped it (a
                configured cube dialed directly by address). Its MAC
                is preferred for the salt, see `resolve_salt()`.

        """
        self.client: BleakClient = client
        self.use_gyroscope = use_gyroscope
        self.advertisement = advertisement

        self.events: list[EventDict] = []

        # The last serial the cube sent, the clock it times its moves
        # on, and the wall clock of the last of them. The four
        # protocols number their moves on a byte and time them with a
        # register the driver accumulates, so the three live here
        # rather than being copied into each driver. What does *not*
        # live here is the last serial a driver has *published* : only
        # the GAN generations tell the two apart, and only they buffer
        # moves long enough for the distinction to mean anything.
        self.serial: int = -1
        self.cube_timestamp: float = 0.0
        self.last_move_timestamp: datetime | None = None

        self.cypher: GanGen2CubeEncrypter = self.init_cypher()
        self.post_init()

    def post_init(self) -> None:
        """Set up a driver's own state, run once at the end of __init__."""

    def resolve_salt(self) -> bytearray:
        """
        Resolve the salt encrypting commands sent to the cube.

        The MAC the cube itself advertised is preferred: it does not
        depend on however a given platform's Bluetooth backend renders
        a device address, unlike `client.address` — a real MAC on
        every backend confirmed so far, but a CoreBluetooth UUID on
        macOS, never usable as a salt. `client.address` is the
        fallback, used when the connection skipped the scan entirely
        (a cube dialed directly by a configured address). `get_salt()`
        raises `ValueError` when neither is usable, left to propagate.

        Returns:
            The salt bytes for the cube's session encryption key.

        """
        mac_address = (
            decode_advertised_mac(self.advertisement.manufacturer_data)
            if self.advertisement is not None else None
        )

        if mac_address is not None:
            return get_salt(mac_address)

        return get_salt(self.client.address)

    @property
    def gyroscope_controllable(self) -> bool:
        """
        Tell whether the cube accepts a gyroscope enable/disable command.

        A property rather than a class attribute because the answer is
        not always a property of the protocol : the Gen4 carries the
        command but only one of its models is known to honour it, and
        the name it answers is the only thing telling them apart.

        Returns:
            False, a protocol carrying no such command being the
            default.

        """
        return False

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
    def format_move(face: int, direction: int) -> str | None:
        """
        Build the notation of a move out of its two decoded fields.

        Every field a driver reads is a slice of bits wider than the
        domain it names, so a face read on 4 or 6 bits and a direction
        read on 2 both carry values no move answers to. Indexing a
        string with one of them raises, which is why they are checked
        here instead of at each of the five call sites.

        Returns:
            The notation of the move, or None when one of the two
            fields falls outside of its domain.

        """
        if not 0 <= face < len(FACES):
            return None

        if not 0 <= direction < len(DIRECTIONS):
            return None

        return (FACES[face] + DIRECTIONS[direction]).strip()

    def advance_cube_timestamp(self, elapsed: int,
                               timestamp: datetime) -> float:
        """
        Accumulate on the clock of the cube the time a move took.

        The register is read on sixteen bits and counts in
        milliseconds, confirmed by the wider time and duration fields
        other protocols declare for the same purpose. **Two** of its
        readings are not durations: a null one is the register having
        overflowed, and `0xFFFF` is the same register saturated, the
        cube having been still for more than 65,5 seconds. The local
        clock stands in for both — converted to milliseconds too,
        which is the whole reason this is not an addition written at
        each call site.

        Added as it comes, a saturated reading would push the clock of
        the cube 65,5 seconds forward on the first move of a session —
        and with no earlier move to date, there is nothing to stand in
        for it either: the clock then stays where it is, exactly as it
        does on an overflow read before the first move.

        The clock is advanced before a move is named, and never after:
        it moved on whether or not the fields beside it could be
        decoded, and skipping it would shift every move coming after.

        Args:
            elapsed: The value of the register of the cube.
            timestamp: The wall clock of the notification.

        Returns:
            The clock of the cube, the move now added to it.

        """
        if elapsed and elapsed != CLOCK_REGISTER_SATURATED:
            self.cube_timestamp += elapsed
        elif self.last_move_timestamp is not None:
            self.cube_timestamp += (
                timestamp - self.last_move_timestamp
            ).total_seconds() * 1000

        return self.cube_timestamp

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
        decryption. The stored field is read little endian.
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

    def strip_head(self, plain: bytes) -> bytes | None:
        """
        Remove the head opening a notification, when there is one.

        The head belongs to the *notification* and not to each of its
        messages: a chained message repeats only its own header, not
        this byte. Taking it off once here is what lets protocols
        sharing a message header also share the handlers reading
        behind it.

        The byte the protocol declares is checked on the way, since
        this is the only place it is still visible.

        Args:
            plain: The decrypted notification.

        Returns:
            The notification without its head, or None when it does not
            open with the head the protocol declares.

        """
        if self.head_magic is None:
            return plain

        if not plain or plain[0] != self.head_magic:
            logger.debug(
                'Notification opens with "0x%02X" where the protocol '
                'declares a head of "0x%02X": %s',
                plain[0] if plain else 0, self.head_magic, plain.hex(),
            )
            return None

        return plain[1:]

    def chain_closed(self, plain: bytes, offset: int) -> bool:
        """
        Tell whether the checksum of the notification closes here.

        A chained message repeating no head, nothing but the checksum
        says that the message just read was the last one : the two
        bytes that follow are either the CRC of everything before them,
        or the header of one more message. Two bytes matching by
        chance is a one in sixty-five thousand affair, and the walk is
        bounded by the frame either way.

        Args:
            plain: The notification, head already stripped.
            offset: Where the next message would start.

        Returns:
            True when the bytes at that offset are the closing CRC.

        """
        if not self.crc_terminator:
            return False

        stop = offset + self.crc_terminator

        if stop > len(plain):
            return False

        declared = int.from_bytes(plain[offset:stop], 'little')

        return self.compute_crc(plain[:offset]) == declared

    def split_messages(self, plain: bytes) -> Iterator[bytes]:
        """
        Yield each message of a notification whose head is gone.

        A chaining protocol packs as many messages as fit into one
        notification, each one being a TLV whose length byte closes
        its header. Every message of the chain has the same header,
        the head having been taken off the notification by
        `strip_head` beforehand.

        Args:
            plain: The notification, head already stripped.

        Yields:
            Each message, from its header to the end of the frame.

        """
        yield plain

        if not self.chained:
            return

        # A head says where a notification starts; with no terminator,
        # nothing says where its chain ends, and reading on would
        # decode the checksum of the frame as one more message.
        if self.head_magic is not None and not self.crc_terminator:
            logger.debug(
                'Protocol declares a head "0x%02X" and no terminator: '
                'its notifications cannot be walked',
                self.head_magic,
            )
            return

        header = self.payload_offset // 8
        limit = len(plain) - self.crc_reserve
        offset = 0

        while offset + header <= limit:
            # The dataLength byte closes the header of the message.
            offset += header + plain[offset + header - 1]

            # The checksum is tested first, and on purpose: it is the
            # terminator of the chain, where the null byte is only a
            # heuristic. A CRC whose low byte happens to be null
            # answers both tests, and only one of them is
            # authoritative.
            if self.chain_closed(plain, offset):
                return

            if offset + header > limit or plain[offset] == 0:
                return

            logger.debug(
                'Chained message "0x%02X" found at offset %d '
                'of a %d bytes frame',
                plain[offset], offset, len(plain),
            )

            yield plain[offset:]

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

        payload = self.strip_head(plain)

        if payload is None:
            return events

        for chunk in self.split_messages(payload):
            # The message is given the frame up to its end, and not up
            # to its declared length: every absolute offset of the
            # handlers stays valid, and no handler can read into the
            # void when a protocol's declared length underestimates
            # what it actually reads.
            await self.handle_message(chunk, clock, timestamp, events)

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

    async def handle_battery(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the battery level of the cube.

        The four protocols publish the same event out of the same
        byte, and only where that byte sits changes : `payload_offset`
        says where the header ends, `battery_level_offset` what the
        generation spends before its level, and `charging_state_width`
        whether those bits are a charging state worth publishing.

        Returns:
            The battery event of the message.

        """
        charging_state = 0

        if self.charging_state_width:
            charging_state = msg.get_bit_word(
                self.payload_offset, self.charging_state_width,
            )

        battery_level = msg.get_bit_word(
            self.payload_offset + self.battery_level_offset, 8,
        )

        battery_payload: BatteryEventDict = {
            'event': 'battery',
            'clock': clock,
            'timestamp': timestamp,
            'charging_state': charging_state,
            'level': min(battery_level, 100),
        }

        return [battery_payload]

    async def handle_disconnect(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Close the link on request of the cube.

        The opcode is absent from some protocol descriptors, and where
        it is declared it can mean something other than a
        disconnection. The first byte of the payload is journaled
        before the link is cut: it is the only thing that will ever
        tell whether cutting is the right reading, and it is armed on
        every protocol so that whichever cube asks first says it.

        Returns:
            The disconnect event telling the application about it.

        """
        logger.warning(
            'Cube requested a disconnection, payload starts with "0x%02X"',
            msg.get_bit_word(self.payload_offset, 8),
        )

        disconnect_payload: DisconnectEventDict = {
            'event': 'disconnect',
            'clock': clock,
            'timestamp': timestamp,
        }

        await self.client.disconnect()

        return [disconnect_payload]

    def add_event(self, store: list[EventDict],
                  event: EventDict | Sequence[EventDict]) -> None:
        """Add event(s) to both local store and global event list."""
        if isinstance(event, Sequence):
            store.extend(event)
            self.events.extend(event)
        else:
            store.append(event)
            self.events.append(event)
