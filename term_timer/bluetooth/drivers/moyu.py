"""
Moyu Weilong V10 Driver.

References :
  - https://github.com/lukeburong/weilong-v10-ai-protocol
"""
import logging
from datetime import datetime
from typing import ClassVar

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDictNoState
from term_timer.bluetooth.annotations import GyroConfigEventDict
from term_timer.bluetooth.annotations import GyroEventDictNoVelocity
from term_timer.bluetooth.annotations import HardwareEventMoyuDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.constants import MOYU_FACE_NAMES
from term_timer.bluetooth.constants import MOYU_FACES
from term_timer.bluetooth.constants import MOYU_MOVE_CAPACITY
from term_timer.bluetooth.constants import MOYU_WEILONG_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_WEILONG_ENCRYPTION_KEY
from term_timer.bluetooth.constants import MOYU_WEILONG_SERVICE
from term_timer.bluetooth.constants import MOYU_WEILONG_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.message import GanProtocolMessage
from term_timer.bluetooth.salt import get_salt

logger = logging.getLogger(__name__)


class MoyuWeilong10Driver(Driver):
    """MoYu Weilong v10 AI."""

    service_uid: ClassVar[str] = MOYU_WEILONG_SERVICE
    state_characteristic_uid: ClassVar[str] = MOYU_WEILONG_STATE_CHARACTERISTIC
    command_characteristic_uid: ClassVar[str] = MOYU_WEILONG_COMMAND_CHARACTERISTIC  # noqa: E501
    encrypter: ClassVar[type[GanGen2CubeEncrypter]] = GanGen2CubeEncrypter
    factor: ClassVar[int] = pow(2, 30)
    # HARDWARE must precede FACELETS: the cube ignores facelets requests
    # until it has processed a hardware request first.
    init_commands: ClassVar[list[str]] = [
        'REQUEST_HARDWARE',
        'REQUEST_FACELETS',
        'REQUEST_BATTERY',
    ]
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {
        0xA0: 'handle_disconnect',
        0xA1: 'handle_hardware',
        0xA3: 'handle_facelets',
        0xA4: 'handle_battery',
        0xA5: 'handle_move',
        0xAB: 'handle_gyroscope',
        0xAC: 'handle_gyroscope_config',
    }

    def init_cypher(self) -> GanGen2CubeEncrypter:
        """
        Initialize encryption handler for cube communication.

        Returns:
            GanGen2CubeEncrypter instance with MoYu encryption keys.

        """
        return self.encrypter(
            MOYU_WEILONG_ENCRYPTION_KEY['key'],
            MOYU_WEILONG_ENCRYPTION_KEY['iv'],
            get_salt(self.client.address),
        )

    def send_command_handler(self, command: str) -> bytes | bool:
        """
        Build and encrypt command messages for MoYu Weilong cube.

        Returns:
            Encrypted command bytes or False if command is invalid.

        """
        msg = bytearray(20)

        if command == 'REQUEST_FACELETS':
            msg[0] = 0xA3
        elif command == 'REQUEST_HARDWARE':
            msg[0] = 0xA1
        elif command == 'REQUEST_BATTERY':
            msg[0] = 0xA4
        elif command == 'REQUEST_ENABLE_GYRO':
            msg[0] = 0xAC
            msg[2] = 0x01
        elif command == 'REQUEST_DISABLE_GYRO':
            msg[0] = 0xAC
        elif command == 'REQUEST_RESET':
            reset_sequence = [
                0xA2, 0x00, 0x00, 0x00, 0x24,
                0x92, 0x49, 0x49, 0x24, 0x92,
                0x6D, 0xB6, 0xDB, 0x92, 0x49,
                0x24, 0xB6, 0xDB, 0x6D, 0x00,
            ]
            msg = bytearray(reset_sequence)
        else:
            return False

        return self.cypher.encrypt(msg)

    async def handle_gyroscope(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the orientation sample of a gyroscope message.

        MoYu declares no angular velocity, only a quaternion.

        Returns:
            The gyroscope event, or nothing when the gyroscope is not
            used.

        """
        if not self.use_gyroscope:
            return []

        # Orientation Quaternion
        qw = msg.get_bit_word(8, 32, little_endian=True, signed=True)
        qx = msg.get_bit_word(40, 32, little_endian=True, signed=True)
        qy = msg.get_bit_word(72, 32, little_endian=True, signed=True)
        qz = msg.get_bit_word(104, 32, little_endian=True, signed=True)

        gyro_payload: GyroEventDictNoVelocity = {
            'event': 'gyro',
            'clock': clock,
            'timestamp': timestamp,
            'quaternion': {
                'x': qx / self.factor,
                'y': qy / self.factor,
                'z': qz / self.factor,
                'w': qw / self.factor,
            },
        }

        return [gyro_payload]

    async def handle_move(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the moves carried by a move message.

        A single message carries the last move plus the four previous
        ones, which is the capacity of the protocol.

        Returns:
            The decoded moves, oldest first, or nothing while the
            facelets have not been received yet.

        """
        if self.serial == -1:  # Block moves until facelets received
            return []

        serial = msg.get_bit_word(88, 8)
        diff = min((serial - self.serial) & 0xFF, MOYU_MOVE_CAPACITY)

        self.serial = serial

        if diff <= 0:
            return []

        moves: list[EventDict] = []

        for i in range(diff - 1, -1, -1):
            move_value = msg.get_bit_word(96 + i * 5, 5)
            elapsed_raw = msg.get_bit_word(8 + i * 16, 16)

            cube_timestamp = self.advance_cube_timestamp(
                elapsed_raw, timestamp,
            )

            # The five bits name sixteen faces where the cube turns
            # six : the mask is remapped onto URFDLB when the table
            # declares it, and left as it is when it does not, so that
            # format_move refuses it as it refuses any other field out
            # of its domain.
            mask = move_value >> 1
            face = MOYU_FACES.get(mask, mask)
            direction = move_value & 1

            move = self.format_move(face, direction)

            if move is None:
                logger.debug(
                    'Move message "0xA5" carries an out of domain move '
                    'at index %d: mask "%d", direction "%d"',
                    i, mask, direction,
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
            moves.append(move_payload)

        self.last_move_timestamp = timestamp

        return moves

    async def handle_facelets(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the cube state carried by a facelets message.

        A sticker is read on three bits, which name eight colours for
        six faces. One out of domain takes the whole frame with it :
        skipping it would cost the string a character and slide every
        sticker after it, and a false state is worse than no state at
        all — the driver already holds its moves until one arrives.

        Returns:
            The facelets event of the message, or nothing when a
            sticker falls outside of the six faces.

        """
        serial = msg.get_bit_word(152, 8)

        state = []
        # Parse in order URFDLB instead of FBUDLR
        for i in range(6):
            native = MOYU_FACES[i]

            for j in range(8):
                value = msg.get_bit_word(8 + (native * 24) + (j * 3), 3)

                if value >= len(MOYU_FACE_NAMES):
                    logger.debug(
                        'Facelets message "0xA3" carries an out of '
                        'domain colour "%d" on the face "%s", sticker '
                        '%d: the frame is dropped whole',
                        value, MOYU_FACE_NAMES[native], j,
                    )
                    return []

                state.append(MOYU_FACE_NAMES[value])

                if j == 3:
                    state.append(MOYU_FACE_NAMES[native])

        # The counter starts on a state the driver was able to read,
        # and never on one it had to throw away : it is what unblocks
        # the moves.
        if self.serial == -1:
            self.serial = serial

        facelets_payload: FaceletsEventDictNoState = {
            'event': 'facelets',
            'clock': clock,
            'timestamp': timestamp,
            'serial': serial,
            'facelets': ''.join(state),
        }

        return [facelets_payload]

    async def handle_hardware(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the hardware identity of the cube.

        Returns:
            The hardware event of the message.

        """
        hw_major = msg.get_bit_word(72, 8)
        hw_minor = msg.get_bit_word(80, 8)
        sw_major = msg.get_bit_word(88, 8)
        sw_minor = msg.get_bit_word(96, 8)
        gyro_enabled = msg.get_bit_word(105, 1)
        gyro_ready = msg.get_bit_word(106, 1)
        serial = msg.get_bit_word(109, 8)

        hardware_name = ''
        for i in range(8):
            hardware_name += chr(msg.get_bit_word(i * 8 + 8, 8))

        hardware_payload: HardwareEventMoyuDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'hardware_name': hardware_name,
            'hardware_version': f'{ hw_major }.{ hw_minor }',
            'software_version': f'{ sw_major }.{ sw_minor }',
            'gyroscope_enabled': bool(gyro_enabled),
            'gyroscope_ready': bool(gyro_ready),
            # Whether the cube carries the sensor, and not whether it
            # has it switched on : the two were the same expression,
            # and the cube in hand — enabled False, ready True — was
            # published as not supporting a gyroscope it had simply
            # turned off. The ready bit is what the firmware says.
            'gyroscope_supported': bool(gyro_ready),
            'serial': serial,
        }

        return [hardware_payload]

    async def handle_gyroscope_config(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the answer to a gyroscope configuration request.

        Returns:
            The gyro-config event of the message.

        """
        gyro_enabled = msg.get_bit_word(16, 8)
        gyro_ready = msg.get_bit_word(8, 8)

        gyro_config_payload: GyroConfigEventDict = {
            'event': 'gyro-config',
            'clock': clock,
            'timestamp': timestamp,
            'gyroscope_enabled': bool(gyro_enabled),
            'gyroscope_ready': bool(gyro_ready),
            # Same reading as the hardware message : a cube announcing
            # its gyroscope off still carries one.
            'gyroscope_supported': bool(gyro_ready),
        }

        return [gyro_config_payload]
