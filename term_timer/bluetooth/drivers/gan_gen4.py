import logging
import time
from datetime import datetime
from datetime import timezone

from term_timer.bluetooth.constants import GAN_GEN4_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN4_SERVICE
from term_timer.bluetooth.constants import GAN_GEN4_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.facelets import to_kociemba_facelets
from term_timer.bluetooth.message import GanProtocolMessage

logger = logging.getLogger(__name__)


class GanGen4Driver(GanGen2Driver):
    """
    GAN12 ui Maglev
    GAN14 ui FreePlay
    """
    service_uid = GAN_GEN4_SERVICE
    state_characteristic_uid = GAN_GEN4_STATE_CHARACTERISTIC
    command_characteristic_uid = GAN_GEN4_COMMAND_CHARACTERISTIC

    def send_command_handler(self, command: str):
        msg = bytearray(20)

        if command == 'REQUEST_FACELETS':
            values = [0xDD, 0x04, 0x00, 0xED, 0x00, 0x00]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_HARDWARE':
            values = [0xDF, 0x03, 0x00, 0x00, 0x00]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_BATTERY':
            values = [0xDD, 0x04, 0x00, 0xEF, 0x00, 0x00]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_RESET':
            values = [
                0xD2, 0x0D, 0x05, 0x39, 0x77, 0x00, 0x00, 0x01,
                0x23, 0x45, 0x67, 0x89, 0xAB, 0x00, 0x00, 0x00,
            ]
            for i, val in enumerate(values):
                msg[i] = val
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
        data_size = msg.get_bit_word(8, 8)

        if event == 0x01:  # Move
            serial = msg.get_bit_word(48, 16, little_endian=True)
            cube_timestamp = msg.get_bit_word(16, 32, little_endian=True)

            direction = msg.get_bit_word(64, 2)
            face = [2, 32, 8, 1, 16, 4].index(msg.get_bit_word(66, 6))
            move = 'URFDLB'[face] + " '"[direction]

            if face >= 0:
                payload = {
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
                self.add_event(events, payload)

        elif event == 0xED:  # Facelets
            serial = msg.get_bit_word(16, 16, little_endian=True)

            if self.last_serial == -1:
                self.last_serial = serial

            # Corner/Edge Permutation/Orientation
            cp = []
            co = []
            ep = []
            eo = []
            # Corners
            for i in range(7):
                cp.append(msg.get_bit_word(32 + i * 3, 3))
                co.append(msg.get_bit_word(53 + i * 2, 2))
            cp.append(28 - sum(cp))
            co.append((3 - (sum(co) % 3)) % 3)
            # Edges
            for i in range(11):
                ep.append(msg.get_bit_word(69 + i * 4, 4))
                eo.append(msg.get_bit_word(113 + i, 1))
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

        elif event == 0xD1:  # Move history
            start_serial = msg.get_bit_word(16, 8)
            count = (data_size - 1) * 2

            for i in range(count):
                direction = msg.get_bit_word(27 + 4 * i, 1)
                face = [1, 5, 3, 0, 4, 2].index(msg.get_bit_word(24 + 4 * i, 3))
                move = 'URFDLB'[face] + " '"[direction]

                if face >= 0:
                    payload = {
                        'event': 'move-history',
                        'clock': clock,
                        'timestamp': timestamp,
                        'serial': (start_serial - i) & 0xFF,
                        'local_timestamp': None,
                        'cube_timestamp': None,
                        'face': face,
                        'direction': direction,
                        'move': move.strip(),
                    }
                    self.add_event(events, payload)

        elif event >= 0xFA and event <= 0xFE:  # Hardware
            if event == 0xFA:  # Product date
                year = msg.get_bit_word(24, 16, little_endian=True)
                month = msg.get_bit_word(40, 8)
                day = msg.get_bit_word(48, 8)

                payload = {
                    'event': 'hardware',
                    'clock': clock,
                    'timestamp': timestamp,
                    'product_date': f'{ year:04d}-{ month:02d}-{ day:02d}',
                }
                self.add_event(events, payload)
            elif event == 0xFC:  # Hardware name
                hardware_name = ''
                for i in range(data_size):
                    hardware_name += chr(msg.get_bit_word(i * 8 + 24, 8))
                payload = {
                    'event': 'hardware',
                    'clock': clock,
                    'timestamp': timestamp,
                    'hardware_name': hardware_name,
                    'gyroscope_supported': 'GAN12uiM' in hardware_name,
                }
                self.add_event(events, payload)
            elif event == 0xFD:  # Software version
                sw_major = msg.get_bit_word(24, 4)
                sw_minor = msg.get_bit_word(28, 4)

                payload = {
                    'event': 'hardware',
                    'clock': clock,
                    'software_version': f'{ sw_major }.{ sw_minor }',
                }
                self.add_event(events, payload)
            elif event == 0xFE:  # Hardware version
                hw_major = msg.get_bit_word(24, 4)
                hw_minor = msg.get_bit_word(28, 4)

                payload = {
                    'event': 'hardware',
                    'clock': clock,
                    'hardware_version': f'{ hw_major }.{ hw_minor }',
                }
                self.add_event(events, payload)

        elif event == 0xEC:  # Gyroscope
            if self.disable_gyro:
                return []
            # Orientation Quaternion
            qw = msg.get_bit_word(16, 16)
            qx = msg.get_bit_word(32, 16)
            qy = msg.get_bit_word(48, 16)
            qz = msg.get_bit_word(64, 16)

            # Angular Velocity
            vx = msg.get_bit_word(80, 4)
            vy = msg.get_bit_word(84, 4)
            vz = msg.get_bit_word(88, 4)

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

        elif event == 0xEF:  # Battery
            battery_level = msg.get_bit_word(8 + data_size * 8, 8)

            payload = {
                'event': 'battery',
                'clock': clock,
                'timestamp': timestamp,
                'level': min(battery_level, 100),
            }
            self.add_event(events, payload)

        elif event == 0xEA:  # Disconnect
            payload = {
                'event': 'disconnect',
                'clock': clock,
                'timestamp': timestamp,
            }
            self.add_event(events, payload)

            await self.client.disconnect()

        return events
