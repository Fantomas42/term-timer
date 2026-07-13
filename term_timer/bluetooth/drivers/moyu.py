"""
Moyu Weilong V10 Driver.

References :
  - https://github.com/lukeburong/weilong-v10-ai-protocol
"""
import logging
import time
from datetime import datetime
from datetime import timezone
from typing import ClassVar

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDictNoState
from term_timer.bluetooth.annotations import GyroConfigEventDict
from term_timer.bluetooth.annotations import GyroEventDictNoVelocity
from term_timer.bluetooth.annotations import HardwareEventMoyuDict
from term_timer.bluetooth.annotations import MoveEventDict
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
    """Weilong v10."""

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

    def __init__(self, client: BleakClient,
                 *, use_gyroscope: bool) -> None:
        """Initialize MoYu Weilong driver with BLE client connection."""
        super().__init__(client, use_gyroscope=use_gyroscope)

        self.last_serial: int = -1
        self.cube_timestamp: float = 0.0
        self.last_move_timestamp: datetime | None = None

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

    async def event_handler(  # noqa: C901, PLR0912, PLR0914, PLR0915
            self, sender: BleakGATTCharacteristic,  # noqa: ARG002
            data: bytearray) -> list[EventDict]:
        """
        Process notifications from the cube.

        Returns:
            List of event dictionaries parsed from cube notifications.

        """
        clock = time.perf_counter_ns()
        timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017

        events: list[EventDict] = []

        msg = GanProtocolMessage(
            self.cypher.decrypt(data),
        )
        event = msg.get_bit_word(0, 8)

        if event == 0xAB:  # Gyroscope
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

            self.add_event(events, gyro_payload)

        elif event == 0xA5:  # Moves
            if self.last_serial == -1:  # Block moves until facelets received
                return []

            serial = msg.get_bit_word(88, 8)
            diff = min((serial - self.last_serial) & 0xFF, 5)

            self.last_serial = serial

            if diff <= 0:
                return []

            for i in range(diff - 1, -1, -1):
                move_value = msg.get_bit_word(96 + i * 5, 5)
                move = 'FBUDLR'[move_value >> 1] + " '"[move_value & 1]
                elapsed_raw = msg.get_bit_word(8 + i * 16, 16)

                # In case of 16-bit cube timestamp register overflow
                elapsed: float
                if elapsed_raw == 0 and self.last_move_timestamp is not None:
                    elapsed = (
                        timestamp - self.last_move_timestamp
                    ).total_seconds()
                else:
                    elapsed = float(elapsed_raw)

                self.cube_timestamp += elapsed
                move_payload: MoveEventDict = {
                    'event': 'move',
                    'clock': clock,
                    'timestamp': timestamp,
                    'serial': (serial - i) & 0xFF,
                    # Missed and recovered events
                    # has no meaningful local timestamps
                    'local_timestamp': timestamp if i == 0 else None,
                    'cube_timestamp': self.cube_timestamp,
                    'face': move_value,
                    'direction': move_value,
                    'move': move.strip(),
                }
                self.add_event(events, move_payload)

            self.last_move_timestamp = timestamp

        elif event == 0xA3:  # Facelets
            serial = msg.get_bit_word(152, 8)

            if self.last_serial == -1:
                self.last_serial = serial

            state = []
            # Parse in order URFDLB instead of FBUDLR
            faces = [2, 5, 0, 3, 4, 1]
            for i in range(6):
                for j in range(8):
                    value = msg.get_bit_word(8 + (faces[i] * 24) + (j * 3), 3)
                    state.append('FBUDLR'[value])
                    if j == 3:
                        state.append('FBUDLR'[faces[i]])

            facelets_payload: FaceletsEventDictNoState = {
                'event': 'facelets',
                'clock': clock,
                'timestamp': timestamp,
                'serial': serial,
                'facelets': ''.join(state),
            }
            self.add_event(events, facelets_payload)

        elif event == 0xA1:  # Hardware
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
                'gyroscope_supported': (
                    bool(gyro_enabled)
                    and bool(gyro_ready)
                ),
                'serial': serial,
            }
            self.add_event(events, hardware_payload)

        elif event == 0xAC:  # Gyro config
            gyro_enabled = msg.get_bit_word(16, 8)
            gyro_ready = msg.get_bit_word(8, 8)

            gyro_config_payload: GyroConfigEventDict = {
                'event': 'gyro-config',
                'clock': clock,
                'timestamp': timestamp,
                'gyroscope_enabled': bool(gyro_enabled),
                'gyroscope_ready': bool(gyro_ready),
                'gyroscope_supported': (
                    bool(gyro_enabled)
                    and bool(gyro_ready)
                ),
            }
            self.add_event(events, gyro_config_payload)

        elif event == 0xA4:  # Battery
            battery_level = msg.get_bit_word(8, 8)

            battery_payload: BatteryEventDict = {
                'event': 'battery',
                'clock': clock,
                'charging_state': 0,
                'timestamp': timestamp,
                'level': min(battery_level, 100),
            }
            self.add_event(events, battery_payload)

        else:
            logger.debug(
                'Unknown event type "%s": %s', event, msg,
            )

        return events
