"""
References :
  - https://github.com/afedotov/gan-web-bluetooth
"""
import logging
import time
from datetime import datetime
from datetime import timezone

from term_timer.bluetooth.constants import GAN_ENCRYPTION_KEY
from term_timer.bluetooth.constants import GAN_GEN2_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN2_SERVICE
from term_timer.bluetooth.constants import GAN_GEN2_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_AI_ENCRYPTION_KEY
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.facelets import to_kociemba_facelets
from term_timer.bluetooth.message import GanProtocolMessage
from term_timer.bluetooth.salt import get_salt

logger = logging.getLogger(__name__)


class GanGen2Driver(Driver):
    """
    GAN Mini ui FreePlay
    GAN12 ui FreePlay
    GAN12 ui
    GAN356 i Carry S
    GAN356 i Carry
    GAN356 i 3
    Monster Go 3Ai
    MoYu AI 2023
    """
    service_uid = GAN_GEN2_SERVICE
    state_characteristic_uid = GAN_GEN2_STATE_CHARACTERISTIC
    command_characteristic_uid = GAN_GEN2_COMMAND_CHARACTERISTIC
    encrypter = GanGen2CubeEncrypter

    def __init__(self, client):
        super().__init__(client)

        self.last_serial = -1
        self.cube_timestamp = 0
        self.last_move_timestamp = 0

    def init_cypher(self):
        if self.client.name.startswith('AiCube'):  # noqa: SLF001
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

    def send_command_handler(self, command: str):
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

        return self.cypher.encrypt(bytes(msg))

    async def event_handler(self, sender, data):  # noqa: ARG002
        """Process notifications from the cube"""
        clock = time.perf_counter_ns()
        timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017

        events = []

        msg = GanProtocolMessage(
            self.cypher.decrypt(data),
        )
        event = msg.get_bit_word(0, 4)

        if event == 0x01:  # Gyroscope
            if self.disable_gyro:
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

            payload = {
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

            self.add_event(events, payload)

        elif event == 0x02:  # Moves
            if self.last_serial == -1:  # Block moves until facelets received
                return []

            serial = msg.get_bit_word(4, 8)
            diff = min((serial - self.last_serial) & 0xFF, 7)

            self.last_serial = serial

            if diff <= 0:
                return []

            for i in range(diff - 1, -1, -1):
                face = msg.get_bit_word(12 + 5 * i, 4)
                direction = msg.get_bit_word(16 + 5 * i, 1)
                move = 'URFDLB'[face] + " '"[direction]
                elapsed = msg.get_bit_word(47 + 16 * i, 16)

                # In case of 16-bit cube timestamp register overflow
                if elapsed == 0 and self.last_move_timestamp:
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
                    'face': face,
                    'direction': direction,
                    'move': move.strip(),
                }
                self.add_event(events, payload)

            self.last_move_timestamp = timestamp

        elif event == 0x04:  # Facelets
            serial = msg.get_bit_word(4, 8)

            if self.last_serial == -1:
                self.last_serial = serial

            # Corner/Edge Permutation/Orientation
            cp = []
            co = []
            ep = []
            eo = []
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

            payload = {
                'event': 'facelets',
                'clock': clock,
                'timestamp': timestamp,
                'serial': serial,
                'facelets': to_kociemba_facelets(cp, co, ep, eo),
                'state': {
                    'CP': cp,
                    'CO': co,
                    'EP': ep,
                    'EO': eo,
                },
            }
            self.add_event(events, payload)

        elif event == 0x05:  # Hardware
            hw_major = msg.get_bit_word(8, 8)
            hw_minor = msg.get_bit_word(16, 8)
            sw_major = msg.get_bit_word(24, 8)
            sw_minor = msg.get_bit_word(32, 8)
            gyro_supported = msg.get_bit_word(104, 1)

            hardware_name = ''
            for i in range(8):
                hardware_name += chr(msg.get_bit_word(i * 8 + 40, 8))

            payload = {
                'event': 'hardware',
                'clock': clock,
                'timestamp': timestamp,
                'hardware_name': hardware_name,
                'hardware_version': f'{ hw_major }.{ hw_minor }',
                'software_version': f'{ sw_major }.{ sw_minor }',
                'gyroscope_supported': bool(gyro_supported),
            }
            self.add_event(events, payload)

        elif event == 0x09:  # Battery
            battery_level = msg.get_bit_word(8, 8)

            payload = {
                'event': 'battery',
                'clock': clock,
                'timestamp': timestamp,
                'level': min(battery_level, 100),
            }
            self.add_event(events, payload)

        elif event == 0x0D:  # Disconnect
            payload = {
                'event': 'disconnect',
                'clock': clock,
                'timestamp': timestamp,
            }
            self.add_event(events, payload)

            await self.client.disconnect()

        else:
            logger.debug(
                'Unknown event type "%s": %s', event, msg,
            )

        return events
