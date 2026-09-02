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

from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDict
from term_timer.bluetooth.annotations import HardwareEventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.annotations import ResetEventDict
from term_timer.bluetooth.constants import DEBOUNCE
from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.message import GanProtocolMessage

logger = logging.getLogger(__name__)


class GanGen3Driver(GanGen2Driver):
    """GAN i carry 2."""

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

        The descriptor under-declares this message, and the wire is what
        settles it : the cube announces 14 bytes of payload where
        `bleProtoId 7` declares 11, and `buildTime` carries the same
        five fields as V3 rather than the 32 bits declared. Measured on
        a GAN i carry 2 the 2026-09-02, its CRC-16 closing the frame.

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

        year = msg.get_bit_word(88, 16, little_endian=True)
        month = msg.get_bit_word(104, 8)
        day = msg.get_bit_word(112, 8)
        hour = msg.get_bit_word(120, 8)
        minute = msg.get_bit_word(128, 8)
        build_time = (
            f'{year:04d}-{month:02d}-{day:02d} '
            f'{hour:02d}:{minute:02d}'
        )

        logger.debug('Build time: %s', build_time)

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
