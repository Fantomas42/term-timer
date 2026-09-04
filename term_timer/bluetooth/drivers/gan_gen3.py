"""
GAN Gen3 Driver.

References :
  - https://github.com/afedotov/gan-web-bluetooth
  - https://github.com/Fantomas42/gan-protocols
"""
import logging
from datetime import datetime
from typing import ClassVar

from bleak import BleakClient
from cubing_algs.facelets import cubies_to_facelets

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDict
from term_timer.bluetooth.annotations import HardwareEventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.annotations import ResetEventDict
from term_timer.bluetooth.annotations import SolvedEventDict
from term_timer.bluetooth.constants import DEBOUNCE
from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import GEN3_HISTORY_FACES
from term_timer.bluetooth.constants import GEN3_MOVE_FACES
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.message import GanProtocolMessage

logger = logging.getLogger(__name__)


class GanGen3Driver(GanGen2Driver):
    """GAN i carry 2."""

    service_uid: ClassVar[str] = GAN_GEN3_SERVICE
    state_characteristic_uid: ClassVar[str] = GAN_GEN3_STATE_CHARACTERISTIC
    command_characteristic_uid: ClassVar[str] = GAN_GEN3_COMMAND_CHARACTERISTIC
    payload_offset: ClassVar[int] = 16
    chained: ClassVar[bool] = True
    head_magic: ClassVar[int | None] = 0x55
    crc_terminator: ClassVar[int] = 2
    # V2 reads its battery level straight behind the header, and
    # declares no charging state : V1 is the only generation to.
    battery_level_offset: ClassVar[int] = 0
    charging_state_width: ClassVar[int] = 0
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {
        0x01: 'handle_move',
        0x02: 'handle_facelets',
        0x06: 'handle_move_history',
        0x07: 'handle_hardware',
        0x08: 'handle_reset',
        0x09: 'handle_account_binding',
        0x0F: 'handle_flag',
        0x10: 'handle_battery',
        0x11: 'handle_disconnect',
        0x12: 'handle_result',
        0x14: 'handle_solved',
    }

    def __init__(self, client: BleakClient,
                 *, use_gyroscope: bool) -> None:
        """
        Initialize the GAN Gen3 driver with move tracking capabilities.

        The serial tracking and the FIFO buffer of the missed moves come
        from the Gen2 driver, which owns them for the three generations.

        Args:
            client: The BLE client connection to the cube.
            use_gyroscope: Whether the driver should use gyroscope data.

        """
        super().__init__(client, use_gyroscope=use_gyroscope)

        self.last_local_timestamp: datetime | None = None

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

        `appProtoId 9` of `GanSDK_ProtocolWriteV2` declares `step` and
        `count` on sixteen bits each, little endian, and both are
        written whole : a count capped at `serial + 1` reaches 256 as
        soon as a whole cycle is missed, which no longer fits on the
        single byte the frame used to carry.

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
        msg[2] = serial & 0xFF
        msg[3] = serial >> 8
        msg[4] = count & 0xFF
        msg[5] = count >> 8

        logger.debug('Sending : REQUEST_MOVE_HISTORY')

        await self.client.write_gatt_char(
            self.command_characteristic_uid,
            self.cypher.encrypt(msg),
        )

    @staticmethod
    def read_event_code(msg: GanProtocolMessage) -> int:
        """
        Read the opcode of a V2 message.

        The head of the notification having been stripped, a V2 message
        opens on its bleProtoId as a V3 one does. The redefinition is
        kept because the Gen2 driver reads its own opcode on four bits,
        and this driver inherits from it.

        Returns:
            The opcode of the message.

        """
        return msg.get_bit_word(0, 8)

    @classmethod
    def is_message_valid(cls, msg: GanProtocolMessage) -> bool:
        """
        Check the length a V2 or a V3 message declares.

        The dataLength byte closes the header of both generations, so
        it sits at `payload_offset - 8` in either : the check is the
        same one, and the Gen4 driver inherits it.

        Returns:
            True when the message declares a payload.

        """
        return msg.get_bit_word(cls.payload_offset - 8, 8) > 0

    @staticmethod
    def format_build_time(msg: GanProtocolMessage, start: int) -> str:
        """
        Read the five fields of a build time and format them.

        V2 and V3 lay the same five fields out — a year on sixteen bits
        little endian, then a month, a day, an hour and a minute of
        eight — at two different offsets : 80 for the `0x07` of V2,
        which the descriptor under-declares (§4.2), and 24 for the
        `0xF5` of V3.

        Args:
            msg: The message carrying the fields.
            start: Bit the year of the build time starts at.

        Returns:
            The build time, as a readable date and time.

        """
        year = msg.get_bit_word(start, 16, little_endian=True)
        month = msg.get_bit_word(start + 16, 8)
        day = msg.get_bit_word(start + 24, 8)
        hour = msg.get_bit_word(start + 32, 8)
        minute = msg.get_bit_word(start + 40, 8)

        return (
            f'{year:04d}-{month:02d}-{day:02d} '
            f'{hour:02d}:{minute:02d}'
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
        serial = msg.get_bit_word(
            self.payload_offset + 32, 16, little_endian=True,
        )
        cube_timestamp = msg.get_bit_word(
            self.payload_offset, 32, little_endian=True,
        )

        direction = msg.get_bit_word(self.payload_offset + 48, 2)
        face_mask = msg.get_bit_word(self.payload_offset + 50, 6)
        face = GEN3_MOVE_FACES.get(face_mask)
        move = None if face is None else self.format_move(face, direction)

        # A move that cannot be named is not lost for that : it leaves
        # a hole in the serial numbers, which the eviction sees and
        # answers with a move history request.
        if face is None or move is None:
            logger.debug(
                'Move message "0x01" carries an out of domain move: '
                'face mask "0x%02X", direction "%d"',
                face_mask, direction,
            )
            return await self.evict_move_buffer()

        # Put move event into FIFO buffer
        move_event: MoveEventDict = {
            'event': 'move',
            'clock': clock,
            'timestamp': timestamp,
            'serial': serial,
            'local_timestamp': timestamp,
            'cube_timestamp': cube_timestamp,
            'face': face,
            'direction': direction,
            'move': move,
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
        # `step` is declared and carried on sixteen bits, but the
        # firmware cycles it on its low byte alone : measured on a GAN
        # i carry 2 the 2026-09-02, the counter went 253 -> 4, its high
        # byte never leaving zero. Every serial comparison of the move
        # buffer therefore wraps on 0xFF, as the Gen2 driver does.
        serial = msg.get_bit_word(
            self.payload_offset, 16, little_endian=True,
        )
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
            cp.append(msg.get_bit_word(self.payload_offset + 16 + i * 3, 3))
            co.append(msg.get_bit_word(self.payload_offset + 37 + i * 2, 2))
        cp.append(28 - sum(cp))
        co.append((3 - (sum(co) % 3)) % 3)
        # Edges
        for i in range(11):
            ep.append(msg.get_bit_word(self.payload_offset + 53 + i * 4, 4))
            eo.append(msg.get_bit_word(self.payload_offset + 97 + i, 1))
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
        data_size = msg.get_bit_word(self.payload_offset - 8, 8)
        start_serial = msg.get_bit_word(self.payload_offset, 8)
        count = (data_size - 1) * 2

        for i in range(count):
            direction = msg.get_bit_word(self.payload_offset + 11 + 4 * i, 1)
            face_id = msg.get_bit_word(self.payload_offset + 8 + 4 * i, 3)
            face = GEN3_HISTORY_FACES.get(face_id)

            move = None if face is None else self.format_move(face, direction)

            if face is None or move is None:
                logger.debug(
                    'Move history message "0x06" carries an out of '
                    'domain move at index %d: face "%d", direction "%d"',
                    i, face_id, direction,
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

    async def handle_hardware(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the hardware identity of the cube.

        The descriptor under-declares this message, and the wire is what
        settles it : the cube announces 14 bytes of payload where
        `bleProtoId 7` declares 11, and `buildTime` carries the same
        five fields as V3 rather than the 32 bits declared. Measured on
        a GAN i carry 2 the 2026-09-02, its CRC-16 closing the frame.

        Returns:
            The hardware event of the message.

        """
        restart_reason = msg.get_bit_word(16, 8)

        hardware_name = ''
        for i in range(5):
            hardware_name += chr(msg.get_bit_word(i * 8 + 24, 8))

        sw_major = msg.get_bit_word(64, 4)
        sw_minor = msg.get_bit_word(68, 4)
        hw_major = msg.get_bit_word(72, 4)
        hw_minor = msg.get_bit_word(76, 4)

        build_time = self.format_build_time(msg, 80)

        logger.debug('Build time: %s', build_time)

        hardware_payload: HardwareEventDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'restart_no_power': restart_reason,
            'build_time': build_time,
            'hardware_name': hardware_name,
            'hardware_version': f'{ hw_major }.{ hw_minor }',
            'software_version': f'{ sw_major }.{ sw_minor }',
            'gyroscope_enabled': False,
            'gyroscope_ready': False,
            'gyroscope_supported': False,
        }

        return [hardware_payload]

    async def handle_reset(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Acknowledge that the cube state has been reset.

        `bleProtoId 8` carries a `result` the driver used to drop, where
        the reset it acknowledges is the one destructive command of the
        protocol. The value is published rather than judged here : V2
        declares it a boolean of eight bits and V3 an integer of
        thirty-two, and only a subscriber knows what it wants to do with
        a reset the cube refused.

        Returns:
            The reset event of the message.

        """
        reset_payload: ResetEventDict = {
            'event': 'reset',
            'clock': clock,
            'timestamp': timestamp,
            'result': msg.get_bit_word(self.payload_offset, 8),
        }

        return [reset_payload]

    async def handle_account_binding(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the answer of the cube to an account binding request.

        The Gen2 handler cannot be inherited : `GanSDK_ProtocolV1.json`
        declares `isBigEndia: 1` where V2 declares `0`, so the same
        `result` of 32 bits is read the other way round here.

        The application never sends that request, so this answer is not
        expected to be seen : the handler exists so that a cube sending
        one anyway is named in the journal instead of counted as an
        unknown opcode.

        Returns:
            Nothing, the result is journaled only.

        """
        result = msg.get_bit_word(
            self.payload_offset, 32, little_endian=True,
        )

        logger.debug('Account binding result: %s', result)

        return []

    async def handle_flag(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the flag the cube announces under `bleProtoId 15`.

        The descriptor names the field `flag` and gives its width, and
        says nothing of what it means : it is journaled raw, and what it
        carries will be read there the day a cube sends one.

        Returns:
            Nothing, the flag is journaled only.

        """
        logger.debug(
            'Flag message "0x0F": flag %s',
            msg.get_bit_word(self.payload_offset, 8),
        )

        return []

    async def handle_result(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the result the cube announces under `bleProtoId 18`.

        The descriptor declares a boolean of eight bits and names no
        command it answers : as for `handle_flag`, it is journaled raw
        rather than interpreted.

        Returns:
            Nothing, the result is journaled only.

        """
        logger.debug(
            'Result message "0x12": result %s',
            msg.get_bit_word(self.payload_offset, 8),
        )

        return []

    async def handle_solved(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the solve the cube announces on its own.

        `bleProtoId 20` in V2 and `bleProtoId 2` in V3 are the same
        message under two codes, declared field for field alike : the
        cube saying it sees itself solved, timed on its own clock. The
        clock it carries is the one of the move that closed the solve,
        the message arriving chained behind it.

        Returns:
            The solved event of the message.

        """
        solved_payload: SolvedEventDict = {
            'event': 'solved',
            'clock': clock,
            'timestamp': timestamp,
            'cube_timestamp': msg.get_bit_word(
                self.payload_offset, 32, little_endian=True,
            ),
        }

        return [solved_payload]
