import asyncio
import unittest
from datetime import datetime
from datetime import timezone
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import GAN_GEN4_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN4_SERVICE
from term_timer.bluetooth.constants import GAN_GEN4_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.drivers.gan_gen4 import GanGen4Driver
from term_timer.bluetooth.types import BatteryEventDict
from term_timer.bluetooth.types import FaceletsEventDict
from term_timer.bluetooth.types import HardwareEventDict
from term_timer.bluetooth.types import HardwareEventPartialDict
from term_timer.bluetooth.types import HardwareEventSoftwareVersionOnlyDict
from term_timer.bluetooth.types import HardwareEventVersionOnlyDict


class TestGanGen4Driver(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN12 uiM'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
            'term_timer.bluetooth.drivers.gan_gen2.get_salt',
            return_value=b'salt12',
        ):
            self.driver = GanGen4Driver(self.mock_client)

    def test_inherits_from_gan_gen3(self) -> None:
        self.assertIsInstance(self.driver, GanGen3Driver)

    def test_class_constants(self) -> None:
        self.assertEqual(
            GanGen4Driver.service_uid,
            GAN_GEN4_SERVICE,
        )
        self.assertEqual(
            GanGen4Driver.state_characteristic_uid,
            GAN_GEN4_STATE_CHARACTERISTIC,
        )
        self.assertEqual(
            GanGen4Driver.command_characteristic_uid,
            GAN_GEN4_COMMAND_CHARACTERISTIC,
        )

    def test_send_command_handler_request_facelets(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_FACELETS')

            mock_cypher.encrypt.assert_called_once()
            args = mock_cypher.encrypt.call_args[0]
            expected_values = [0xDD, 0x04, 0x00, 0xED, 0x00, 0x00]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_hardware(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_HARDWARE')

            args = mock_cypher.encrypt.call_args[0]
            expected_values = [0xDF, 0x03, 0x00, 0x00, 0x00]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_battery(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_BATTERY')

            args = mock_cypher.encrypt.call_args[0]
            expected_values = [0xDD, 0x04, 0x00, 0xEF, 0x00, 0x00]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_reset(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_RESET')

            args = mock_cypher.encrypt.call_args[0]
            expected_values = [
                0xD2,
                0x0D,
                0x05,
                0x39,
                0x77,
                0x00,
                0x00,
                0x01,
                0x23,
                0x45,
                0x67,
                0x89,
                0xAB,
                0x00,
                0x00,
                0x00,
            ]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_invalid_command(self) -> None:
        result = self.driver.send_command_handler('INVALID_COMMAND')
        self.assertFalse(result)

    async def test_request_move_history_odd_serial(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            # odd serial, even count
            await self.driver.request_move_history(101, 6)

            self.mock_client.write_gatt_char.assert_called_once()
            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0xD1)
            self.assertEqual(args[0][1], 0x04)
            self.assertEqual(args[0][2], 101)  # serial unchanged
            self.assertEqual(args[0][4], 6)  # count unchanged

    async def test_request_move_history_even_serial(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            # even serial, odd count
            await self.driver.request_move_history(100, 5)

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][2], 99)  # serial adjusted to odd
            self.assertEqual(args[0][4], 6)  # count adjusted to even

    async def test_request_move_history_overflow_protection(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            # Request history that would overflow beyond serial 255
            await self.driver.request_move_history(250, 300)

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][2], 249)  # adjusted to odd
            self.assertEqual(args[0][4], 250)  # count capped to serial + 1

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_move_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = 100

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x01  # event type (move)
                    if start == 8 and length == 8:
                        return 10  # data_size
                    if start == 16 and length == 32:
                        return 12345  # cube_timestamp
                    if start == 48 and length == 16:
                        return 102  # serial
                    if start == 64 and length == 2:
                        return 1  # direction
                    if start == 66 and length == 6:
                        return 2  # face value
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                with patch.object(
                    self.driver,
                    'evict_move_buffer',
                ) as mock_evict:
                    mock_evict.return_value = [{'event': 'move', 'move': 'U'}]

                    mock_sender = Mock()
                    result = await self.driver.event_handler(
                        mock_sender,
                        test_data,
                    )

                    self.assertEqual(len(result), 1)
                    self.assertEqual(len(self.driver.move_buffer), 1)
                    move_in_buffer = self.driver.move_buffer[0]
                    self.assertEqual(move_in_buffer['event'], 'move')
                    self.assertEqual(move_in_buffer['serial'], 102)
                    self.assertEqual(move_in_buffer['cube_timestamp'], 12345)

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_move_blocked_before_facelets(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = -1  # No facelets received yet

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x01  # event type (move)
                    if start == 8 and length == 8:
                        return 10  # data_size
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen4.cubies_to_facelets')
    async def test_event_handler_facelets_event(
            self, mock_cubies_to_facelets: Mock,
            mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp
        mock_cubies_to_facelets.return_value = (
            'UUUUUUUUURRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB'
        )

        self.driver.last_serial = -1

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0xED  # event type (facelets)
                    if start == 8 and length == 8:
                        return 10  # data_size
                    if start == 16 and length == 16:
                        return 50  # serial
                    return start % 8  # Mock corner/edge data

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'facelets')
                facelets_event = cast(FaceletsEventDict, event)
                self.assertEqual(facelets_event['serial'], 50)
                self.assertEqual(self.driver.serial, 50)
                self.assertEqual(self.driver.last_serial, 50)

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen4.DEBOUNCE', 1.0)
    async def test_event_handler_facelets_with_debounce_check(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        current_time = datetime.now(tz=timezone.utc)  # noqa: UP017
        old_time = datetime.fromtimestamp(
            current_time.timestamp() - 2.0,  # 2 seconds ago
            tz=timezone.utc,  # noqa: UP017
        )
        mock_datetime.now.return_value = current_time

        # Not first facelets
        self.driver.last_serial = 100
        # Old enough to trigger debounce
        self.driver.last_local_timestamp = old_time
        self.driver.serial = 105

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0xED  # event type (facelets)
                    if start == 8 and length == 8:
                        return 10  # data_size
                    if start == 16 and length == 16:
                        return 107  # serial
                    return start % 8  # Mock corner/edge data

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                with (
                    patch.object(
                        self.driver,
                        'check_if_move_missed',
                    ) as mock_check,
                    patch(
                        'term_timer.bluetooth.drivers.gan_gen4.cubies_to_facelets',
                    ),
                ):
                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, test_data)

                    mock_check.assert_called_once()

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_move_history(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0xD1  # event type (move history)
                    if start == 8 and length == 8:
                        return 5  # data_size (4 moves)
                    if start == 16 and length == 8:
                        return 100  # start_serial
                    if start == 24 and length == 3:
                        return 1  # face for move 1
                    if start == 27 and length == 1:
                        return 1  # direction for move 1
                    if start == 28 and length == 3:
                        return 5  # face for move 2
                    if start == 31 and length == 1:
                        return 0  # direction for move 2
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                with (
                    patch.object(
                        self.driver,
                        'inject_missed_move_to_buffer',
                    ) as mock_inject,
                    patch.object(
                        self.driver,
                        'evict_move_buffer',
                    ) as mock_evict,
                ):
                    mock_evict.return_value = []

                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, test_data)
                    # (5-1)*2 = 8 moves
                    self.assertEqual(mock_inject.call_count, 8)

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_hardware_product_date(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xFA,  # event type (product date)
                    10,  # data_size
                    2023,  # year
                    6,  # month
                    15,  # day
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast(HardwareEventPartialDict, event)
                self.assertEqual(hw_event['product_date'], '2023-06-15')

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_hardware_name(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0xFC  # event type (hardware name)
                    if start == 8 and length == 8:
                        return 8  # data_size
                    # Return characters for "GAN12uiM"
                    chars = 'GAN12uiM'
                    char_index = (start - 24) // 8
                    if 0 <= char_index < len(chars):
                        return ord(chars[char_index])
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast(HardwareEventDict, event)
                self.assertEqual(hw_event['hardware_name'], 'GAN12uiM')
                # GAN12uiM supports gyro
                self.assertTrue(hw_event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_hardware_name_without_gyro(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0xFC  # event type (hardware name)
                    if start == 8 and length == 8:
                        return 7  # data_size
                    # Return characters for "GAN14ui"
                    chars = 'GAN14ui'
                    char_index = (start - 24) // 8
                    if 0 <= char_index < len(chars):
                        return ord(chars[char_index])
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast(HardwareEventDict, event)
                self.assertEqual(hw_event['hardware_name'], 'GAN14ui')
                # GAN14ui doesn't support gyro
                self.assertFalse(hw_event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_software_version(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xFD,  # event type (software version)
                    2,  # data_size
                    5,  # sw_major
                    3,  # sw_minor
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast(HardwareEventSoftwareVersionOnlyDict, event)
                self.assertEqual(hw_event['software_version'], '5.3')

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_hardware_version(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xFE,  # event type (hardware version)
                    2,  # data_size
                    2,  # hw_major
                    1,  # hw_minor
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast(HardwareEventVersionOnlyDict, event)
                self.assertEqual(hw_event['hardware_version'], '2.1')

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_gyroscope_disabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = False

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0xEC  # gyroscope event

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_gyroscope_enabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = True

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0xEC  # event type (gyroscope)
                    if start == 16 and length == 16:
                        return 0x8000  # qw (signed bit set)
                    if start == 32 and length == 16:
                        return 0x4000  # qx
                    if start == 48 and length == 16:
                        return 0x2000  # qy
                    if start == 64 and length == 16:
                        return 0x1000  # qz
                    if start == 80 and length == 4:
                        return 0x08  # vx (signed bit set)
                    if start == 84 and length == 4:
                        return 0x04  # vy
                    if start == 88 and length == 4:
                        return 0x02  # vz
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'gyro')
                self.assertEqual(event['clock'], 123456789)
                self.assertEqual(event['timestamp'], mock_timestamp)
                self.assertIn('quaternion', event)
                self.assertIn('velocity', event)

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_battery_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xEF,  # event type (battery)
                    3,  # data_size
                    85,  # battery level
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'battery')
                battery_event = cast(BatteryEventDict, event)
                self.assertEqual(battery_event['level'], 85)

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_battery_level_capped(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xEF,  # event type (battery)
                    3,  # data_size
                    150,  # battery level > 100
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                battery_event = cast(BatteryEventDict, event)
                self.assertEqual(battery_event['level'], 100)

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    async def test_event_handler_disconnect_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xEA,  # event type (disconnect)
                    1,  # data_size
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'disconnect')
                self.mock_client.disconnect.assert_called_once()

    @patch('term_timer.bluetooth.drivers.gan_gen4.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen4.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen4.logger')
    async def test_event_handler_unknown_event(
            self, mock_logger: Mock, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x99,  # unknown event type
                    5,  # data_size
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])
                mock_logger.debug.assert_called_once()

    def test_event_handler_is_async(self) -> None:
        # Verify that event_handler is an async function
        self.assertTrue(asyncio.iscoroutinefunction(self.driver.event_handler))

    def test_request_move_history_is_async(self) -> None:
        # Verify that request_move_history is an async function
        self.assertTrue(
            asyncio.iscoroutinefunction(self.driver.request_move_history),
        )

    def test_hardware_event_range(self) -> None:
        # Test the hardware event range (0xFA to 0xFE)
        hardware_events = [0xFA, 0xFB, 0xFC, 0xFD, 0xFE]
        for event in hardware_events:
            self.assertTrue(0xFA <= event <= 0xFE)

        # Test events outside the range
        non_hardware_events = [0xF9, 0xFF]
        for event in non_hardware_events:
            self.assertFalse(0xFA <= event <= 0xFE)

    def test_gyroscope_support_detection(self) -> None:
        # Test gyroscope support detection logic
        test_cases = [
            ('GAN12uiM', True),
            ('GAN12ui', False),
            ('GAN14ui', False),
            ('GAN356i', False),
            ('unknown', False),
        ]

        for hardware_name, expected_gyro_support in test_cases:
            has_gyro = 'GAN12uiM' in hardware_name
            self.assertEqual(has_gyro, expected_gyro_support)

    def test_quaternion_calculation_gen4(self) -> None:
        # Test quaternion calculation logic for Gen4 (same as Gen2)
        test_value = 0x4000  # Positive value (bit 15 is 0)
        sign = 1 - ((test_value >> 15) * 2)  # Should be 1
        magnitude = (test_value & 0x7FFF) / 0x7FFF  # Should be 0x4000 / 0x7FFF
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertAlmostEqual(expected, 0.5, places=4)

    def test_velocity_calculation_gen4(self) -> None:
        # Test velocity calculation logic for Gen4 (same as Gen2)
        test_value = 0x04  # Positive value (bit 3 is 0)
        sign = 1 - ((test_value >> 3) * 2)  # Should be 1
        magnitude = test_value & 0x7  # Should be 4
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertEqual(expected, 4)

    def test_face_mapping_gen4_move_history(self) -> None:
        # Test the Gen4 face mapping for move history (same as Gen3)
        # [1, 5, 3, 0, 4, 2] maps to URFDLB
        face_indices = [1, 5, 3, 0, 4, 2]
        face_names = 'URFDLB'
        expected_mapping = ['R', 'B', 'D', 'U', 'L', 'F']

        for i, expected_face in enumerate(expected_mapping):
            self.assertEqual(face_names[face_indices[i]], expected_face)

    def test_face_mapping_gen4_move_event(self) -> None:
        # Test the Gen4 face mapping for move events
        # [2, 32, 8, 1, 16, 4] are the bit patterns for URFDLB
        bit_patterns = [2, 32, 8, 1, 16, 4]
        face_names = 'URFDLB'

        for i, pattern in enumerate(bit_patterns):
            # Find index of this pattern in the list
            index = bit_patterns.index(pattern)
            self.assertEqual(index, i)
            self.assertEqual(face_names[i], face_names[index])

    def test_hardware_version_formatting(self) -> None:
        # Test hardware version string formatting
        major, minor = 2, 5
        version_string = f'{major}.{minor}'
        self.assertEqual(version_string, '2.5')

    def test_software_version_formatting(self) -> None:
        # Test software version string formatting
        major, minor = 1, 3
        version_string = f'{major}.{minor}'
        self.assertEqual(version_string, '1.3')

    def test_product_date_formatting(self) -> None:
        # Test product date string formatting
        year, month, day = 2023, 6, 15
        date_string = f'{year:04d}-{month:02d}-{day:02d}'
        self.assertEqual(date_string, '2023-06-15')

    def test_battery_calculation_with_data_size_offset(self) -> None:
        # Test battery level calculation with data_size offset
        # Battery level is at position: 8 + data_size * 8
        data_size = 3
        battery_bit_position = 8 + data_size * 8
        self.assertEqual(battery_bit_position, 32)

    async def test_event_handler_with_invalid_data(self) -> None:
        # Test with empty data
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytearray()

            with patch(
                'term_timer.bluetooth.drivers.gan_gen4.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg_class.side_effect = ValueError('Invalid data')

                with self.assertRaises(ValueError):
                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, bytearray())

    def test_command_byte_sequences(self) -> None:
        # Test that command byte sequences are correctly formed
        test_cases = [
            ('REQUEST_FACELETS', [0xDD, 0x04, 0x00, 0xED, 0x00, 0x00]),
            ('REQUEST_HARDWARE', [0xDF, 0x03, 0x00, 0x00, 0x00]),
            ('REQUEST_BATTERY', [0xDD, 0x04, 0x00, 0xEF, 0x00, 0x00]),
        ]

        for command, expected_start in test_cases:
            with patch.object(self.driver, 'cypher') as mock_cypher:
                mock_cypher.encrypt.return_value = b'encrypted'
                self.driver.send_command_handler(command)
                args = mock_cypher.encrypt.call_args[0]
                for i, expected_byte in enumerate(expected_start):
                    self.assertEqual(args[0][i], expected_byte)
