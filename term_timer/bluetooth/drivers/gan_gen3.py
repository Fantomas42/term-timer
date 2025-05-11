"""
References :
  - https://github.com/afedotov/gan-web-bluetooth
"""
import logging
import time
from datetime import datetime
from datetime import timezone

from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.facelets import to_kociemba_facelets
from term_timer.bluetooth.message import GanProtocolMessage

logger = logging.getLogger(__name__)


class GanGen3Driver(GanGen2Driver):
    """
    GAN356 i Carry 2
    """
    service_uid = GAN_GEN3_SERVICE
    state_characteristic_uid = GAN_GEN3_STATE_CHARACTERISTIC
    command_characteristic_uid = GAN_GEN3_COMMAND_CHARACTERISTIC

    serial = -1
    last_serial = -1
    last_local_timestamp = None
    move_buffer = []

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

    async def request_move_history(self, serial, count):
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

        logger.debug('Sending : REQUEST_HISTORY')

        await self.client.write_gatt_char(
            self.command_characteristic_uid,
            self.cypher.encrypt(bytes(msg)),
        )

    async def evict_move_buffer(self):
        evicted_events = []

        while len(self.move_buffer) > 0:
            buffer_head = self.move_buffer[0]
            diff = 1 if self.last_serial == -1 else (
                buffer_head['serial'] - self.last_serial) & 0xFF
            if diff > 1:
                await self.request_move_history(buffer_head['serial'], diff)
                break

            evicted_events.append(self.move_buffer.pop(0))
            self.last_serial = buffer_head['serial']

        if len(self.move_buffer) > 16:
            self.client.disconnect()

        return evicted_events

    def is_serial_in_range(self, start, end, serial,
                           closed_start=False, closed_end=False):
        return (
            ((end - start) & 0xFF) >= ((serial - start) & 0xFF)
            and (closed_start or ((start - serial) & 0xFF) > 0)
            and (closed_end or ((end - serial) & 0xFF) > 0)
        )

    def inject_missed_move_to_buffer(self, move):
        if len(self.move_buffer) > 0:
            buffer_head = self.move_buffer[0]

            if any(e['event'] == 'move' and e['serial'] == move['serial']
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
                False, True,
        ):
                self.move_buffer.insert(0, move)

    async def check_if_move_missed(self):
        diff = (self.serial - self.last_serial) & 0xFF

        if diff > 0 and self.serial != 0:
            buffer_head = self.move_buffer[0] if self.move_buffer else None
            start_serial = buffer_head['serial'] if buffer_head else (
                self.serial + 1
            ) & 0xFF
            await self.request_move_history(start_serial, diff + 1)

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
                self.move_buffer.append(
                    {
                        'event': 'move',
                        'clock': clock,
                        'timestamp': timestamp,
                        'serial': serial,
                        'local_timestamp': timestamp,
                        'cube_timestamp': cube_timestamp,
                        'face': face,
                        'direction': direction,
                        'move': move.strip(),
                    },
                )
            self.add_event(events, await self.evict_move_buffer())

        elif event == 0x02:  # Facelets
            serial = msg.get_bit_word(24, 16, little_endian=True)
            self.serial = serial

            # Also check and recovery missed moves
            # using periodic facelets event sent by cube
            if self.last_serial != 1:
                # Debounce the facelet event if there are active cube moves
                if (
                        self.last_local_timestamp is not None
                        and (
                            timestamp - self.last_local_timestamp
                        ).total_seconds() > 0.5
                ):
                    await self.check_if_move_missed()

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

                if face >= 0:
                    move = 'URFDLB'[face] + " '"[direction]

                    self.inject_missed_move_to_buffer(
                        {
                            'event': 'move',
                            'clock': clock,
                            'timestamp': timestamp,
                            'serial': (start_serial - i) & 0xFF,
                            # Missed and recovered events
                            # has no meaningful local timestamps
                            'local_timestamp': None,
                            # Cube hardware timestamp for missed move
                            # you should interpolate using cubeTimestampLinearFit
                            'cube_timestamp': None,
                            'face': face,
                            'direction': direction,
                            'move': move.strip(),
                        },
                    )

            self.add_event(events, await self.evict_move_buffer())

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
