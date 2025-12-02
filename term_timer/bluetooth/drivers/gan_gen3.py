"""
GAN Gen3 Driver.

References :
  - https://github.com/afedotov/gan-web-bluetooth
  - https://github.com/Fantomas42/gan-protocols
"""
import logging
import time
from datetime import datetime
from datetime import timezone
from typing import ClassVar

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from cubing_algs.facelets import cubies_to_facelets

from term_timer.bluetooth.constants import DEBOUNCE
from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.message import GanProtocolMessage
from term_timer.bluetooth.types import BatteryEventDict
from term_timer.bluetooth.types import DisconnectEventDict
from term_timer.bluetooth.types import EventDict
from term_timer.bluetooth.types import FaceletsEventDict
from term_timer.bluetooth.types import HardwareEventDict
from term_timer.bluetooth.types import MoveEventDict

logger = logging.getLogger(__name__)


class GanGen3Driver(GanGen2Driver):
    """GAN356 i Carry 2."""

    service_uid: ClassVar[str] = GAN_GEN3_SERVICE
    state_characteristic_uid: ClassVar[str] = GAN_GEN3_STATE_CHARACTERISTIC
    command_characteristic_uid: ClassVar[str] = GAN_GEN3_COMMAND_CHARACTERISTIC

    def __init__(self, client: BleakClient,
                 *, use_gyroscope: bool) -> None:
        """
        Initialize the GAN Gen3 driver with move tracking capabilities.

        Sets up serial number tracking, timestamp management, and a FIFO
        buffer for handling move events and detecting missed moves.

        Args:
            client: The BLE client connection to the cube.
            use_gyroscope: Whether the driver should use gyroscope data.

        """
        super().__init__(client, use_gyroscope=use_gyroscope)

        self.serial: int = -1
        self.last_serial: int = -1
        self.last_local_timestamp: datetime | None = None
        self.move_buffer: list[MoveEventDict] = []

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

    async def evict_move_buffer(self) -> list[MoveEventDict]:
        """
        Process and emit move events from the buffer in sequence order.

        Removes move events from the buffer when they can be delivered in the
        correct serial order. If a gap is detected, requests missing history.
        Disconnects if the buffer grows too large (indicating sync issues).

        Returns:
            List of move events that were successfully evicted from the
            buffer and are ready to be emitted.

        """
        evicted_events: list[MoveEventDict] = []

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

        if diff > 0 and self.serial != 0:
            buffer_head = self.move_buffer[0] if self.move_buffer else None
            start_serial = buffer_head['serial'] if buffer_head else (
                self.serial + 1
            ) & 0xFF
            await self.request_move_history(start_serial, diff + 1)

    async def event_handler(  # noqa: C901, PLR0912, PLR0914, PLR0915
            self, sender: BleakGATTCharacteristic,  # noqa: ARG002
            data: bytearray) -> list[EventDict]:
        """
        Process notifications from the cube and decode event messages.

        Decrypts and parses incoming data to handle various event types
        including moves, facelets, move history, hardware info, battery
        status, and disconnection events. Manages move buffering and
        recovery of missed moves.

        Args:
            sender: The GATT characteristic that sent the notification.
            data: The encrypted message data from the cube.

        Returns:
            List of decoded events ready to be emitted to listeners.

        """
        clock = time.perf_counter_ns()
        timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017

        events: list[EventDict] = []

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
            evicted = await self.evict_move_buffer()
            if evicted:
                self.add_event(events, evicted)

        elif event == 0x02:  # Facelets
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
            self.add_event(events, facelets_payload)

        elif event == 0x06:  # Move history
            start_serial = msg.get_bit_word(24, 8)
            count = (data_size - 1) * 2

            for i in range(count):
                direction = msg.get_bit_word(35 + 4 * i, 1)
                face = [1, 5, 3, 0, 4, 2].index(msg.get_bit_word(32 + 4 * i, 3))

                if face >= 0:
                    move = 'URFDLB'[face] + " '"[direction]

                    history_move: MoveEventDict = {
                        'event': 'move',
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

            evicted = await self.evict_move_buffer()
            if evicted:
                self.add_event(events, evicted)

        elif event == 0x07:  # Hardware
            restart_reason = msg.get_bit_word(24, 8)

            hardware_name = ''
            for i in range(5):
                hardware_name += chr(msg.get_bit_word(i * 8 + 32, 8))

            sw_major = msg.get_bit_word(72, 4)
            sw_minor = msg.get_bit_word(76, 4)
            hw_major = msg.get_bit_word(80, 4)
            hw_minor = msg.get_bit_word(84, 4)

            _build_time = msg.get_bit_word(88, 32, little_endian=True)

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
            self.add_event(events, hardware_payload)

        elif event == 0x10:  # Battery
            battery_level = msg.get_bit_word(24, 8)

            battery_payload: BatteryEventDict = {
                'event': 'battery',
                'clock': clock,
                'timestamp': timestamp,
                'charging_state': 0,
                'level': min(battery_level, 100),
            }
            self.add_event(events, battery_payload)

        elif event == 0x11:  # Disconnect
            disconnect_payload: DisconnectEventDict = {
                'event': 'disconnect',
                'clock': clock,
                'timestamp': timestamp,
            }
            self.add_event(events, disconnect_payload)

            await self.client.disconnect()

        else:
            logger.debug(
                'Unknown event type "%s": %s', event, msg,
            )

        return events
