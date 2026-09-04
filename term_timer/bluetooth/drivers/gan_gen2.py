"""
GAN Gen2 Driver.

References :
  - https://github.com/afedotov/gan-web-bluetooth
  - https://github.com/Fantomas42/gan-protocols/
"""
import logging
import time
from datetime import datetime
from datetime import timezone
from typing import ClassVar

from bleak import BleakClient
from cubing_algs.facelets import cubies_to_facelets

from term_timer.bluetooth.annotations import DisconnectEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDict
from term_timer.bluetooth.annotations import GyroEventDict
from term_timer.bluetooth.annotations import HardwareEventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.constants import GAN_ENCRYPTION_KEY
from term_timer.bluetooth.constants import GAN_GEN2_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN2_SERVICE
from term_timer.bluetooth.constants import GAN_GEN2_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import GEN2_FACE_ANGLES_CAPACITY
from term_timer.bluetooth.constants import GEN2_MOVE_CAPACITY
from term_timer.bluetooth.constants import GEN2_MOVE_HISTORY_CAPACITY
from term_timer.bluetooth.constants import MOVE_BUFFER_LIMIT
from term_timer.bluetooth.constants import MOVE_HISTORY_TIMEOUT
from term_timer.bluetooth.constants import MOYU_AI_ENCRYPTION_KEY
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.message import GanProtocolMessage
from term_timer.bluetooth.salt import get_salt

logger = logging.getLogger(__name__)


class GanGen2Driver(Driver):
    """
    GAN12 ui.
    GAN12 ui FreePlay.
    GAN mini ui FreePlay.
    GAN i carry S.
    GAN356 i, i2, i3.
    GAN356 i play, i play 2.
    MG3 AI, XES.
    MoYu AI 2023.
    """

    service_uid: ClassVar[str] = GAN_GEN2_SERVICE
    state_characteristic_uid: ClassVar[str] = GAN_GEN2_STATE_CHARACTERISTIC
    command_characteristic_uid: ClassVar[str] = GAN_GEN2_COMMAND_CHARACTERISTIC
    encrypter: ClassVar[type[GanGen2CubeEncrypter]] = GanGen2CubeEncrypter
    payload_offset: ClassVar[int] = 4
    # V1 is the only GAN protocol declaring a real charging state, on
    # the four bits its header leaves before the battery level.
    battery_level_offset: ClassVar[int] = 4
    charging_state_width: ClassVar[int] = 4
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {
        0x01: 'handle_gyroscope',
        0x02: 'handle_move',
        0x03: 'handle_face_angles',
        0x04: 'handle_facelets',
        0x05: 'handle_hardware',
        0x07: 'handle_move_history',
        0x09: 'handle_battery',
        0x0D: 'handle_disconnect',
        0x0E: 'handle_account_binding',
    }

    def __init__(self, client: BleakClient,
                 *, use_gyroscope: bool) -> None:
        """
        Initialize GAN Gen2 driver with BLE client connection.

        The serial the cube last sent and the clock of its moves come
        from `Driver`, which holds them for the four protocols. What
        is added here is the serial last *published*, which only a
        driver buffering its moves needs, and the FIFO buffer telling
        the two apart.

        Args:
            client: The BLE client connection to the cube.
            use_gyroscope: Whether the driver should use gyroscope data.

        """
        super().__init__(client, use_gyroscope=use_gyroscope)

        self.last_serial: int = -1
        self.move_buffer: list[MoveEventDict] = []
        self.history_request_pending: bool = False
        self.history_request_clock: float = 0.0

    def init_cypher(self) -> GanGen2CubeEncrypter:
        """
        Initialize encryption handler for cube communication.

        Returns:
            GanGen2CubeEncrypter instance with appropriate encryption keys.

        """
        if self.client.name and self.client.name.startswith('AiCube'):
            return self.encrypter(
                MOYU_AI_ENCRYPTION_KEY['key'],
                MOYU_AI_ENCRYPTION_KEY['iv'],
                get_salt(self.client.address),
            )
        return self.encrypter(
            GAN_ENCRYPTION_KEY['key'],
            GAN_ENCRYPTION_KEY['iv'],
            get_salt(self.client.address),
        )

    def send_command_handler(self, command: str) -> bytes | bool:
        """
        Build and encrypt command messages for GAN Gen2 cube.

        Returns:
            Encrypted command bytes or False if command is invalid.

        """
        msg = bytearray(20)

        if command == 'REQUEST_FACELETS':
            msg[0] = 0x04
        elif command == 'REQUEST_HARDWARE':
            msg[0] = 0x05
        elif command == 'REQUEST_BATTERY':
            msg[0] = 0x09
        elif command == 'REQUEST_RESET':
            reset_sequence = [
                0x0A, 0x05, 0x39, 0x77, 0x00, 0x00, 0x01, 0x23, 0x45, 0x67,
                0x89, 0xAB, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ]
            msg = bytearray(reset_sequence)
        else:
            return False

        return self.cypher.encrypt(msg)

    async def request_move_history(self, serial: int, count: int) -> None:
        """
        Request historical move data from the cube's internal buffer.

        V1 packs its history the same five bits per move as a live
        message, so no window has to be aligned on a byte the way V2 and
        V3 need: only the capacity of the answer caps the request.

        Args:
            serial: The serial number to start the history request from.
            count: The number of historical moves to request.

        """
        msg = bytearray(20)

        count = min(count, GEN2_MOVE_HISTORY_CAPACITY)

        msg[0] = 0x07
        msg[1] = serial
        msg[2] = count

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
        Read the opcode of a V1 message.

        V1 declares its bleProtoId on the first 4 bits, and no
        dataLength at all.

        Returns:
            The opcode of the message.

        """
        return msg.get_bit_word(0, 4)

    async def handle_gyroscope(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the two orientation samples of a gyroscope message.

        V1 is the only protocol version declaring two samples in a
        single message, each with its own quaternion and velocity.

        Returns:
            The two gyroscope events, oldest first, or nothing when the
            gyroscope is not used.

        """
        if not self.use_gyroscope:
            return []

        # Orientation Quaternion
        qw = msg.get_bit_word(4, 16)
        qx = msg.get_bit_word(20, 16)
        qy = msg.get_bit_word(36, 16)
        qz = msg.get_bit_word(52, 16)

        # Angular Velocity
        vx = msg.get_bit_word(68, 4)
        vy = msg.get_bit_word(72, 4)
        vz = msg.get_bit_word(76, 4)

        gyro_payload: GyroEventDict = {
            'event': 'gyro',
            'clock': clock,
            'timestamp': timestamp,
            'quaternion': {
                'x': (1 - (qx >> 15) * 2) * (qx & 0x7FFF) / 0x7FFF,
                'y': (1 - (qy >> 15) * 2) * (qy & 0x7FFF) / 0x7FFF,
                'z': (1 - (qz >> 15) * 2) * (qz & 0x7FFF) / 0x7FFF,
                'w': (1 - (qw >> 15) * 2) * (qw & 0x7FFF) / 0x7FFF,
            },
            'velocity': {
                'x': (1 - (vx >> 3) * 2) * (vx & 0x7),
                'y': (1 - (vy >> 3) * 2) * (vy & 0x7),
                'z': (1 - (vz >> 3) * 2) * (vz & 0x7),
            },
        }

        # Second Orientation Quaternion
        qw = msg.get_bit_word(4 + 76, 16)
        qx = msg.get_bit_word(20 + 76, 16)
        qy = msg.get_bit_word(36 + 76, 16)
        qz = msg.get_bit_word(52 + 76, 16)

        # Second Angular Velocity
        vx = msg.get_bit_word(68 + 76, 4)
        vy = msg.get_bit_word(72 + 76, 4)
        vz = msg.get_bit_word(76 + 76, 4)

        second_gyro_payload: GyroEventDict = {
            'event': 'gyro',
            'clock': clock,
            'timestamp': timestamp,
            'quaternion': {
                'x': (1 - (qx >> 15) * 2) * (qx & 0x7FFF) / 0x7FFF,
                'y': (1 - (qy >> 15) * 2) * (qy & 0x7FFF) / 0x7FFF,
                'z': (1 - (qz >> 15) * 2) * (qz & 0x7FFF) / 0x7FFF,
                'w': (1 - (qw >> 15) * 2) * (qw & 0x7FFF) / 0x7FFF,
            },
            'velocity': {
                'x': (1 - (vx >> 3) * 2) * (vx & 0x7),
                'y': (1 - (vy >> 3) * 2) * (vy & 0x7),
                'z': (1 - (vz >> 3) * 2) * (vz & 0x7),
            },
        }

        return [gyro_payload, second_gyro_payload]

    async def handle_move(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the moves carried by a move message.

        A single message carries the last move plus the six previous
        ones, which is the capacity of the protocol : beyond seven moves
        announced between two notifications, the oldest ones are only
        recoverable through a history request, which the eviction of the
        buffer opens on its own.

        The moves are pushed into the FIFO buffer rather than emitted,
        so that such a gap can still be filled before they are delivered
        in order. With the one move of a nominal message, the eviction
        is immediate and the latency unchanged.

        Returns:
            The moves the buffer could deliver in order, or nothing
            while the facelets have not been received yet.

        """
        if self.last_serial == -1:  # Block moves until facelets received
            return []

        serial = msg.get_bit_word(4, 8)
        announced = (serial - self.serial) & 0xFF
        diff = min(announced, GEN2_MOVE_CAPACITY)

        if announced > GEN2_MOVE_CAPACITY:
            logger.warning(
                'Move message "0x02" announces %d moves since serial %d, '
                '%d of them beyond the capacity of the message',
                announced, self.serial, announced - GEN2_MOVE_CAPACITY,
            )

        self.serial = serial

        if diff <= 0:
            return []

        for i in range(diff - 1, -1, -1):
            face = msg.get_bit_word(12 + 5 * i, 4)
            direction = msg.get_bit_word(16 + 5 * i, 1)
            elapsed_raw = msg.get_bit_word(47 + 16 * i, 16)

            cube_timestamp = self.advance_cube_timestamp(
                elapsed_raw, timestamp,
            )

            move = self.format_move(face, direction)

            if move is None:
                logger.debug(
                    'Move message "0x02" carries an out of domain move '
                    'at index %d: face "%d", direction "%d"',
                    i, face, direction,
                )
                continue

            move_payload: MoveEventDict = {
                'event': 'move',
                'clock': clock,
                'timestamp': timestamp,
                'serial': (serial - i) & 0xFF,
                # Missed and recovered events
                # has no meaningful local timestamps
                'local_timestamp': timestamp if i == 0 else None,
                'cube_timestamp': cube_timestamp,
                'face': face,
                'direction': direction,
                'move': move,
            }
            self.move_buffer.append(move_payload)

        self.last_move_timestamp = timestamp

        return await self.evict_move_buffer()

    async def handle_face_angles(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the raw face angles streamed by the cube.

        Returns:
            Nothing, the angles are journaled only.

        """
        step = msg.get_bit_word(4, 3)
        count = msg.get_bit_word(7, 3)

        # The count is read on 3 bits and can announce more records
        # than a 20 bytes notification carries.
        kept = min(count, GEN2_FACE_ANGLES_CAPACITY)

        records = []
        for i in range(kept):
            offset = 10 + 25 * i
            records.append((
                msg.get_bit_word(offset, 1),          # pos
                msg.get_bit_word(offset + 1, 3),      # face1
                msg.get_bit_word(offset + 4, 9),      # angle1
                msg.get_bit_word(offset + 13, 3),     # face2
                msg.get_bit_word(offset + 16, 9),     # angle2
            ))

        logger.debug(
            'Face angles - step:%s, count:%s, '
            'records (pos, face1, angle1, face2, angle2):%s',
            step, count, records,
        )

        if count > GEN2_FACE_ANGLES_CAPACITY:
            logger.debug(
                'Face angles message announces %d records, '
                'only %d fit in the notification',
                count, GEN2_FACE_ANGLES_CAPACITY,
            )

        return []

    async def handle_facelets(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the cube state carried by a facelets message.

        Returns:
            The facelets event of the message.

        """
        serial = msg.get_bit_word(4, 8)

        # V1 answers a facelets request, and pushes one unsolicited
        # answer to a reset : the protocol has no reset message of its
        # own, and the cube acknowledges the command with the state it
        # was just told to hold. Measured on a GAN12 ui FreePlay the
        # 2026-09-02, a lone frame 306 ms after the write. Either way
        # this is where the two counters start, and not a place where
        # a gap in the move serials could be noticed.
        if self.last_serial == -1:
            self.serial = serial
            self.last_serial = serial

        # Corner/Edge Permutation/Orientation
        cp = []
        co = []
        ep = []
        eo = []
        so = [0, 1, 2, 3, 4, 5]
        # Corners
        for i in range(7):
            cp.append(msg.get_bit_word(12 + i * 3, 3))
            co.append(msg.get_bit_word(33 + i * 2, 2))
        cp.append(28 - sum(cp))
        co.append((3 - (sum(co) % 3)) % 3)
        # Edges
        for i in range(11):
            ep.append(msg.get_bit_word(47 + i * 4, 4))
            eo.append(msg.get_bit_word(91 + i, 1))
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

    async def handle_hardware(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the hardware identity of the cube.

        V1 is the only GAN protocol carrying two versions and two
        gyroscope capability bits.

        Returns:
            The hardware event of the message.

        """
        restart_no_power = msg.get_bit_word(4, 4)

        hw_major = msg.get_bit_word(8, 8)
        hw_minor = msg.get_bit_word(16, 8)

        sw_major = msg.get_bit_word(24, 8)
        sw_minor = msg.get_bit_word(32, 8)

        hardware_name = ''
        for i in range(8):
            hardware_name += chr(msg.get_bit_word(i * 8 + 40, 8))

        gyro_enabled = msg.get_bit_word(104, 1)
        gyro_ready = msg.get_bit_word(105, 1)

        hardware_payload: HardwareEventDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'restart_no_power': restart_no_power,
            'hardware_name': hardware_name,
            'hardware_version': f'{ hw_major }.{ hw_minor }',
            'software_version': f'{ sw_major }.{ sw_minor }',
            'gyroscope_enabled': bool(gyro_enabled),
            'gyroscope_ready': bool(gyro_ready),
            'gyroscope_supported': (
                bool(gyro_enabled)
                and bool(gyro_ready)
            ),
        }

        return [hardware_payload]

    async def handle_move_history(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the moves answering a move history request.

        V1 answers with the same five bits per move as a live message,
        the newest first, behind the serial the window starts at. The
        durations are answered by another message, never requested : a
        recovered move carries no cube timestamp, which is what V2 and
        V3 already do.

        Returns:
            The moves the buffer could deliver in order once the
            recovered ones have been injected, if any.

        """
        self.close_history_request()

        start_serial = msg.get_bit_word(4, 8)
        count = msg.get_bit_word(12, 5)

        # The count is read on five bits and can announce more moves
        # than the answer is able to carry.
        kept = min(count, GEN2_MOVE_HISTORY_CAPACITY)

        if count > GEN2_MOVE_HISTORY_CAPACITY:
            logger.debug(
                'Move history message announces %d moves, '
                'only %d fit in the notification',
                count, GEN2_MOVE_HISTORY_CAPACITY,
            )

        for i in range(kept):
            face = msg.get_bit_word(17 + 5 * i, 4)
            direction = msg.get_bit_word(21 + 5 * i, 1)

            move = self.format_move(face, direction)

            if move is None:
                logger.debug(
                    'Move history message "0x07" carries an out of '
                    'domain move at index %d: face "%d", direction "%d"',
                    i, face, direction,
                )
                continue

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
                'move': move,
            }
            self.inject_missed_move_to_buffer(history_move)

        return await self.evict_move_buffer()

    async def handle_account_binding(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the answer of the cube to an account binding request.

        The application never sends that request, so this answer is not
        expected to be seen : the handler exists so that a cube sending
        one anyway is named in the journal instead of counted as an
        unknown opcode.

        Returns:
            Nothing, the result is journaled only.

        """
        result = msg.get_bit_word(4, 32)

        logger.debug('Account binding result: %s', result)

        return []
