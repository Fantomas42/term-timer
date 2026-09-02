"""
GAN Gen3 Driver.

References :
  - https://github.com/afedotov/gan-web-bluetooth
  - https://github.com/Fantomas42/gan-protocols
"""
import logging
import time
from datetime import datetime
from datetime import timezone
from typing import ClassVar

from bleak import BleakClient
from cubing_algs.facelets import cubies_to_facelets

from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import DisconnectEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDict
from term_timer.bluetooth.annotations import HardwareEventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.annotations import ResetEventDict
from term_timer.bluetooth.constants import DEBOUNCE
from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import MOVE_BUFFER_LIMIT
from term_timer.bluetooth.constants import MOVE_HISTORY_TIMEOUT
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.message import GanProtocolMessage

logger = logging.getLogger(__name__)


class GanGen3Driver(GanGen2Driver):
    """GAN356 i Carry 2."""

    service_uid: ClassVar[str] = GAN_GEN3_SERVICE
    state_characteristic_uid: ClassVar[str] = GAN_GEN3_STATE_CHARACTERISTIC
    command_characteristic_uid: ClassVar[str] = GAN_GEN3_COMMAND_CHARACTERISTIC
    payload_offset: ClassVar[int] = 24
    chained: ClassVar[bool] = True
    head_magic: ClassVar[int | None] = 0x55
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {
        0x01: 'handle_move',
        0x02: 'handle_facelets',
        0x06: 'handle_move_history',
        0x07: 'handle_hardware',
        0x08: 'handle_reset',
        0x10: 'handle_battery',
        0x11: 'handle_disconnect',
    }

    def __init__(self, client: BleakClient,
                 *, use_gyroscope: bool) -> None:
        """
        Initialize the GAN Gen3 driver with move tracking capabilities.

        Sets up serial number tracking, timestamp management, and a FIFO
        buffer for handling move events and detecting missed moves.

        Args:
            client: The BLE client connection to the cube.
            use_gyroscope: Whether the driver should use gyroscope data.

        """
        super().__init__(client, use_gyroscope=use_gyroscope)

        self.serial: int = -1
        self.last_serial: int = -1
        self.last_local_timestamp: datetime | None = None
        self.move_buffer: list[MoveEventDict] = []
        self.history_request_pending: bool = False
        self.history_request_clock: float = 0.0

    def send_command_handler(self, command: str) -> bytes | bool:
        """
        Build and encrypt command messages for the GAN Gen3 cube.

        Constructs protocol-specific message payloads for requesting cube
        state, hardware info, battery level, or resetting the cube, then
        encrypts them for transmission.

        Args:
            command: The command type (REQUEST_FACELETS, REQUEST_HARDWARE,
                REQUEST_BATTERY, or REQUEST_RESET).

        Returns:
            Encrypted command bytes if command is valid, False otherwise.

        """
        msg = bytearray(16)

        if command == 'REQUEST_FACELETS':
            msg[0] = 0x68
            msg[1] = 0x01
        elif command == 'REQUEST_HARDWARE':
            msg[0] = 0x68
            msg[1] = 0x04
        elif command == 'REQUEST_BATTERY':
            msg[0] = 0x68
            msg[1] = 0x07
        elif command == 'REQUEST_RESET':
            reset_sequence = [
                0x68, 0x05, 0x05, 0x39, 0x77, 0x00, 0x00, 0x01,
                0x23, 0x45, 0x67, 0x89, 0xAB, 0x00, 0x00, 0x00,
            ]
            msg = bytearray(reset_sequence)
        else:
            return False

        return self.cypher.encrypt(msg)

    async def request_move_history(self, serial: int, count: int) -> None:
        """
        Request historical move data from the cube's internal buffer.

        Constructs a move history request with alignment adjustments to work
        around firmware quirks. Ensures serial numbers are odd-aligned and
        move counts are even, and prevents overflow at the 255->0 boundary.

        Args:
            serial: The serial number to start the history request from.
            count: The number of historical moves to request.

        """
        msg = bytearray(16)

        # Move history response data is byte-aligned,
        # and moves always starting with near-ceil odd serial number,
        # regardless of requested.
        # Adjust serial and count to get odd serial aligned history window
        # with even number of moves inside.
        if serial % 2 == 0:
            serial = (serial - 1) & 0xFF
        if count % 2 == 1:
            count += 1

        # Never overflow requested history window beyond
        # the serial number cycle edge 255 -> 0.
        # Because due to iCarry2 firmware bug the moves beyond the edge
        # will be spoofed with 'D' (just zero bytes).
        count = min(count, serial + 1)

        msg[0] = 0x68
        msg[1] = 0x03
        msg[2] = serial
        msg[4] = count

        logger.debug('Sending : REQUEST_MOVE_HISTORY')

        await self.client.write_gatt_char(
            self.command_characteristic_uid,
            self.cypher.encrypt(msg),
        )

    @property
    def history_request_blocking(self) -> bool:
        """
        Check if a move history request is still awaiting its answer.

        A request stops blocking once MOVE_HISTORY_TIMEOUT has elapsed
        without the cube answering, so that a lost write or a refused
        history window can be requested again instead of holding the
        move buffer closed forever.

        Returns:
            True while a pending request is young enough to wait for.

        """
        if not self.history_request_pending:
            return False

        elapsed = time.monotonic() - self.history_request_clock

        return elapsed < MOVE_HISTORY_TIMEOUT

    async def open_history_request(self, serial: int, count: int) -> None:
        """
        Send a move history request and mark it as pending.

        Logs a warning when the previous request is being retried, which
        means the cube never answered it.

        Args:
            serial: The serial number to start the history request from.
            count: The number of historical moves to request.

        """
        if self.history_request_pending:
            logger.warning(
                'Move history request unanswered after %ss, '
                'retrying from serial %s for %s moves',
                MOVE_HISTORY_TIMEOUT, serial, count,
            )

        self.history_request_pending = True
        self.history_request_clock = time.monotonic()

        await self.request_move_history(serial, count)

    def close_history_request(self) -> None:
        """Mark the pending move history request as answered."""
        self.history_request_pending = False

    async def evict_move_buffer(self) -> list[EventDict]:
        """
        Process and emit move events from the buffer in sequence order.

        Removes move events from the buffer when they can be delivered in the
        correct serial order. If a gap is detected, requests missing history.
        Disconnects if the buffer grows too large (indicating sync issues),
        emitting a disconnect event so the application is told about it.

        Returns:
            List of events that were successfully evicted from the buffer
            and are ready to be emitted.

        """
        evicted_events: list[EventDict] = []

        while len(self.move_buffer) > 0:
            buffer_head = self.move_buffer[0]
            diff = 1 if self.last_serial == -1 else (
                buffer_head['serial'] - self.last_serial) & 0xFF
            if diff > 1:
                if self.history_request_blocking:
                    logger.debug(
                        'Eviction on hold, waiting for %s missed moves '
                        'before serial %s',
                        diff - 1, buffer_head['serial'],
                    )
                else:
                    await self.open_history_request(
                        buffer_head['serial'], diff,
                    )
                break

            evicted_events.append(self.move_buffer.pop(0))
            self.last_serial = buffer_head['serial']

        if len(self.move_buffer) > MOVE_BUFFER_LIMIT:
            logger.warning(
                'Move buffer overflowed with %s moves stuck behind '
                'an unrecovered gap, disconnecting the cube',
                len(self.move_buffer),
            )

            overflow_payload: DisconnectEventDict = {
                'event': 'disconnect',
                'clock': time.perf_counter_ns(),
                'timestamp': datetime.now(tz=timezone.utc),  # noqa: UP017
            }
            evicted_events.append(overflow_payload)

            await self.client.disconnect()

        return evicted_events

    @staticmethod
    def is_serial_in_range(start: int, end: int, serial: int, *,
                           closed_start: bool = False,
                           closed_end: bool = False) -> bool:
        """
        Check if a serial number falls within a range with wraparound.

        Handles modular arithmetic for serial numbers that wrap around at 255,
        allowing for both open and closed interval boundaries.

        Args:
            start: The range start serial number.
            end: The range end serial number.
            serial: The serial number to check.
            closed_start: Whether the start boundary is inclusive.
            closed_end: Whether the end boundary is inclusive.

        Returns:
            True if the serial number is within the specified range.

        """
        return (
            ((end - start) & 0xFF) >= ((serial - start) & 0xFF)
            and (closed_start or ((start - serial) & 0xFF) > 0)
            and (closed_end or ((end - serial) & 0xFF) > 0)
        )

    def inject_missed_move_to_buffer(self, move: MoveEventDict) -> None:
        """
        Insert a recovered historical move into the buffer at the correct
        position.

        Validates that the move belongs in the current sequence and isn't a
        duplicate before inserting it into the buffer for ordered delivery.

        Args:
            move: The move event to inject into the buffer.

        """
        if len(self.move_buffer) > 0:
            buffer_head = self.move_buffer[0]

            if any(e['event'] in {'move', 'move_history'}
                   and e['serial'] == move['serial']
                   for e in self.move_buffer):
                return

            if not self.is_serial_in_range(
                    self.last_serial,
                    buffer_head['serial'],
                    move['serial'],
            ):
                return

            if move['serial'] == ((buffer_head['serial'] - 1) & 0xFF):
                self.move_buffer.insert(0, move)
        elif self.is_serial_in_range(
                self.last_serial,
                self.serial,
                move['serial'],
                closed_start=False,
                closed_end=True,
        ):
            self.move_buffer.insert(0, move)

    async def check_if_move_missed(self) -> None:
        """
        Detect gaps in the move sequence and request missing history.

        Compares the current serial with the last processed serial to detect
        missed moves, then requests the appropriate history window to recover
        them.

        """
        diff = (self.serial - self.last_serial) & 0xFF

        if diff > 0 and self.serial != 0 and not self.history_request_blocking:
            buffer_head = self.move_buffer[0] if self.move_buffer else None
            start_serial = buffer_head['serial'] if buffer_head else (
                self.serial + 1
            ) & 0xFF
            await self.open_history_request(start_serial, diff + 1)

    @staticmethod
    def read_event_code(msg: GanProtocolMessage) -> int:
        """
        Read the opcode of a V2 message.

        V2 prefixes its bleProtoId with a head byte, and follows it with
        a dataLength byte.

        Returns:
            The opcode of the message.

        """
        return msg.get_bit_word(8, 8)

    @classmethod
    def is_message_valid(cls, msg: GanProtocolMessage) -> bool:
        """
        Check the head byte and the length declared by a V2 message.

        Returns:
            True when the message starts with the head magic of V2 and
            declares a payload.

        """
        return (
            msg.get_bit_word(0, 8) == cls.head_magic
            and msg.get_bit_word(16, 8) > 0
        )

    async def handle_move(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode a move message and evict what the buffer can deliver.

        The move is pushed into the FIFO buffer rather than emitted, so
        that a gap in the serial numbers can still be filled by a move
        history request before the moves are delivered in order.

        Returns:
            The moves the buffer could deliver in order, if any.

        """
        if self.last_serial == -1:  # Block moves until facelets received
            return []

        self.last_local_timestamp = timestamp
        serial = msg.get_bit_word(56, 16, little_endian=True)
        cube_timestamp = msg.get_bit_word(24, 32, little_endian=True)

        direction = msg.get_bit_word(72, 2)
        face = [2, 32, 8, 1, 16, 4].index(msg.get_bit_word(74, 6))
        move = 'URFDLB'[face] + " '"[direction]

        # Put move event into FIFO buffer
        if face >= 0:
            move_event: MoveEventDict = {
                'event': 'move',
                'clock': clock,
                'timestamp': timestamp,
                'serial': serial,
                'local_timestamp': timestamp,
                'cube_timestamp': cube_timestamp,
                'face': face,
                'direction': direction,
                'move': move.strip(),
            }
            self.move_buffer.append(move_event)

        return await self.evict_move_buffer()

    async def handle_facelets(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the cube state and check for missed moves.

        The facelets message is sent periodically by the cube, which
        makes it the place where a gap in the move serials is noticed.

        Returns:
            The facelets event of the message.

        """
        serial = msg.get_bit_word(24, 16, little_endian=True)
        self.serial = serial

        # Also check and recovery missed moves
        # using periodic facelets event sent by cube
        if self.last_serial != -1:
            # Debounce the facelet event if there are active cube moves
            if (
                    self.last_local_timestamp is not None
                    and (
                        timestamp - self.last_local_timestamp
                    ).total_seconds() > DEBOUNCE
            ):
                await self.check_if_move_missed()
        else:
            self.last_serial = serial

        # Corner/Edge Permutation/Orientation
        cp = []
        co = []
        ep = []
        eo = []
        so = [0, 1, 2, 3, 4, 5]
        # Corners
        for i in range(7):
            cp.append(msg.get_bit_word(40 + i * 3, 3))
            co.append(msg.get_bit_word(61 + i * 2, 2))
        cp.append(28 - sum(cp))
        co.append((3 - (sum(co) % 3)) % 3)
        # Edges
        for i in range(11):
            ep.append(msg.get_bit_word(77 + i * 4, 4))
            eo.append(msg.get_bit_word(121 + i, 1))
        ep.append(66 - sum(ep))
        eo.append((2 - (sum(eo) % 2)) % 2)

        facelets_payload: FaceletsEventDict = {
            'event': 'facelets',
            'clock': clock,
            'timestamp': timestamp,
            'serial': serial,
            'facelets': cubies_to_facelets(cp, co, ep, eo, so),
            'state': {
                'CP': cp,
                'CO': co,
                'EP': ep,
                'EO': eo,
            },
        }

        return [facelets_payload]

    async def handle_move_history(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the moves answering a move history request.

        Returns:
            The moves the buffer could deliver in order once the
            recovered ones have been injected, if any.

        """
        self.close_history_request()
        data_size = msg.get_bit_word(16, 8)
        start_serial = msg.get_bit_word(24, 8)
        count = (data_size - 1) * 2

        for i in range(count):
            direction = msg.get_bit_word(35 + 4 * i, 1)
            face = [1, 5, 3, 0, 4, 2].index(msg.get_bit_word(32 + 4 * i, 3))

            if face >= 0:
                move = 'URFDLB'[face] + " '"[direction]

                history_move: MoveEventDict = {
                    'event': 'move_history',
                    'clock': clock,
                    'timestamp': timestamp,
                    'serial': (start_serial - i) & 0xFF,
                    # Missed and recovered events
                    # has no meaningful local timestamps
                    'local_timestamp': None,
                    # Cube hardware timestamp for missed move
                    # you should interpolate using
                    # cubeTimestampLinearFit
                    'cube_timestamp': None,
                    'face': face,
                    'direction': direction,
                    'move': move.strip(),
                }
                self.inject_missed_move_to_buffer(history_move)

        return await self.evict_move_buffer()

    async def handle_hardware(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the hardware identity of the cube.

        Returns:
            The hardware event of the message.

        """
        restart_reason = msg.get_bit_word(24, 8)

        hardware_name = ''
        for i in range(5):
            hardware_name += chr(msg.get_bit_word(i * 8 + 32, 8))

        sw_major = msg.get_bit_word(72, 4)
        sw_minor = msg.get_bit_word(76, 4)
        hw_major = msg.get_bit_word(80, 4)
        hw_minor = msg.get_bit_word(84, 4)

        _build_time = msg.get_bit_word(88, 32, little_endian=True)

        hardware_payload: HardwareEventDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'restart_no_power': restart_reason,
            'hardware_name': hardware_name,
            'hardware_version': f'{ hw_major }.{ hw_minor }',
            'software_version': f'{ sw_major }.{ sw_minor }',
            'gyroscope_enabled': False,
            'gyroscope_ready': False,
            'gyroscope_supported': False,
        }

        return [hardware_payload]

    async def handle_reset(  # noqa: PLR6301
            self, msg: GanProtocolMessage,  # noqa: ARG002
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Acknowledge that the cube state has been reset.

        Returns:
            The reset event of the message.

        """
        reset_payload: ResetEventDict = {
            'event': 'reset',
            'clock': clock,
            'timestamp': timestamp,
        }

        return [reset_payload]

    async def handle_battery(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the battery level of the cube.

        Returns:
            The battery event of the message.

        """
        battery_level = msg.get_bit_word(24, 8)

        battery_payload: BatteryEventDict = {
            'event': 'battery',
            'clock': clock,
            'timestamp': timestamp,
            'charging_state': 0,
            'level': min(battery_level, 100),
        }

        return [battery_payload]
