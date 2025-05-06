import time
from datetime import datetime
from datetime import timezone

from term_timer.bluetooth.constants import GAN_ENCRYPTION_KEY
from term_timer.bluetooth.constants import GAN_GEN2_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN2_SERVICE
from term_timer.bluetooth.constants import GAN_GEN2_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN4_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN4_SERVICE
from term_timer.bluetooth.constants import GAN_GEN4_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_ENCRYPTION_KEY
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.facelets import to_kociemba_facelets
from term_timer.bluetooth.message import GanProtocolMessage
from term_timer.bluetooth.salt import get_salt


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

    last_serial = -1

    def init_cypher(self):
        if self.device.name.startswith('AiCube'):
            return self.encrypter(
                MOYU_ENCRYPTION_KEY['key'],
                MOYU_ENCRYPTION_KEY['iv'],
                get_salt(self.device.address),
            )
        return self.encrypter(
            GAN_ENCRYPTION_KEY['key'],
            GAN_ENCRYPTION_KEY['iv'],
            get_salt(self.device.address),
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
            serial = msg.get_bit_word(4, 8)
            diff = min((serial - self.last_serial) & 0xFF, 7)
            self.last_serial = serial

            for i in range(diff - 1, -1, -1):
                face = msg.get_bit_word(12 + 5 * i, 4)
                direction = msg.get_bit_word(16 + 5 * i, 1)
                move = 'URFDLB'[face] + " '"[direction]
                elapsed = msg.get_bit_word(47 + 16 * i, 16)
                # if elapsed == 0:
                #     # In case of 16-bit cube timestamp register overflow
                #     elapsed = timestamp - self.last_move_timestamp
                self.cube_timestamp += elapsed
                payload = {
                    'event': 'move',
                    'clock': clock,
                    'timestamp': timestamp,
                    'serial': (serial - i) & 0xFF,
                    # Missed and recovered events has no meaningful
                    # local timestamps
                    'localTimestamp': timestamp if i == 0 else None,
                    'cubeTimestamp': self.cube_timestamp,
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

        return events


class GanGen3Driver(GanGen2Driver):
    """
    GAN356 i Carry 2
    """
    service_uid = GAN_GEN3_SERVICE
    state_characteristic_uid = GAN_GEN3_STATE_CHARACTERISTIC
    command_characteristic_uid = GAN_GEN3_COMMAND_CHARACTERISTIC

    async def event_handler(self, sender, data):  # noqa: ARG002
        """Process notifications from the cube"""
        clock = time.perf_counter_ns()
        timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017

        events = []

        msg = GanProtocolMessage(
            self.cypher.decrypt(data),
        )
        magic = msg.get_bit_word(0, 8)
        event = msg.get_bit_word(8, 8)
        data_size = msg.get_bit_word(16, 8)

        if magic != 0x55 or data_size <= 0:
            return events

        if event == 0x01:  # Move
            serial = msg.get_bit_word(56, 16, little_endian=True)
            cube_timestamp = msg.get_bit_word(24, 32, little_endian=True)

            direction = msg.get_bit_word(72, 2)
            face = [2, 32, 8, 1, 16, 4].index(msg.get_bit_word(74, 6))
            move = 'URFDLB'[face] + " '"[direction]

            if face >= 0:
                payload = {
                    'event': 'move',
                    'clock': clock,
                    'timestamp': timestamp,
                    'serial': serial,
                    'localTimestamp': timestamp,
                    'cubeTimestamp': cube_timestamp,
                    'face': face,
                    'direction': direction,
                    'move': move.strip(),
                }
                self.add_event(events, payload)

        elif event == 0x02:  # Facelets
            serial = msg.get_bit_word(24, 16, little_endian=True)

            if self.last_serial == -1:
                self.last_serial = serial

            # Corner/Edge Permutation/Orientation
            cp = []
            co = []
            ep = []
            eo = []
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

        elif event == 0x06:  # Move history
            start_serial = msg.get_bit_word(24, 8)
            count = (data_size - 1) * 2

            for i in range(count):
                direction = msg.get_bit_word(35 + 4 * i, 1)
                face = [1, 5, 3, 0, 4, 2].index(msg.get_bit_word(32 + 4 * i, 3))
                move = 'URFDLB'[face] + " '"[direction]

                if face >= 0:
                    payload = {
                        'event': 'move-history',
                        'clock': clock,
                        'timestamp': timestamp,
                        'serial': (start_serial - i) & 0xFF,
                        'localTimestamp': None,
                        'cubeTimestamp': None,
                        'face': face,
                        'direction': direction,
                        'move': move.strip(),
                    }
                    self.add_event(events, payload)

        elif event == 0x07:  # Hardware
            sw_major = msg.get_bit_word(72, 4)
            sw_minor = msg.get_bit_word(76, 4)
            hw_major = msg.get_bit_word(80, 4)
            hw_minor = msg.get_bit_word(84, 4)

            hardware_name = ''
            for i in range(5):
                hardware_name += chr(msg.get_bit_word(i * 8 + 32, 8))

            payload = {
                'event': 'hardware',
                'clock': clock,
                'timestamp': timestamp,
                'hardware_name': hardware_name,
                'hardware_version': f'{ hw_major }.{ hw_minor }',
                'software_version': f'{ sw_major }.{ sw_minor }',
                'gyroscope_supported': False,
            }
            self.add_event(events, payload)

        elif event == 0x10:  # Battery
            battery_level = msg.get_bit_word(24, 8)

            payload = {
                'event': 'battery',
                'clock': clock,
                'timestamp': timestamp,
                'level': min(battery_level, 100),
            }
            self.add_event(events, payload)

        elif event == 0x11:  # Disconnect
            payload = {
                'event': 'disconnect',
                'clock': clock,
                'timestamp': timestamp,
            }
            self.add_event(events, payload)

            await self.client.disconnect()

        return events

    def send_command_handler(self, command: str):
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

        return self.cypher.encrypt(bytes(msg))


class GanGen4Driver(GanGen2Driver):
    """
    GAN12 ui Maglev
    GAN14 ui FreePlay
    """
    service_uid = GAN_GEN4_SERVICE
    state_characteristic_uid = GAN_GEN4_STATE_CHARACTERISTIC
    command_characteristic_uid = GAN_GEN4_COMMAND_CHARACTERISTIC

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
                    'localTimestamp': timestamp,
                    'cubeTimestamp': cube_timestamp,
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
                        'localTimestamp': None,
                        'cubeTimestamp': None,
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
