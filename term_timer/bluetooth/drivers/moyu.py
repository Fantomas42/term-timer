"""
References :
  - https://github.com/lukeburong/weilong-v10-ai-protocol
"""
import logging
import time
from datetime import datetime
from datetime import timezone

from term_timer.bluetooth.constants import MOYU_WEILONG_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_WEILONG_ENCRYPTION_KEY
from term_timer.bluetooth.constants import MOYU_WEILONG_SERVICE
from term_timer.bluetooth.constants import MOYU_WEILONG_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.facelets import to_kociemba_facelets
from term_timer.bluetooth.message import GanProtocolMessage
from term_timer.bluetooth.salt import get_salt

logger = logging.getLogger(__name__)


class MoyuWeilong10Driver(Driver):
    """
    Weilong v10
    """
    service_uid = MOYU_WEILONG_SERVICE
    state_characteristic_uid = MOYU_WEILONG_STATE_CHARACTERISTIC
    command_characteristic_uid = MOYU_WEILONG_COMMAND_CHARACTERISTIC
    encrypter = GanGen2CubeEncrypter

    last_serial = -1
    cube_timestamp = 0
    last_move_timestamp = 0

    def init_cypher(self):
        return self.encrypter(
            MOYU_WEILONG_ENCRYPTION_KEY['key'],
            MOYU_WEILONG_ENCRYPTION_KEY['iv'],
            get_salt(self.device.address),
        )

    def send_command_handler(self, command: str):
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
                0x24, 0xB6, 0xDB, 0x6D, 0x02,
            ]
            msg = bytearray(reset_sequence)
        else:
            return False

        return self.cypher.encrypt(bytes(msg))

    async def event_handler(self, sender, data):  # noqa: ARG002
        """Process notifications from the cube"""
        clock = time.perf_counter_ns()
        timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017

        events = []

        msg = GanProtocolMessage(
            self.cypher.decrypt(data),
        )
        event = msg.get_bit_word(0, 8)

        if event == 0xAB:  # Gyroscope
            if self.disable_gyro:
                return []

        #     # Orientation Quaternion
        #     qw = msg.get_bit_word(4, 16)
        #     qx = msg.get_bit_word(20, 16)
        #     qy = msg.get_bit_word(36, 16)
        #     qz = msg.get_bit_word(52, 16)

        #     # Angular Velocity
        #     vx = msg.get_bit_word(68, 4)
        #     vy = msg.get_bit_word(72, 4)
        #     vz = msg.get_bit_word(76, 4)

        #     payload = {
        #         'event': 'gyro',
        #         'clock': clock,
        #         'timestamp': timestamp,
        #         'quaternion': {
        #             'x': (1 - (qx >> 15) * 2) * (qx & 0x7FFF) / 0x7FFF,
        #             'y': (1 - (qy >> 15) * 2) * (qy & 0x7FFF) / 0x7FFF,
        #             'z': (1 - (qz >> 15) * 2) * (qz & 0x7FFF) / 0x7FFF,
        #             'w': (1 - (qw >> 15) * 2) * (qw & 0x7FFF) / 0x7FFF,
        #         },
        #         'velocity': {
        #             'x': (1 - (vx >> 3) * 2) * (vx & 0x7),
        #             'y': (1 - (vy >> 3) * 2) * (vy & 0x7),
        #             'z': (1 - (vz >> 3) * 2) * (vz & 0x7),
        #         },
        #     }

        #     self.add_event(events, payload)

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
                elapsed = msg.get_bit_word(8 + i * 16, 16)

                # In case of 16-bit cube timestamp register overflow
                if elapsed == 0:
                    elapsed = (
                        timestamp - self.last_move_timestamp
                    ).total_seconds()

                self.cube_timestamp += elapsed
                payload = {
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
                self.add_event(events, payload)

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

            payload = {
                'event': 'facelets',
                'clock': clock,
                'timestamp': timestamp,
                'serial': serial,
                'facelets': ''.join(state),
            }
            self.add_event(events, payload)

        elif event == 0xA1:  # Hardware
            hw_major = msg.get_bit_word(72, 8)
            hw_minor = msg.get_bit_word(80, 8)
            sw_major = msg.get_bit_word(88, 8)
            sw_minor = msg.get_bit_word(96, 8)
            gyro_enabled = msg.get_bit_word(105, 1)
            gyro_supported = msg.get_bit_word(106, 1)
            serial = msg.get_bit_word(109, 8)

            hardware_name = ''
            for i in range(8):
                hardware_name += chr(msg.get_bit_word(i * 8 + 8, 8))

            payload = {
                'event': 'hardware',
                'clock': clock,
                'timestamp': timestamp,
                'hardware_name': hardware_name,
                'hardware_version': f'{ hw_major }.{ hw_minor }',
                'software_version': f'{ sw_major }.{ sw_minor }',
                'gyroscope_enabled': bool(gyro_enabled),
                'gyroscope_support': bool(gyro_supported),
                'gyroscope_supported': (
                    bool(gyro_supported)
                    and bool(gyro_enabled)
                ),
                'serial': serial,
            }
            self.add_event(events, payload)

        elif event == 0xAC:  # Gyro config
            gyro_enabled = msg.get_bit_word(16, 8)
            gyro_supported = msg.get_bit_word(8, 8)

            payload = {
                'event': 'gyro-config',
                'clock': clock,
                'timestamp': timestamp,
                'gyroscope_enabled': bool(gyro_enabled),
                'gyroscope_support': bool(gyro_supported),
                'gyroscope_supported': (
                    bool(gyro_supported)
                    and bool(gyro_enabled)
                ),
            }
            self.add_event(events, payload)

        elif event == 0xA4:  # Battery
            battery_level = msg.get_bit_word(8, 8)

            payload = {
                'event': 'battery',
                'clock': clock,
                'timestamp': timestamp,
                'level': min(battery_level, 100),
            }
            self.add_event(events, payload)

        else:
            logger.debug(
                'Unknown event type "%s": %s', event, msg,
            )

        return events
