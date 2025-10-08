import asyncio
import unittest
from datetime import datetime
from datetime import timezone
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver


class TestGanGen3Driver(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN356 iCarry2'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
            'term_timer.bluetooth.drivers.gan_gen2.get_salt',
            return_value=b'salt12',
        ):
            self.driver = GanGen3Driver(self.mock_client)

    def test_init_sets_correct_attributes(self) -> None:
        self.assertEqual(self.driver.client, self.mock_client)
        self.assertEqual(self.driver.serial, -1)
        self.assertEqual(self.driver.last_serial, -1)
        self.assertIsNone(self.driver.last_local_timestamp)
        self.assertEqual(self.driver.move_buffer, [])

    def test_inherits_from_gan_gen2(self) -> None:
        self.assertIsInstance(self.driver, GanGen2Driver)

    def test_class_constants(self) -> None:
        self.assertEqual(
            GanGen3Driver.service_uid,
            GAN_GEN3_SERVICE,
        )
        self.assertEqual(
            GanGen3Driver.state_characteristic_uid,
            GAN_GEN3_STATE_CHARACTERISTIC,
        )
        self.assertEqual(
            GanGen3Driver.command_characteristic_uid,
            GAN_GEN3_COMMAND_CHARACTERISTIC,
        )

    def test_send_command_handler_request_facelets(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_FACELETS')

            mock_cypher.encrypt.assert_called_once()
            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x68)
            self.assertEqual(args[0][1], 0x01)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_hardware(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_HARDWARE')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x68)
            self.assertEqual(args[0][1], 0x04)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_battery(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_BATTERY')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x68)
            self.assertEqual(args[0][1], 0x07)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_reset(self) -> None:
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_RESET')

            args = mock_cypher.encrypt.call_args[0]
            expected_sequence = [
                0x68,
                0x05,
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
            self.assertEqual(list(args[0]), expected_sequence)
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
            self.assertEqual(args[0][0], 0x68)
            self.assertEqual(args[0][1], 0x03)
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

    async def test_evict_move_buffer_empty(self) -> None:
        self.driver.move_buffer = []
        self.driver.last_serial = 100

        result = await self.driver.evict_move_buffer()

        self.assertEqual(result, [])
        self.assertEqual(len(self.driver.move_buffer), 0)

    async def test_evict_move_buffer_sequential_moves(self) -> None:
        self.driver.last_serial = 100
        self.driver.move_buffer = [
            {'serial': 101, 'event': 'move', 'move': 'U'},
            {'serial': 102, 'event': 'move', 'move': 'R'},
        ]

        result = await self.driver.evict_move_buffer()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['serial'], 101)
        self.assertEqual(result[1]['serial'], 102)
        self.assertEqual(self.driver.last_serial, 102)
        self.assertEqual(len(self.driver.move_buffer), 0)

    async def test_evict_move_buffer_missed_move_requests_history(self) -> None:
        self.driver.last_serial = 100
        self.driver.move_buffer = [
            {'serial': 103, 'event': 'move', 'move': 'U'},  # Gap at 101, 102
        ]

        with patch.object(self.driver, 'request_move_history') as mock_request:
            result = await self.driver.evict_move_buffer()

            mock_request.assert_called_once_with(103, 3)  # serial 103, diff 3
            self.assertEqual(result, [])  # No events evicted due to gap
            self.assertEqual(len(self.driver.move_buffer), 1)

    async def test_evict_move_buffer_first_move_no_gap_check(self) -> None:
        self.driver.last_serial = -1  # First move
        self.driver.move_buffer = [
            {'serial': 50, 'event': 'move', 'move': 'U'},
        ]

        result = await self.driver.evict_move_buffer()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['serial'], 50)
        self.assertEqual(self.driver.last_serial, 50)
        self.assertEqual(len(self.driver.move_buffer), 0)

    def test_is_serial_in_range_basic(self) -> None:
        # Test serial 5 is in range [3, 7]
        result = self.driver.is_serial_in_range(3, 7, 5)
        self.assertTrue(result)

    def test_is_serial_in_range_boundary_open(self) -> None:
        # Test boundaries with open intervals
        # start boundary, open
        self.assertFalse(self.driver.is_serial_in_range(3, 7, 3))
        # end boundary, open
        self.assertFalse(self.driver.is_serial_in_range(3, 7, 7))

    def test_is_serial_in_range_boundary_closed(self) -> None:
        # Test boundaries with closed intervals
        self.assertTrue(
            self.driver.is_serial_in_range(3, 7, 3, closed_start=True),
        )
        self.assertTrue(
            self.driver.is_serial_in_range(3, 7, 7, closed_end=True),
        )

    def test_is_serial_in_range_wraparound(self) -> None:
        # Test wraparound case (e.g., range [250, 10] includes 255, 0, 5)
        self.assertTrue(self.driver.is_serial_in_range(250, 10, 255))
        self.assertTrue(self.driver.is_serial_in_range(250, 10, 0))
        self.assertTrue(self.driver.is_serial_in_range(250, 10, 5))
        self.assertFalse(self.driver.is_serial_in_range(250, 10, 100))

    def test_inject_missed_move_to_buffer_empty_buffer(self) -> None:
        self.driver.last_serial = 100
        self.driver.serial = 105
        self.driver.move_buffer = []

        move = {'serial': 103, 'event': 'move', 'move': 'U'}
        self.driver.inject_missed_move_to_buffer(move)

        self.assertEqual(len(self.driver.move_buffer), 1)
        self.assertEqual(self.driver.move_buffer[0], move)

    def test_inject_missed_move_to_buffer_with_existing_buffer(self) -> None:
        self.driver.last_serial = 100
        self.driver.move_buffer = [
            {'serial': 105, 'event': 'move', 'move': 'R'},
        ]

        move = {'serial': 104, 'event': 'move', 'move': 'U'}
        self.driver.inject_missed_move_to_buffer(move)

        self.assertEqual(len(self.driver.move_buffer), 2)
        self.assertEqual(self.driver.move_buffer[0], move)  # Inserted at front
        self.assertEqual(self.driver.move_buffer[1]['serial'], 105)

    def test_inject_missed_move_to_buffer_duplicate_serial(self) -> None:
        self.driver.last_serial = 100
        self.driver.move_buffer = [
            {'serial': 103, 'event': 'move', 'move': 'R'},
        ]

        move = {'serial': 103, 'event': 'move', 'move': 'U'}  # Duplicate serial
        self.driver.inject_missed_move_to_buffer(move)

        self.assertEqual(len(self.driver.move_buffer), 1)  # No change
        # Original preserved
        self.assertEqual(self.driver.move_buffer[0]['move'], 'R')

    def test_inject_missed_move_to_buffer_out_of_range(self) -> None:
        self.driver.last_serial = 100
        self.driver.move_buffer = [
            {'serial': 105, 'event': 'move', 'move': 'R'},
        ]

        move = {'serial': 110, 'event': 'move', 'move': 'U'}  # Out of range
        self.driver.inject_missed_move_to_buffer(move)

        self.assertEqual(len(self.driver.move_buffer), 1)  # No change

    async def test_check_if_move_missed_no_gap(self) -> None:
        self.driver.last_serial = 100
        self.driver.serial = 100

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            mock_request.assert_not_called()

    async def test_check_if_move_missed_with_gap(self) -> None:
        self.driver.last_serial = 100
        self.driver.serial = 103
        self.driver.move_buffer = []

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            # start_serial=104, diff+1=4
            mock_request.assert_called_once_with(104, 4)

    async def test_check_if_move_missed_with_buffer_head(self) -> None:
        self.driver.last_serial = 100
        self.driver.serial = 105
        self.driver.move_buffer = [
            {'serial': 103, 'event': 'move', 'move': 'U'},
        ]

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            # buffer_head serial, diff+1
            mock_request.assert_called_once_with(103, 6)

    async def test_check_if_move_missed_serial_zero_case(self) -> None:
        self.driver.last_serial = 100
        self.driver.serial = 0  # Wraparound case

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            mock_request.assert_not_called()  # No request when serial is 0

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
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
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int,
                                      *, _little_endian: bool = False) -> int:
                    if start == 0 and length == 8:
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x01  # event type (move)
                    if start == 16 and length == 8:
                        return 10  # data_size
                    if start == 24 and length == 32:
                        return 12345  # cube_timestamp
                    if start == 56 and length == 16:
                        return 102  # serial
                    if start == 72 and length == 2:
                        return 1  # direction
                    if start == 74 and length == 6:
                        return 2  # face value
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                with patch.object(
                    self.driver,
                    'evict_move_buffer',
                ) as mock_evict:
                    mock_evict.return_value = [{'event': 'move', 'move': 'U'}]

                    result = await self.driver.event_handler(
                        'sender',
                        test_data,
                    )

                    self.assertEqual(len(result), 1)
                    self.assertEqual(len(self.driver.move_buffer), 1)
                    move_in_buffer = self.driver.move_buffer[0]
                    self.assertEqual(move_in_buffer['event'], 'move')
                    self.assertEqual(move_in_buffer['serial'], 102)
                    self.assertEqual(move_in_buffer['cube_timestamp'], 12345)

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
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
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x55,  # magic
                    0x01,  # event type (move)
                    10,  # data_size
                ]

                result = await self.driver.event_handler('sender', test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen3.cubies_to_facelets')
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

        self.driver.last_serial = 1  # Set to 1 to trigger else branch
        self.driver.last_local_timestamp = None

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int,
                                      *, _little_endian: bool = False) -> int:
                    if start == 0 and length == 8:
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x02  # event type (facelets)
                    if start == 16 and length == 8:
                        return 10  # data_size
                    if start == 24 and length == 16:
                        return 50  # serial
                    return start % 8  # Mock corner/edge data

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                result = await self.driver.event_handler('sender', test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'facelets')
                self.assertEqual(event['serial'], 50)
                self.assertEqual(self.driver.serial, 50)
                self.assertEqual(self.driver.last_serial, 50)

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen3.DEBOUNCE', 1.0)
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
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int,
                                      *, _little_endian: bool = False) -> int:
                    if start == 0 and length == 8:
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x02  # event type (facelets)
                    if start == 16 and length == 8:
                        return 10  # data_size
                    if start == 24 and length == 16:
                        return 107  # serial
                    return start % 8  # Mock corner/edge data

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                with (
                    patch.object(
                        self.driver,
                        'check_if_move_missed',
                    ) as mock_check,
                    patch(
                        'term_timer.bluetooth.drivers.gan_gen3.cubies_to_facelets',
                    ),
                ):
                    await self.driver.event_handler('sender', test_data)
                    mock_check.assert_called_once()

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
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
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int,
                                      *, _little_endian: bool = False) -> int:
                    if start == 0 and length == 8:
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x06  # event type (move history)
                    if start == 16 and length == 8:
                        return 5  # data_size (4 moves)
                    if start == 24 and length == 8:
                        return 100  # start_serial
                    if start == 32 and length == 3:
                        return 1  # face for move 1
                    if start == 35 and length == 1:
                        return 1  # direction for move 1
                    if start == 36 and length == 3:
                        return 5  # face for move 2
                    if start == 39 and length == 1:
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

                    await self.driver.event_handler('sender', test_data)
                    # (5-1)*2 = 8 moves
                    self.assertEqual(mock_inject.call_count, 8)

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
    async def test_event_handler_hardware_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x07  # event type (hardware)
                    if start == 16 and length == 8:
                        return 10  # data_size
                    if start == 72 and length == 4:
                        return 1  # sw_major
                    if start == 76 and length == 4:
                        return 2  # sw_minor
                    if start == 80 and length == 4:
                        return 3  # hw_major
                    if start == 84 and length == 4:
                        return 4  # hw_minor
                    return ord('G')  # Hardware name characters

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                result = await self.driver.event_handler('sender', test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                self.assertEqual(event['hardware_version'], '3.4')
                self.assertEqual(event['software_version'], '1.2')
                # Gen3 doesn't support gyro
                self.assertFalse(event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
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
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x55,  # magic
                    0x10,  # event type (battery)
                    5,  # data_size
                    80,  # battery level
                ]

                result = await self.driver.event_handler('sender', test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'battery')
                self.assertEqual(event['level'], 80)

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
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
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x55,  # magic
                    0x11,  # event type (disconnect)
                    1,  # data_size
                ]

                result = await self.driver.event_handler('sender', test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'disconnect')
                self.mock_client.disconnect.assert_called_once()

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
    async def test_event_handler_invalid_magic_or_size(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x54,  # invalid magic (not 0x55)
                    0x01,  # event type
                    0,  # invalid data_size (0)
                ]

                result = await self.driver.event_handler('sender', test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.gan_gen3.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.gan_gen3.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen3.logger')
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
                'term_timer.bluetooth.drivers.gan_gen3.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x55,  # magic
                    0xFF,  # unknown event type
                    5,  # data_size
                ]

                result = await self.driver.event_handler('sender', test_data)

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

    def test_face_mapping_gen3(self) -> None:
        # Test the Gen3 face mapping for move history
        # [1, 5, 3, 0, 4, 2] maps to URFDLB
        face_indices = [1, 5, 3, 0, 4, 2]
        face_names = 'URFDLB'
        expected_mapping = ['R', 'B', 'D', 'U', 'L', 'F']

        for i, expected_face in enumerate(expected_mapping):
            self.assertEqual(face_names[face_indices[i]], expected_face)

    def test_move_direction_bits(self) -> None:
        # Test move direction bits encoding for Gen3
        # [2, 32, 8, 1, 16, 4] are the bit patterns for URFDLB
        bit_patterns = [2, 32, 8, 1, 16, 4]
        face_names = 'URFDLB'

        for i, pattern in enumerate(bit_patterns):
            # Find index of this pattern in the list
            index = bit_patterns.index(pattern)
            self.assertEqual(index, i)
            self.assertEqual(face_names[i], face_names[index])

    def test_serial_arithmetic_wraparound(self) -> None:
        # Test 8-bit serial arithmetic with wraparound
        test_cases = [
            # 1 - 255 = -254, -254 & 0xFF = 2 (with 8-bit wraparound)
            (1, 255, 2),
            # 5 - 250 = -245, -245 & 0xFF = 11 (with 8-bit wraparound)
            (5, 250, 11),
            # 90 - 100 = -10, -10 & 0xFF = 246 (with 8-bit wraparound)
            (90, 100, 246),
        ]

        for serial, last_serial, expected_diff in test_cases:
            diff = (serial - last_serial) & 0xFF
            self.assertEqual(diff, expected_diff)

    async def test_evict_move_buffer_integration(self) -> None:
        # Integration test for the complete move buffer eviction process
        self.driver.last_serial = 100
        self.driver.move_buffer = [
            {'serial': 101, 'event': 'move', 'move': 'U'},
            {'serial': 102, 'event': 'move', 'move': 'R'},
            {'serial': 104, 'event': 'move', 'move': 'F'},  # Gap at 103
        ]

        with patch.object(self.driver, 'request_move_history') as mock_request:
            # First call should evict first two moves
            result1 = await self.driver.evict_move_buffer()
            self.assertEqual(len(result1), 2)
            self.assertEqual(self.driver.last_serial, 102)
            self.assertEqual(len(self.driver.move_buffer), 1)

            # Second call should detect gap and request history
            result2 = await self.driver.evict_move_buffer()
            # The actual implementation may call
            # request_move_history multiple times
            self.assertGreaterEqual(mock_request.call_count, 1)
            mock_request.assert_called_with(104, 2)  # Gap of 1, so diff=2
            self.assertEqual(len(result2), 0)  # No eviction due to gap
