"""
GAN Gen4 Driver.

References :
  - https://github.com/afedotov/gan-web-bluetooth
  - https://github.com/Fantomas42/gan-protocols
"""
import logging
from datetime import datetime
from typing import ClassVar

from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import GyroEventDict
from term_timer.bluetooth.annotations import HardwareEventNameOnlyDict
from term_timer.bluetooth.annotations import HardwareEventPartialDict
from term_timer.bluetooth.annotations import (
    HardwareEventSoftwareVersionOnlyDict,
)
from term_timer.bluetooth.annotations import HardwareEventVersionOnlyDict
from term_timer.bluetooth.annotations import ResetEventDict
from term_timer.bluetooth.constants import GAN_GEN4_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN4_SERVICE
from term_timer.bluetooth.constants import GAN_GEN4_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.message import GanProtocolMessage

logger = logging.getLogger(__name__)


# PLR0904 : V3 declares more opcodes than the default limit allows
# public methods, and the dispatch table gives each one a handler.
class GanGen4Driver(GanGen3Driver):
    """
    GAN12 ui Maglev.
    GAN12 ui FreePlay2.
    GAN12 ui SP.
    GAN14 ui.
    GAN16 ui.
    GAN i3.
    GAN i4.
    GAN i carry 4.
    GAN i carry E.
    """

    service_uid: ClassVar[str] = GAN_GEN4_SERVICE
    state_characteristic_uid: ClassVar[str] = GAN_GEN4_STATE_CHARACTERISTIC
    command_characteristic_uid: ClassVar[str] = GAN_GEN4_COMMAND_CHARACTERISTIC
    # The same sixteen bits as V2, and that is the whole point : the
    # head of V2 opens its notification and not its messages, so both
    # generations lay their payloads out behind the same header, and
    # the move, facelets and history handlers are shared, not copied.
    payload_offset: ClassVar[int] = 16
    chained: ClassVar[bool] = True
    # V3 declares no head byte, its messages start with their
    # bleProtoId, and closes its frames with two bytes of CRC-16.
    head_magic: ClassVar[int | None] = None
    crc_reserve: ClassVar[int] = 2
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {
        0x01: 'handle_move',
        0x02: 'handle_solved',
        0xD1: 'handle_move_history',
        0xD2: 'handle_reset',
        0xD3: 'handle_calibrate',
        0xD4: 'handle_gyroscope_config',
        0xEA: 'handle_disconnect',
        0xEC: 'handle_gyroscope',
        0xED: 'handle_facelets',
        0xEE: 'handle_gyroscope_detail',
        0xEF: 'handle_battery',
        0xF0: 'handle_debug_info',
        0xF5: 'handle_build_time',
        0xF6: 'handle_restart_reason',
        0xFA: 'handle_product_date',
        0xFC: 'handle_hardware_name',
        0xFD: 'handle_software_version',
        0xFE: 'handle_hardware_version',
        0xFF: 'handle_mac_address',
    }

    def send_command_handler(self, command: str) -> bytes | bool:  # noqa: C901, PLR0912
        """
        Build and encrypt command messages for GAN Gen4 cube.

        Returns:
            Encrypted command bytes or False if command is invalid.

        """
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
        elif command == 'REQUEST_CALIBRATE':
            values = [0xD3, 0x01, 0x01]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_ENABLE_GYRO':
            values = [0xD4, 0x01, 0x01]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_DISABLE_GYRO':
            values = [0xD4, 0x01, 0x00]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_DEBUG_INFO':
            values = [0xF0, 0x01, 0x01]
            for i, val in enumerate(values):
                msg[i] = val
        else:
            return False

        return self.cypher.encrypt(msg)

    async def request_move_history(self, serial: int, count: int) -> None:
        """Request move history from cube starting at serial number."""
        msg = bytearray(20)

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
        # Because due to firmware bug the moves beyond the edge
        # will be spoofed with 'D' (just zero bytes).
        count = min(count, serial + 1)

        msg[0] = 0xD1
        msg[1] = 0x04
        msg[2] = serial
        msg[4] = count

        logger.debug('Sending : REQUEST_HISTORY')

        await self.client.write_gatt_char(
            self.command_characteristic_uid,
            self.cypher.encrypt(msg),
        )

    async def handle_mac_address(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the MAC address of the cube.

        Returns:
            Nothing, the address is journaled only.

        """
        mac_address = ''
        for i in range(7):
            if i > 0:
                mac_address += ':'
            mac_address += f'{msg.get_bit_word(24 + i * 8, 8):02X}'

        logger.debug('MAC Address: %s', mac_address)

        return []

    async def handle_hardware_version(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the hardware version of the cube.

        Returns:
            The partial hardware event carrying the version.

        """
        hw_major = msg.get_bit_word(24, 4)
        hw_minor = msg.get_bit_word(28, 4)

        hw_version_payload: HardwareEventVersionOnlyDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'hardware_version': f'{ hw_major }.{ hw_minor }',
        }

        return [hw_version_payload]

    async def handle_software_version(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the software version of the cube.

        Returns:
            The partial hardware event carrying the version.

        """
        sw_major = msg.get_bit_word(24, 4)
        sw_minor = msg.get_bit_word(28, 4)

        sw_version_payload: HardwareEventSoftwareVersionOnlyDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'software_version': f'{ sw_major }.{ sw_minor }',
        }

        return [sw_version_payload]

    async def handle_hardware_name(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the hardware name of the cube.

        Returns:
            The partial hardware event carrying the name.

        """
        data_size = msg.get_bit_word(8, 8)

        # dataLength counts the index byte the name is written after,
        # so the name itself is one byte shorter than the payload.
        hardware_name = ''
        for i in range(data_size - 1):
            hardware_name += chr(msg.get_bit_word(i * 8 + 24, 8))

        hardware_name_payload: HardwareEventNameOnlyDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'hardware_name': hardware_name,
            'gyroscope_supported': 'GAN12uiM' in hardware_name,
        }

        return [hardware_name_payload]

    async def handle_product_date(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the production date of the cube.

        Returns:
            The partial hardware event carrying the date.

        """
        year = msg.get_bit_word(24, 16, little_endian=True)
        month = msg.get_bit_word(40, 8)
        day = msg.get_bit_word(48, 8)

        product_date_payload: HardwareEventPartialDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'product_date': f'{ year:04d}-{ month:02d}-{ day:02d}',
        }

        return [product_date_payload]

    async def handle_restart_reason(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log why the cube restarted.

        Returns:
            Nothing, the reason is journaled only.

        """
        restart_reason = msg.get_bit_word(24, 16, little_endian=True)

        logger.debug('Restart reason: %s', restart_reason)

        return []

    async def handle_build_time(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log when the firmware of the cube was built.

        Returns:
            Nothing, the build time is journaled only.

        """
        logger.debug('Build time: %s', self.format_build_time(msg, 24))

        return []

    async def handle_gyroscope(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the orientation sample of a gyroscope message.

        V3 declares a single sample per message, where V1 declares two.

        Returns:
            The gyroscope event, or nothing when the gyroscope is not
            used.

        """
        if not self.use_gyroscope:
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

        gyro_payload: GyroEventDict = {
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

        return [gyro_payload]

    async def handle_battery(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the battery level of the cube.

        V3 prefixes the level with an index that V2 does not declare.

        Returns:
            The battery event of the message.

        """
        _battery_index = msg.get_bit_word(16, 8)
        battery_level = msg.get_bit_word(24, 8)

        battery_payload: BatteryEventDict = {
            'event': 'battery',
            'clock': clock,
            'timestamp': timestamp,
            'charging_state': 0,
            'level': min(battery_level, 100),
        }

        return [battery_payload]

    async def handle_reset(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Acknowledge that the cube state has been reset.

        `bleProtoId 210` declares its `result` on thirty-two bits where
        V2 declares eight, so the two generations publish the same key
        with two domains. Journalising it would have kept it out of the
        stream, which is where a refused reset has to be seen.

        Returns:
            The reset event of the message.

        """
        reset_payload: ResetEventDict = {
            'event': 'reset',
            'clock': clock,
            'timestamp': timestamp,
            'result': msg.get_bit_word(16, 32, little_endian=True),
        }

        return [reset_payload]

    async def handle_calibrate(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the answer to a calibration request.

        Returns:
            Nothing, the result is journaled only.

        """
        calibrate_result = msg.get_bit_word(16, 8)

        logger.debug('Calibration result: %s', calibrate_result)

        return []

    async def handle_gyroscope_config(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the answer to a gyroscope configuration request.

        Returns:
            Nothing, the result is journaled only.

        """
        gyro_enabled = msg.get_bit_word(16, 8)

        logger.debug('Gyro enabled: %s', bool(gyro_enabled))

        return []

    async def handle_gyroscope_detail(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the detailed face rotation tracking of the cube.

        Returns:
            Nothing, the angles are journaled only.

        """
        tag = msg.get_bit_word(16, 8)
        face_old = msg.get_bit_word(24, 8)
        face_cur = msg.get_bit_word(32, 8)
        angle_init = msg.get_bit_word(40, 16, little_endian=True)
        angle_last = msg.get_bit_word(56, 16, little_endian=True)
        angle_cur = msg.get_bit_word(72, 16, little_endian=True)
        parallel = msg.get_bit_word(88, 8)

        logger.debug(
            'Gyro movement - tag:%s, face:%s->%s, '
            'angles:%s/%s/%s, parallel:%s',
            tag, face_old, face_cur,
            angle_init, angle_last, angle_cur,
            parallel,
        )

        return []

    async def handle_debug_info(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the fault journal the cube keeps about itself.

        Returns:
            Nothing, the content is journaled only.

        """
        data_size = msg.get_bit_word(8, 8)
        index = msg.get_bit_word(16, 8)

        content = ''
        for i in range(min(data_size - 1, 15)):
            content += chr(msg.get_bit_word(24 + i * 8, 8))

        logger.debug('Debug info [%s]: %s', index, content)

        return []
