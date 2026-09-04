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
from term_timer.bluetooth.annotations import GyroConfigEventDict
from term_timer.bluetooth.annotations import GyroEventDict
from term_timer.bluetooth.annotations import HardwareEventBuildTimeOnlyDict
from term_timer.bluetooth.annotations import HardwareEventMacOnlyDict
from term_timer.bluetooth.annotations import HardwareEventNameOnlyDict
from term_timer.bluetooth.annotations import HardwareEventPartialDict
from term_timer.bluetooth.annotations import HardwareEventRestartOnlyDict
from term_timer.bluetooth.annotations import (
    HardwareEventSoftwareVersionOnlyDict,
)
from term_timer.bluetooth.annotations import HardwareEventVersionOnlyDict
from term_timer.bluetooth.annotations import ResetEventDict
from term_timer.bluetooth.constants import GAN_GEN4_COLOR_CHANNELS
from term_timer.bluetooth.constants import GAN_GEN4_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN4_ENGINE_ECO
from term_timer.bluetooth.constants import GAN_GEN4_ENGINE_PERF
from term_timer.bluetooth.constants import GAN_GEN4_SERVICE
from term_timer.bluetooth.constants import GAN_GEN4_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.message import GanProtocolMessage

logger = logging.getLogger(__name__)


# PLR0904 : V3 declares more opcodes than the default limit allows
# public methods, and the dispatch table gives each one a handler.
class GanGen4Driver(GanGen3Driver):  # noqa: PLR0904
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
        # The six feeds CubeStation 6.6 appended to V3. Read only :
        # they publish nothing and, above all, the driver never writes
        # the command 21 that would turn the colour sensor on.
        0x11: 'handle_color_sensor_config',
        0x12: 'handle_color_sensor_sample',
        0x13: 'handle_raw_face_angle',
        0x14: 'handle_raw_face_angle_pair',
        0x1A: 'handle_timed_turn',
        0x1B: 'handle_timed_turn_packed',
        0xD1: 'handle_move_history',
        0xD2: 'handle_reset',
        0xD3: 'handle_restore',
        0xD4: 'handle_gyroscope_config',
        0xDC: 'handle_account_binding',
        0xEA: 'handle_disconnect',
        0xEC: 'handle_gyroscope',
        0xED: 'handle_facelets',
        0xEE: 'handle_face_rotation',
        0xEF: 'handle_battery',
        0xF0: 'handle_exception_log',
        0xF5: 'handle_build_time',
        0xF6: 'handle_restart_reason',
        0xFA: 'handle_product_date',
        0xFC: 'handle_hardware_name',
        0xFD: 'handle_software_version',
        0xFE: 'handle_hardware_version',
        0xFF: 'handle_mac_address',
    }

    @property
    def gyroscope_configurable(self) -> bool:
        """
        Tell whether the cube accepts the 0xD4 engine configuration.

        SendEngineConfig, the only caller of the command, is guarded in
        CubeStation by deviceData_Cn[model].lowBattery, and the GAN i4
        is the single row of the thirty-two carrying that flag. This is
        a precaution rather than a constraint of the protocol : it goes
        away the day a log shows another model answering 0xD4.

        Returns:
            True on a GAN i4, False on every other Gen4 model.

        """
        name = self.client.name or ''

        return name.upper().startswith('GANI4_')

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
        elif command == 'REQUEST_RESTORE':
            values = [0xD3, 0x01, 0x01]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_ENABLE_GYRO':
            if not self.gyroscope_configurable:
                return False
            values = [0xD4, 0x01, GAN_GEN4_ENGINE_PERF]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_DISABLE_GYRO':
            if not self.gyroscope_configurable:
                return False
            values = [0xD4, 0x01, GAN_GEN4_ENGINE_ECO]
            for i, val in enumerate(values):
                msg[i] = val
        elif command == 'REQUEST_EXCEPTION_LOG':
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
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the MAC address of the cube.

        Seven bytes are read, not six : `bleProtoId 255` declares
        `macAddress` with `elementCount: 7`. An oddity of GAN, not a
        slip of the driver — do not shorten the loop to a MAC length.
        The seventh is padding on the GAN i4, whose six first bytes are
        its BLE address to the byte, measured the 2026-09-03.

        The published address stops at the last byte carrying a value,
        as the `0xFE` does with its own trailing null : a cube filling
        the seventh says so on screen instead of saying it to a log
        file, and one that does not renders a plain MAC address.

        Returns:
            The partial hardware event carrying the address.

        """
        octets = [
            msg.get_bit_word(24 + i * 8, 8)
            for i in range(7)
        ]

        logger.debug(
            'MAC Address: %s',
            ':'.join(f'{octet:02X}' for octet in octets),
        )

        while len(octets) > 6 and not octets[-1]:
            octets.pop()

        mac_address_payload: HardwareEventMacOnlyDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'mac_address': ':'.join(f'{octet:02X}' for octet in octets),
        }

        return [mac_address_payload]

    async def handle_hardware_version(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the hardware version of the cube.

        The `0xFE` declares its `deviceVersion` on a single field of
        sixteen bits, where the `0xFD` next door declares two nibbles
        joined by a dot. GAN encodes its versions in nibbles — the
        `0xFD` of the GAN i4 spells `5.3` as `0x53` — so the first byte
        is read that way here too, and the second one has never been
        seen carrying anything : `0x00` on the GAN i4, measured the
        2026-09-03.

        It is appended to the rendering rather than dropped the day it
        stops being null. A cube that never fills it renders exactly
        what it rendered before, and a cube that fills it says so on
        screen instead of saying it to a log file nobody reads.

        Returns:
            The partial hardware event carrying the version.

        """
        hw_major = msg.get_bit_word(24, 4)
        hw_minor = msg.get_bit_word(28, 4)
        hw_extra = msg.get_bit_word(32, 8)

        logger.debug(
            'Hardware version field: 0x%04X, bytes 0x%02X 0x%02X',
            msg.get_bit_word(24, 16, little_endian=True),
            msg.get_bit_word(24, 8),
            hw_extra,
        )

        hardware_version = f'{ hw_major }.{ hw_minor }'

        if hw_extra:
            hardware_version += f'.{ hw_extra }'

        hw_version_payload: HardwareEventVersionOnlyDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'hardware_version': hardware_version,
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
            # Every proto 3 row of deviceData_Cn declares a gyroscope
            # but the two GANicE ones, so a blacklist of two replaces
            # the whitelist of one. Matched case-insensitively : the
            # case of a GAN name is not authoritative, the application
            # itself lowercases every one of them before comparing.
            'gyroscope_supported': not hardware_name.upper().startswith(
                'GANICE',
            ),
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
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode why the cube restarted.

        The key is the one V2 already publishes from the same field of
        its own identity message, so the two generations answer the
        same question with the same name. The width differs — sixteen
        bits here against eight there — and the value is published raw
        rather than judged, as the `result` of a reset is.

        Returns:
            The partial hardware event carrying the reason.

        """
        restart_reason = msg.get_bit_word(24, 16, little_endian=True)

        logger.debug('Restart reason: %s', restart_reason)

        restart_payload: HardwareEventRestartOnlyDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'restart_no_power': restart_reason,
        }

        return [restart_payload]

    async def handle_build_time(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode when the firmware of the cube was built.

        Returns:
            The partial hardware event carrying the build time.

        """
        build_time = self.format_build_time(msg, 24)

        logger.debug('Build time: %s', build_time)

        build_time_payload: HardwareEventBuildTimeOnlyDict = {
            'event': 'hardware',
            'clock': clock,
            'timestamp': timestamp,
            'build_time': build_time,
        }

        return [build_time_payload]

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

    async def handle_restore(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the answer to a cube restore request.

        Journaled and not published, as the account binding answer next
        door is : `REQUEST_RESTORE` has no caller outside this driver,
        so a `result` arriving anyway is an incident rather than a
        datum of the cube. The handler exists so that it is named in
        the journal instead of counted as an unknown opcode.

        Returns:
            Nothing, the result is journaled only.

        """
        restore_result = msg.get_bit_word(16, 8)

        logger.debug('Restore result: %s', restore_result)

        return []

    async def handle_gyroscope_config(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:
        """
        Decode the state of the gyroscope the cube reports.

        The answer does not echo the mode the command carries : it is
        a flag, 1 for a gyroscope that streams and 0 for one that does
        not, measured on a GAN i4 the 2026-09-03 against the traffic
        of the link itself — `1, 0, 1` for a Perf, Eco, Perf session.
        The two encodings sit on the same opcode and are not the same
        domain, which is what makes reading the answer as a mode so
        easy a mistake.

        The cube also chains this message behind its build time at
        initialization, unasked, so the state is known before any
        command is sent.

        Returns:
            The gyro-config event of the message.

        """
        result = msg.get_bit_word(16, 8)

        logger.debug('Engine config: %s', result)

        gyro_config_payload: GyroConfigEventDict = {
            'event': 'gyro-config',
            'clock': clock,
            'timestamp': timestamp,
            'gyroscope_enabled': bool(result),
            # The cube answered, so it has a gyroscope and it is ready:
            # an observation, where the model table is only a guess.
            'gyroscope_ready': True,
            'gyroscope_supported': True,
        }

        return [gyro_config_payload]

    async def handle_face_rotation(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the face rotation the cube is tracking.

        `bleProtoId 238` is `appProtoId 14`, which the reference names
        Rotation Data : the face being turned, the angle it started at,
        the one it is at now, and whether it sits parallel to a face.
        Nothing gyroscopic — the orientation of the cube in space is the
        `0xEC` next door, and the two were told apart by their fields,
        not by their names.

        No cube has ever been seen sending one : zero occurrence over
        the twenty-seven logs kept the 2026-09-03, the GAN i4 sessions
        of the day included. Publishing it is therefore a question
        without a sample, and it stays journaled until one shows up.

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
            'Face rotation - tag:%s, face:%s->%s, '
            'angles:%s/%s/%s, parallel:%s',
            tag, face_old, face_cur,
            angle_init, angle_last, angle_cur,
            parallel,
        )

        return []

    async def handle_exception_log(  # noqa: PLR6301
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

        logger.debug('Exception log [%s]: %s', index, content)

        return []

    @staticmethod
    def decode_color_channels(msg: GanProtocolMessage,
                              start_bit: int) -> dict[str, int]:
        """
        Read the six raw channels of a colour sensor message.

        The two colour messages differ by their leading byte only — a
        `configStatus` on the `0x11`, an `index` on the `0x12` — and
        carry the same six channels behind it.

        Args:
            msg: The decrypted message holding the channels.
            start_bit: Bit the first channel starts at.

        Returns:
            The channels keyed by colour name, in protocol order.

        """
        return {
            name: msg.get_bit_word(start_bit + index * 8, 8)
            for index, name in enumerate(GAN_GEN4_COLOR_CHANNELS)
        }

    async def handle_color_sensor_config(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the colour sensor answering the high precision command.

        `bleProtoId 17` echoes the `configStatus` byte the command 21
        carries, then the six raw channels. The driver never sends that
        command : `RequestHighPrecision` returns immediately on a `Prod`
        server and is restricted to names containing `16ui`, so a retail
        cube should never emit one of these on its own. Decoding it
        costs a handler and turns an `Unknown event type` line into a
        readable one the day a cube proves otherwise.

        Journaled and not published, as the five feeds next door are :
        the layout is read off the descriptor and is certain, its units
        and its meaning are not, and no cube has been seen sending one.

        Returns:
            Nothing, the channels are journaled only.

        """
        config_status = msg.get_bit_word(16, 8)

        logger.debug(
            'Colour sensor config - status:%s, channels:%s',
            config_status, self.decode_color_channels(msg, 24),
        )

        return []

    async def handle_color_sensor_sample(
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log one indexed sample of the colour sensor.

        `bleProtoId 18` is the `0x11` with an `index` where the other
        has its `configStatus` : the sample of a series rather than the
        answer to a command.

        Returns:
            Nothing, the channels are journaled only.

        """
        index = msg.get_bit_word(16, 8)

        logger.debug(
            'Colour sensor sample - index:%s, channels:%s',
            index, self.decode_color_channels(msg, 24),
        )

        return []

    async def handle_raw_face_angle(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the uncalibrated angle of one face.

        The eight bit counterpart of the sixteen bit angles the `0xEE`
        carries : the same face being turned, read before the firmware
        cooks it. Nothing says what the byte is a fraction of, so it is
        logged as it arrives rather than converted into degrees.

        Returns:
            Nothing, the angle is journaled only.

        """
        index = msg.get_bit_word(16, 8)
        face = msg.get_bit_word(24, 8)
        angle_raw = msg.get_bit_word(32, 8)

        logger.debug(
            'Raw face angle - index:%s, face:%s, angle:%s',
            index, face, angle_raw,
        )

        return []

    async def handle_raw_face_angle_pair(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log the uncalibrated angles of two faces packed together.

        The two face identifiers share a byte, and the descriptor
        declares the B one *before* the A one — so the high nibble is
        the B and the low nibble the A, against the reading order the
        names suggest. Their two angles then come back in the A, B
        order.

        Returns:
            Nothing, the angles are journaled only.

        """
        index = msg.get_bit_word(16, 8)
        face_b = msg.get_bit_word(24, 4)
        face_a = msg.get_bit_word(28, 4)
        angle_raw_a = msg.get_bit_word(32, 8)
        angle_raw_b = msg.get_bit_word(40, 8)

        logger.debug(
            'Raw face angles - index:%s, faces:%s/%s, angles:%s/%s',
            index, face_a, face_b, angle_raw_a, angle_raw_b,
        )

        return []

    async def handle_timed_turn(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log a turn timed on the clock of the cube, long form.

        Both timings are declared `isBigEndia: 1`, alone against a
        descriptor that is little endian everywhere else — the two are
        therefore read big endian, which is what `get_bit_word` does by
        default.

        `bleProtoId 26` shares its `appProtoId 25` with the `0x1B` next
        door, whose layout is incompatible with this one : the two are
        told apart by their bleProtoId, which is exactly what the
        dispatch table keys on.

        Returns:
            Nothing, the timings are journaled only.

        """
        index = msg.get_bit_word(16, 8)
        face = msg.get_bit_word(24, 8)
        start_ms = msg.get_bit_word(32, 32)
        duration_ms = msg.get_bit_word(64, 32)

        logger.debug(
            'Timed turn - index:%s, face:%s, start:%sms, duration:%sms',
            index, face, start_ms, duration_ms,
        )

        return []

    async def handle_timed_turn_packed(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list[EventDict]:  # noqa: ARG002
        """
        Log a turn timed on the clock of the cube, packed form.

        Seven bytes where the `0x1A` takes ten : a face on three bits, a
        validity flag on one, a duration on twelve straddling two bytes,
        the serial of the move and a start time. The `valid` bit is
        declared `isBigEndia: 1`, a flag that means nothing on a single
        bit, and the `startMS` is left little endian where the `0x1A`
        marks its own big — the two forms disagree on the endianness of
        the same field.

        Returns:
            Nothing, the timings are journaled only.

        """
        face = msg.get_bit_word(16, 3)
        valid = msg.get_bit_word(19, 1)
        duration_ms = msg.get_bit_word(20, 12)
        last_step = msg.get_bit_word(32, 8)
        start_ms = msg.get_bit_word(40, 32, little_endian=True)

        logger.debug(
            'Timed turn packed - face:%s, valid:%s, serial:%s, '
            'start:%sms, duration:%sms',
            face, bool(valid), last_step, start_ms, duration_ms,
        )

        return []
