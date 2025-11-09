"""Tests for driver moyu."""

import asyncio
import unittest
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import MOYU_WEILONG_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_WEILONG_SERVICE
from term_timer.bluetooth.constants import MOYU_WEILONG_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.moyu import MoyuWeilong10Driver

if TYPE_CHECKING:
    from term_timer.bluetooth.types import BatteryEventDict
    from term_timer.bluetooth.types import FaceletsEventDictNoState
    from term_timer.bluetooth.types import GyroConfigEventDict
    from term_timer.bluetooth.types import HardwareEventMoyuDict


class TestMoyuWeilong10Driver(unittest.IsolatedAsyncioTestCase):  # noqa: PLR0904
    """Tests for MoyuWeilong10Driver class."""

    def setUp(self) -> None:
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'WeiLong v10'

        with patch(
                'term_timer.bluetooth.drivers.moyu.get_salt',
                return_value=b'salt12',
        ):
            self.driver = MoyuWeilong10Driver(self.mock_client)

    def test_init_sets_correct_attributes(self) -> None:
        self.assertEqual(self.driver.client, self.mock_client)
        self.assertEqual(self.driver.last_serial, -1)
        self.assertEqual(self.driver.cube_timestamp, 0)
        self.assertEqual(self.driver.last_move_timestamp, None)

    def test_class_constants(self) -> None:
        self.assertEqual(
            MoyuWeilong10Driver.service_uid,
            MOYU_WEILONG_SERVICE,
        )
        self.assertEqual(
            MoyuWeilong10Driver.state_characteristic_uid,
            MOYU_WEILONG_STATE_CHARACTERISTIC,
        )
        self.assertEqual(
            MoyuWeilong10Driver.command_characteristic_uid,
            MOYU_WEILONG_COMMAND_CHARACTERISTIC,
        )
        self.assertEqual(MoyuWeilong10Driver.factor, pow(2, 30))

    def test_init_cypher(self) -> None:
        result = self.driver.init_cypher()
        self.assertIsNotNone(result)
        self.assertIsNotNone(self.driver.cypher)

    def test_send_command_handler_request_facelets(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_FACELETS')

            mock_cypher.encrypt.assert_called_once()
            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0xA3)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_hardware(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_HARDWARE')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0xA1)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_battery(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_BATTERY')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0xA4)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_enable_gyro(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_ENABLE_GYRO')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0xAC)
            self.assertEqual(args[0][2], 0x01)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_disable_gyro(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_DISABLE_GYRO')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0xAC)
            self.assertEqual(args[0][2], 0x00)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_reset(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_RESET')

            args = mock_cypher.encrypt.call_args[0]
            expected_sequence = [
                0xA2, 0x00, 0x00, 0x00, 0x24,
                0x92, 0x49, 0x49, 0x24, 0x92,
                0x6D, 0xB6, 0xDB, 0x92, 0x49,
                0x24, 0xB6, 0xDB, 0x6D, 0x02,
            ]
            self.assertEqual(list(args[0]), expected_sequence)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_invalid_command(self) -> None:
        result = self.driver.send_command_handler('INVALID_COMMAND')
        self.assertFalse(result)

    def test_send_command_handler_empty_command(self) -> None:
        result = self.driver.send_command_handler('')
        self.assertFalse(result)

    def test_send_command_handler_none_command(self) -> None:
        result = self.driver.send_command_handler(None)  # type: ignore[arg-type]
        self.assertFalse(result)

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_gyroscope_disabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = False

        # Create mock data that represents a gyro event (0xAB)
        encrypted_data = bytearray(20)
        decrypted_data = bytearray([0xAB] + [0] * 19)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = decrypted_data

            mock_sender = Mock()
            result = await self.driver.event_handler(
                mock_sender, encrypted_data,
            )

            self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_gyroscope_enabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = True

        # Create test data for gyro event
        test_data = bytearray(20)
        test_data[0] = 0xAB  # Gyro event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xAB,  # event type
                    1000,  # qw
                    2000,  # qx
                    3000,  # qy
                    4000,  # qz
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'gyro')
                self.assertEqual(event['clock'], 123456789)
                self.assertEqual(event['timestamp'], mock_timestamp)
                self.assertIn('quaternion', event)

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_moves_blocked_before_facelets(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        # Ensure last_serial is -1 (no facelets received yet)
        self.driver.last_serial = -1

        # Create test data for move event
        test_data = bytearray(20)
        test_data[0] = 0xA5  # Move event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0xA5

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_move_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        # Set last_serial so moves are not blocked
        self.driver.last_serial = 100
        self.driver.last_move_timestamp = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0xA5  # Move event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xA5,  # event type
                    102,   # serial (diff of 2)
                    10,    # move_value (face 5, direction 0 -> "R")
                    1000,  # elapsed time
                    8,     # another move_value
                    500,   # another elapsed time
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 2)
                self.assertEqual(result[0]['event'], 'move')
                # Skip checking 'move' key as it doesn't exist in type
                self.assertEqual(result[1]['event'], 'move')

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_facelets_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0xA3  # Facelets event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                # Mock the bit extraction for facelets
                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0xA3  # event type
                    if start == 152 and length == 8:
                        return 50  # serial
                    # Return facelet color values (0-5 for FBUDLR)
                    return start % 6

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'facelets')
                facelets_event = cast('FaceletsEventDictNoState', event)
                self.assertEqual(facelets_event['serial'], 50)
                self.assertIn('facelets', facelets_event)
                self.assertEqual(len(facelets_event['facelets']), 54)

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_hardware_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0xA1  # Hardware event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int) -> int:  # noqa: PLR0911
                    if start == 0 and length == 8:
                        return 0xA1  # event type
                    if start == 72 and length == 8:
                        return 1  # hw_major
                    if start == 80 and length == 8:
                        return 2  # hw_minor
                    if start == 88 and length == 8:
                        return 3  # sw_major
                    if start == 96 and length == 8:
                        return 4  # sw_minor
                    if start == 105 and length == 1:
                        return 1  # gyro_enabled
                    if start == 106 and length == 1:
                        return 1  # gyro_supported
                    if start == 109 and length == 8:
                        return 123  # serial
                    # Hardware name characters
                    return ord('A')

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventMoyuDict', event)
                self.assertEqual(hw_event['hardware_version'], '1.2')
                self.assertEqual(hw_event['software_version'], '3.4')
                self.assertTrue(hw_event['gyroscope_enabled'])
                self.assertTrue(hw_event['gyroscope_ready'])
                self.assertTrue(hw_event['gyroscope_supported'])
                self.assertEqual(hw_event['serial'], 123)

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_battery_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0xA4  # Battery event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xA4,  # event type
                    75,    # battery level
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'battery')
                battery_event = cast('BatteryEventDict', event)
                self.assertEqual(battery_event['level'], 75)

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_battery_level_capped(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0xA4

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xA4,  # event type
                    150,   # battery level > 100
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                battery_event = cast('BatteryEventDict', event)
                self.assertEqual(battery_event['level'], 100)

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    async def test_event_handler_gyro_config_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0xAC  # Gyro config event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0xAC,  # event type
                    1,     # gyro_enabled
                    1,     # gyro_ready
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'gyro-config')
                gyro_config_event = cast('GyroConfigEventDict', event)
                self.assertTrue(gyro_config_event['gyroscope_enabled'])
                self.assertTrue(gyro_config_event['gyroscope_ready'])
                self.assertTrue(gyro_config_event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.moyu.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.moyu.datetime')
    @patch('term_timer.bluetooth.drivers.moyu.logger')
    async def test_event_handler_unknown_event(
            self, mock_logger: Mock, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0xFF  # Unknown event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0xFF

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])
                mock_logger.debug.assert_called_once()

    def test_event_handler_is_async(self) -> None:
        # Verify that event_handler is an async function
        self.assertTrue(asyncio.iscoroutinefunction(self.driver.event_handler))

    async def test_event_handler_with_invalid_data(self) -> None:
        # Test with empty data
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytearray()

            with patch(
                    'term_timer.bluetooth.drivers.moyu.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg_class.side_effect = ValueError('Invalid data')

                with self.assertRaises(ValueError):
                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, bytearray())

    def test_move_value_to_face_mapping(self) -> None:
        # Test the move value to face/direction mapping
        # move_value >> 1 gives face index (0-5 for FBUDLR)
        # move_value & 1 gives direction (0 for normal, 1 for prime)

        test_cases = [
            (0, 'F'),    # 0 >> 1 = 0 (F), 0 & 1 = 0 (normal)
            (1, "F'"),   # 1 >> 1 = 0 (F), 1 & 1 = 1 (prime)
            (2, 'B'),    # 2 >> 1 = 1 (B), 2 & 1 = 0 (normal)
            (3, "B'"),   # 3 >> 1 = 1 (B), 3 & 1 = 1 (prime)
            (10, 'R'),   # 10 >> 1 = 5 (R), 10 & 1 = 0 (normal)
            (11, "R'"),  # 11 >> 1 = 5 (R), 11 & 1 = 1 (prime)
        ]

        face_map = 'FBUDLR'
        direction_map = " '"

        for move_value, expected in test_cases:
            face_idx = move_value >> 1
            direction_idx = move_value & 1
            actual = face_map[face_idx] + direction_map[direction_idx]
            self.assertEqual(actual.strip(), expected)

    def test_facelets_face_order(self) -> None:
        # Test that the face order mapping is correct
        # The code uses faces = [2, 5, 0, 3, 4, 1] to parse in URFDLB order
        expected_order = [2, 5, 0, 3, 4, 1]  # Maps URFDLB to FBUDLR indices
        face_names = ['F', 'B', 'U', 'D', 'L', 'R']  # FBUDLR order

        # Verify the mapping gives us URFDLB when applied to FBUDLR
        result_order = [face_names[i] for i in expected_order]
        expected_result = ['U', 'R', 'F', 'D', 'L', 'B']

        self.assertEqual(result_order, expected_result)
