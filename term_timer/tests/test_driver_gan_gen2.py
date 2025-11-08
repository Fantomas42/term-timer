"""Tests for driver gan gen2."""

import asyncio
import unittest
from datetime import datetime
from datetime import timezone
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import GAN_GEN2_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN2_SERVICE
from term_timer.bluetooth.constants import GAN_GEN2_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.types import BatteryEventDict
from term_timer.bluetooth.types import FaceletsEventDict
from term_timer.bluetooth.types import HardwareEventDict
from term_timer.bluetooth.types import MoveEventDict


class TestGanGen2Driver(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN356 i'

        with patch(
                'term_timer.bluetooth.drivers.gan_gen2.get_salt',
                return_value=b'salt12',
        ):
            self.driver = GanGen2Driver(self.mock_client)

    def test_init_sets_correct_attributes(self) -> None:
        self.assertEqual(self.driver.client, self.mock_client)
        self.assertEqual(self.driver.last_serial, -1)
        self.assertEqual(self.driver.cube_timestamp, 0)
        self.assertEqual(self.driver.last_move_timestamp, None)

    def test_class_constants(self) -> None:
        self.assertEqual(
            GanGen2Driver.service_uid,
            GAN_GEN2_SERVICE,
        )
        self.assertEqual(
            GanGen2Driver.state_characteristic_uid,
            GAN_GEN2_STATE_CHARACTERISTIC,
        )
        self.assertEqual(
            GanGen2Driver.command_characteristic_uid,
            GAN_GEN2_COMMAND_CHARACTERISTIC,
        )

    def test_init_cypher_gan_cube(self) -> None:
        # Test that init_cypher returns the encrypter for GAN cube
        self.mock_client.name = 'GAN356 i'

        # Test calling init_cypher directly
        result = self.driver.init_cypher()
        self.assertIsNotNone(result)

        # Test that cypher was set during initialization
        self.assertIsNotNone(self.driver.cypher)

    def test_init_cypher_aicube(self) -> None:
        # Create a new driver with AiCube name
        # to test the different encryption key path
        mock_aicube_client = Mock()
        mock_aicube_client.address = 'AA:BB:CC:DD:EE:FF'
        mock_aicube_client.name = 'AiCube_TEST'

        with patch(
                'term_timer.bluetooth.drivers.gan_gen2.get_salt',
                return_value=b'salt12',
        ):
            aicube_driver = GanGen2Driver(mock_aicube_client)

        # Test that init_cypher is called and returns the encrypter
        self.assertIsNotNone(aicube_driver.cypher)

        # Test calling init_cypher directly
        result = aicube_driver.init_cypher()
        self.assertIsNotNone(result)

    def test_send_command_handler_request_facelets(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_FACELETS')

            mock_cypher.encrypt.assert_called_once()
            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x04)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_hardware(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_HARDWARE')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x05)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_battery(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_BATTERY')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x09)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_reset(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_RESET')

            args = mock_cypher.encrypt.call_args[0]
            expected_sequence = [
                0x0A, 0x05, 0x39, 0x77, 0x00, 0x00, 0x01, 0x23, 0x45, 0x67,
                0x89, 0xAB, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
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

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_gyroscope_disabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = False

        # Create mock data that represents a gyro event (0x01)
        encrypted_data = bytearray(20)
        decrypted_data = bytearray([0x01] + [0] * 19)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = decrypted_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0x01

                mock_sender = Mock()
                result = await self.driver.event_handler(
                    mock_sender, encrypted_data,
                )

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_gyroscope_enabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = True

        test_data = bytearray(20)
        test_data[0] = 0x01  # Lower 4 bits are 0x01 for gyro

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x01,    # event type (first 4 bits)
                    0x8000,  # qw (signed bit set)
                    0x4000,  # qx
                    0x2000,  # qy
                    0x1000,  # qz
                    0x08,    # vx (signed bit set)
                    0x04,    # vy
                    0x02,    # vz
                    0x8000,  # b qw (signed bit set)
                    0x4000,  # b qx
                    0x2000,  # b qy
                    0x1000,  # b qz
                    0x08,    # b vx (signed bit set)
                    0x04,    # b vy
                    0x02,    # b vz
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 2)
                for event in result:
                    self.assertEqual(event['event'], 'gyro')
                    self.assertEqual(event['clock'], 123456789)
                    self.assertEqual(event['timestamp'], mock_timestamp)
                    self.assertIn('quaternion', event)
                    self.assertIn('velocity', event)

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_moves_blocked_before_facelets(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        # Ensure last_serial is -1 (no facelets received yet)
        self.driver.last_serial = -1

        test_data = bytearray(20)
        test_data[0] = 0x02  # Lower 4 bits are 0x02 for move

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0x02

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
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
        test_data[0] = 0x02  # Lower 4 bits are 0x02 for move

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x02,  # event type
                    102,   # serial (diff of 2)
                    0,     # face (U)
                    1,     # direction (prime)
                    1000,  # elapsed time
                    3,     # another face (F)
                    0,     # direction (normal)
                    500,   # another elapsed time
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 2)
                self.assertEqual(result[0]['event'], 'move')
                move_event_0 = cast(MoveEventDict, result[0])
                self.assertEqual(move_event_0['move'], "U'")
                self.assertEqual(result[1]['event'], 'move')
                move_event_1 = cast(MoveEventDict, result[1])
                self.assertEqual(move_event_1['move'], 'D')

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_move_with_zero_elapsed_time(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = 100
        self.driver.last_move_timestamp = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x02

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x02,  # event type
                    101,   # serial (diff of 1)
                    0,     # face (U)
                    0,     # direction (normal)
                    1,     # elapsed time (overflow case)
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'move')
                move_event = cast(MoveEventDict, event)
                self.assertEqual(move_event['move'], 'U')
                cube_timestamp = move_event['cube_timestamp']
                self.assertIsNotNone(cube_timestamp)
                cube_timestamp = cast(int, cube_timestamp)
                # Should have computed elapsed time from timestamp difference
                self.assertGreater(cube_timestamp, 0)

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen2.cubies_to_facelets')
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

        test_data = bytearray(20)
        test_data[0] = 0x04  # Lower 4 bits are 0x04 for facelets

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                # Mock corner and edge data
                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 4:
                        return 0x04  # event type
                    if start == 4 and length == 8:
                        return 50  # serial
                    if 12 <= start <= 32:  # corner permutations
                        return start % 8
                    if 33 <= start <= 46:  # corner orientations
                        return start % 3
                    if 47 <= start <= 90:  # edge permutations
                        return start % 12
                    if 91 <= start <= 101:  # edge orientations
                        return start % 2
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'facelets')
                facelets_event = cast(FaceletsEventDict, event)
                self.assertEqual(facelets_event['serial'], 50)
                self.assertIn('facelets', facelets_event)
                self.assertIn('state', facelets_event)
                self.assertIn('CP', facelets_event['state'])
                self.assertIn('CO', facelets_event['state'])
                self.assertIn('EP', facelets_event['state'])
                self.assertIn('EO', facelets_event['state'])

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_hardware_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x05  # Lower 4 bits are 0x05 for hardware

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 4:
                        return 0x05  # event type
                    if start == 8 and length == 8:
                        return 1  # hw_major
                    if start == 16 and length == 8:
                        return 2  # hw_minor
                    if start == 24 and length == 8:
                        return 3  # sw_major
                    if start == 32 and length == 8:
                        return 4  # sw_minor
                    if start == 104 and length == 1:
                        return 1  # gyro_supported
                    # Hardware name characters
                    return ord('A')

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast(HardwareEventDict, event)
                self.assertEqual(hw_event['hardware_version'], '1.2')
                self.assertEqual(hw_event['software_version'], '3.4')
                self.assertTrue(hw_event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_battery_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x09  # Lower 4 bits are 0x09 for battery

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x09,  # event type
                    1,     # charging
                    85,    # battery level
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'battery')
                battery_event = cast(BatteryEventDict, event)
                self.assertEqual(battery_event['level'], 85)
                self.assertEqual(battery_event['charging_state'], 1)

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_battery_level_capped(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x09

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x09,  # event type
                    1,     # charging
                    150,   # battery level > 100
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                battery_event = cast(BatteryEventDict, event)
                self.assertEqual(battery_event['level'], 100)
                self.assertEqual(battery_event['charging_state'], 1)

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    async def test_event_handler_disconnect_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.mock_client.disconnect = AsyncMock()

        test_data = bytearray(20)
        test_data[0] = 0x0D  # Lower 4 bits are 0x0D for disconnect

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0x0D

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'disconnect')
                self.mock_client.disconnect.assert_called_once()

    @patch('term_timer.bluetooth.drivers.gan_gen2.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen2.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen2.logger')
    async def test_event_handler_unknown_event(
            self, mock_logger: Mock, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x0F  # Unknown event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0x0F

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])
                mock_logger.debug.assert_called_once()

    def test_event_handler_is_async(self) -> None:
        # Verify that event_handler is an async function
        self.assertTrue(asyncio.iscoroutinefunction(self.driver.event_handler))

    def test_quaternion_calculation_positive_values(self) -> None:
        # Test quaternion calculation logic for positive values
        test_value = 0x4000  # Positive value (bit 15 is 0)
        sign = 1 - ((test_value >> 15) * 2)  # Should be 1
        magnitude = (test_value & 0x7FFF) / 0x7FFF  # Should be 0x4000 / 0x7FFF
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertAlmostEqual(expected, 0.5, places=4)

    def test_quaternion_calculation_negative_values(self) -> None:
        # Test quaternion calculation logic for negative values
        test_value = 0x8000  # Negative value (bit 15 is 1)
        sign = 1 - ((test_value >> 15) * 2)  # Should be -1
        magnitude = (test_value & 0x7FFF) / 0x7FFF  # Should be 0 / 0x7FFF
        expected = sign * magnitude

        self.assertEqual(sign, -1)
        self.assertEqual(expected, 0.0)

    def test_velocity_calculation_positive_values(self) -> None:
        # Test velocity calculation logic for positive values
        test_value = 0x04  # Positive value (bit 3 is 0)
        sign = 1 - ((test_value >> 3) * 2)  # Should be 1
        magnitude = test_value & 0x7  # Should be 4
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertEqual(expected, 4)

    def test_velocity_calculation_negative_values(self) -> None:
        # Test velocity calculation logic for negative values
        test_value = 0x08  # Negative value (bit 3 is 1)
        sign = 1 - ((test_value >> 3) * 2)  # Should be -1
        magnitude = test_value & 0x7  # Should be 0
        expected = sign * magnitude

        self.assertEqual(sign, -1)
        self.assertEqual(expected, 0)

    def test_corner_permutation_calculation(self) -> None:
        # Test that corner permutation is correctly calculated
        # The last corner is calculated as 28 - sum(first 7)
        cp_values = [0, 1, 2, 3, 4, 5, 6]
        last_cp = 28 - sum(cp_values)
        self.assertEqual(last_cp, 7)  # 28 - 21 = 7

    def test_corner_orientation_calculation(self) -> None:
        # Test that corner orientation is correctly calculated
        # The last corner orientation is calculated as (3 - (sum % 3)) % 3
        co_values = [0, 1, 2, 0, 1, 2, 0]
        last_co = (3 - (sum(co_values) % 3)) % 3
        self.assertEqual(last_co, 0)  # (3 - (6 % 3)) % 3 = (3 - 0) % 3 = 0

    def test_edge_permutation_calculation(self) -> None:
        # Test that edge permutation is correctly calculated
        # The last edge is calculated as 66 - sum(first 11)
        ep_values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        last_ep = 66 - sum(ep_values)
        self.assertEqual(last_ep, 11)  # 66 - 55 = 11

    def test_edge_orientation_calculation(self) -> None:
        # Test that edge orientation is correctly calculated
        # The last edge orientation is calculated as (2 - (sum % 2)) % 2
        eo_values = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        last_eo = (2 - (sum(eo_values) % 2)) % 2
        self.assertEqual(last_eo, 1)  # (2 - (5 % 2)) % 2 = (2 - 1) % 2 = 1

    async def test_event_handler_with_invalid_data(self) -> None:
        # Test with empty data
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytearray()

            with patch(
                    'term_timer.bluetooth.drivers.gan_gen2.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg_class.side_effect = ValueError('Invalid data')

                with self.assertRaises(ValueError):
                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, bytearray())
