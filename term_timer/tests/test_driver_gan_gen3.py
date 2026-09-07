"""Tests for driver gan gen3."""
import asyncio
import time
import unittest
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from cubing_algs.constants import FACES

from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import GEN3_HISTORY_FACES
from term_timer.bluetooth.constants import GEN3_MOVE_FACES
from term_timer.bluetooth.constants import MOVE_BUFFER_LIMIT
from term_timer.bluetooth.constants import MOVE_HISTORY_TIMEOUT
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.message import GanProtocolMessage

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import FaceletsEventDict
    from term_timer.bluetooth.annotations import HardwareEventDict
    from term_timer.bluetooth.annotations import MoveEventDict
    from term_timer.bluetooth.annotations import ResetEventDict
    from term_timer.bluetooth.annotations import SolvedEventDict


class TestFormatBuildTime(unittest.TestCase):
    """Tests for the five fields of a build time."""

    def test_format_build_time(self) -> None:
        """Test the year is read little endian and the rest byte by byte."""
        msg = GanProtocolMessage(
            bytes([0xE7, 0x07, 0x0C, 0x11, 0x0F, 0x0A]),
        )

        self.assertEqual(
            GanGen3Driver.format_build_time(msg, 0),
            '2023-12-17 15:10',
        )

    def test_format_build_time_at_an_offset(self) -> None:
        """Test the same fields are read wherever the message puts them."""
        msg = GanProtocolMessage(
            bytes([0x07, 0x0E, 0xE7, 0x07, 0x0C, 0x11, 0x0F, 0x0A]),
        )

        self.assertEqual(
            GanGen3Driver.format_build_time(msg, 16),
            '2023-12-17 15:10',
        )


class TestGanGen3Driver(unittest.IsolatedAsyncioTestCase):  # noqa: PLR0904
    """Tests for GanGen3Driver class."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN356 iCarry2'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
            'term_timer.bluetooth.drivers.base.get_salt',
            return_value=b'salt12',
        ):
            self.driver = GanGen3Driver(
                self.mock_client,
                use_gyroscope=False,
            )

    def test_init_sets_correct_attributes(self) -> None:
        """Test init sets correct attributes."""
        self.assertEqual(self.driver.client, self.mock_client)
        self.assertEqual(self.driver.serial, -1)
        self.assertEqual(self.driver.last_serial, -1)
        self.assertIsNone(self.driver.last_local_timestamp)
        self.assertEqual(self.driver.move_buffer, [])

    def test_inherits_from_gan_gen2(self) -> None:
        """Test inherits from gan gen2."""
        self.assertIsInstance(self.driver, GanGen2Driver)

    def test_class_constants(self) -> None:
        """Test class constants."""
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
        """Test send command handler request facelets."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_FACELETS')

            mock_cypher.encrypt.assert_called_once()
            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x68)
            self.assertEqual(args[0][1], 0x01)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_hardware(self) -> None:
        """Test send command handler request hardware."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_HARDWARE')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x68)
            self.assertEqual(args[0][1], 0x04)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_battery(self) -> None:
        """Test send command handler request battery."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_BATTERY')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x68)
            self.assertEqual(args[0][1], 0x07)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_reset(self) -> None:
        """Test send command handler request reset."""
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
        """Test send command handler invalid command."""
        result = self.driver.send_command_handler('INVALID_COMMAND')
        self.assertFalse(result)

    async def test_request_move_history_odd_serial(self) -> None:
        """Test request move history odd serial."""
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
        """Test request move history even serial."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            # even serial, odd count
            await self.driver.request_move_history(100, 5)

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][2], 99)  # serial adjusted to odd
            self.assertEqual(args[0][4], 6)  # count adjusted to even

    async def test_request_move_history_overflow_protection(self) -> None:
        """Test request move history overflow protection."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            # Request history that would overflow beyond serial 255
            await self.driver.request_move_history(250, 300)

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][2], 249)  # adjusted to odd
            self.assertEqual(args[0][4], 250)  # count capped to serial + 1

    async def test_evict_move_buffer_empty(self) -> None:
        """Test evict move buffer empty."""
        self.driver.move_buffer = []
        self.driver.last_serial = 100

        result = await self.driver.evict_move_buffer()

        self.assertEqual(result, [])
        self.assertEqual(len(self.driver.move_buffer), 0)

    async def test_evict_move_buffer_sequential_moves(self) -> None:
        """Test evict move buffer sequential moves."""
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 101, 'event': 'move', 'move': 'U'},
            {'serial': 102, 'event': 'move', 'move': 'R'},
        ])

        result = cast(
            'list[MoveEventDict]',
            await self.driver.evict_move_buffer(),
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['serial'], 101)
        self.assertEqual(result[1]['serial'], 102)
        self.assertEqual(self.driver.last_serial, 102)
        self.assertEqual(len(self.driver.move_buffer), 0)

    async def test_evict_move_buffer_missed_move_requests_history(self) -> None:
        """Test evict move buffer missed move requests history."""
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 103, 'event': 'move', 'move': 'U'},  # Gap at 101, 102
        ])

        with patch.object(self.driver, 'request_move_history') as mock_request:
            result = await self.driver.evict_move_buffer()

            mock_request.assert_called_once_with(103, 3)  # serial 103, diff 3
            self.assertEqual(result, [])  # No events evicted due to gap
            self.assertEqual(len(self.driver.move_buffer), 1)

    async def test_evict_move_buffer_first_move_no_gap_check(self) -> None:
        """Test evict move buffer first move no gap check."""
        self.driver.last_serial = -1  # First move
        self.driver.move_buffer = cast('Any', [
            {'serial': 50, 'event': 'move', 'move': 'U'},
        ])

        result = cast(
            'list[MoveEventDict]',
            await self.driver.evict_move_buffer(),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['serial'], 50)
        self.assertEqual(self.driver.last_serial, 50)
        self.assertEqual(len(self.driver.move_buffer), 0)

    def test_is_serial_in_range_basic(self) -> None:
        """Test is serial in range basic."""
        # Test serial 5 is in range [3, 7]
        result = self.driver.is_serial_in_range(3, 7, 5)
        self.assertTrue(result)

    def test_is_serial_in_range_boundary_open(self) -> None:
        """Test is serial in range boundary open."""
        # Test boundaries with open intervals
        # start boundary, open
        self.assertFalse(self.driver.is_serial_in_range(3, 7, 3))
        # end boundary, open
        self.assertFalse(self.driver.is_serial_in_range(3, 7, 7))

    def test_is_serial_in_range_boundary_closed(self) -> None:
        """Test is serial in range boundary closed."""
        # Test boundaries with closed intervals
        self.assertTrue(
            self.driver.is_serial_in_range(3, 7, 3, closed_start=True),
        )
        self.assertTrue(
            self.driver.is_serial_in_range(3, 7, 7, closed_end=True),
        )

    def test_is_serial_in_range_wraparound(self) -> None:
        """Test is serial in range wraparound."""
        # Test wraparound case (e.g., range [250, 10] includes 255, 0, 5)
        self.assertTrue(self.driver.is_serial_in_range(250, 10, 255))
        self.assertTrue(self.driver.is_serial_in_range(250, 10, 0))
        self.assertTrue(self.driver.is_serial_in_range(250, 10, 5))
        self.assertFalse(self.driver.is_serial_in_range(250, 10, 100))

    def test_inject_missed_move_to_buffer_empty_buffer(self) -> None:
        """Test inject missed move to buffer empty buffer."""
        self.driver.last_serial = 100
        self.driver.serial = 105
        self.driver.move_buffer = []

        move = cast('Any', {'serial': 103, 'event': 'move', 'move': 'U'})
        self.driver.inject_missed_move_to_buffer(move)

        self.assertEqual(len(self.driver.move_buffer), 1)
        self.assertEqual(self.driver.move_buffer[0], move)

    def test_inject_missed_move_to_buffer_with_existing_buffer(self) -> None:
        """Test inject missed move to buffer with existing buffer."""
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 105, 'event': 'move', 'move': 'R'},
        ])

        move = cast('Any', {'serial': 104, 'event': 'move', 'move': 'U'})
        self.driver.inject_missed_move_to_buffer(move)

        self.assertEqual(len(self.driver.move_buffer), 2)
        self.assertEqual(self.driver.move_buffer[0], move)  # Inserted at front
        self.assertEqual(self.driver.move_buffer[1]['serial'], 105)

    def test_inject_missed_move_to_buffer_duplicate_serial(self) -> None:
        """Test inject missed move to buffer duplicate serial."""
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 103, 'event': 'move', 'move': 'R'},
        ])

        # Duplicate serial
        move = cast('Any', {'serial': 103, 'event': 'move', 'move': 'U'})
        self.driver.inject_missed_move_to_buffer(move)

        # No change
        self.assertEqual(len(self.driver.move_buffer), 1)
        # Original preserved
        self.assertEqual(self.driver.move_buffer[0]['move'], 'R')

    def test_inject_missed_move_to_buffer_out_of_range(self) -> None:
        """Test inject missed move to buffer out of range."""
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 105, 'event': 'move', 'move': 'R'},
        ])

        # Out of range
        move = cast('Any', {'serial': 110, 'event': 'move', 'move': 'U'})
        self.driver.inject_missed_move_to_buffer(move)

        # No change
        self.assertEqual(len(self.driver.move_buffer), 1)

    async def test_check_if_move_missed_no_gap(self) -> None:
        """Test check if move missed no gap."""
        self.driver.last_serial = 100
        self.driver.serial = 100

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            mock_request.assert_not_called()

    async def test_check_if_move_missed_with_gap(self) -> None:
        """Test check if move missed with gap."""
        self.driver.last_serial = 100
        self.driver.serial = 103
        self.driver.move_buffer = []

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            # start_serial=104, diff+1=4
            mock_request.assert_called_once_with(104, 4)

    async def test_check_if_move_missed_with_buffer_head(self) -> None:
        """Test check if move missed with buffer head."""
        self.driver.last_serial = 100
        self.driver.serial = 105
        self.driver.move_buffer = cast('Any', [
            {'serial': 103, 'event': 'move', 'move': 'U'},
        ])

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            # buffer_head serial, diff+1
            mock_request.assert_called_once_with(103, 6)

    async def test_check_if_move_missed_serial_zero_case(self) -> None:
        """Test check if move missed serial zero case."""
        self.driver.last_serial = 100
        self.driver.serial = 0  # Wraparound case

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            mock_request.assert_not_called()  # No request when serial is 0

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler move event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = 100

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(  # noqa: PLR0911
                        start: int, length: int, *,
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

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_blocked_before_facelets(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler move blocked before facelets."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = -1  # No facelets received yet

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(
                        start: int, length: int, *,
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

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_out_of_domain_face(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a face out of domain emits nothing and does not raise."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = 101

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(  # noqa: PLR0911
                        start: int, length: int, *,
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
                        return 63  # face mask, none of the six faces
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                with self.assertLogs(
                        'term_timer.bluetooth.drivers.gan_gen3',
                        level='DEBUG',
                ) as logged:
                    result = await self.driver.event_handler(
                        Mock(), test_data,
                    )

        self.assertIn('out of domain move', logged.output[0])
        self.assertIn('face mask "0x3F"', logged.output[0])
        self.assertEqual(result, [])
        self.assertEqual(self.driver.move_buffer, [])
        # The move was never named, so it stays a hole in the serials
        self.assertEqual(self.driver.last_serial, 101)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen3.cubies_to_facelets')
    async def test_event_handler_facelets_event(
            self, mock_cubies_to_facelets: Mock,
            mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler facelets event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp
        mock_cubies_to_facelets.return_value = (
            'UUUUUUUUURRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB'
        )

        self.driver.last_serial = 1  # Set to 1 to trigger else branch
        self.driver.last_local_timestamp = None

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x02  # event type (facelets)
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
                facelets_event = cast('FaceletsEventDict', event)
                self.assertEqual(facelets_event['serial'], 50)
                self.assertEqual(self.driver.serial, 50)
                self.assertEqual(self.driver.last_serial, 1)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen3.DEBOUNCE', 1.0)
    async def test_event_handler_facelets_with_debounce_check(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler facelets with debounce check."""
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
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int, *,
                                      little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x02  # event type (facelets)
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
                        'term_timer.bluetooth.drivers.gan_gen3.cubies_to_facelets',
                    ),
                ):
                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, test_data)
                    mock_check.assert_called_once()

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_history(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler move history."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(  # noqa: PLR0911
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x06  # event type (move history)
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

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_history_out_of_domain_move(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test an unnamable recovered move is journaled, not injected."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(  # noqa: PLR0911
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x06  # event type (move history)
                    if start == 8 and length == 8:
                        return 2  # data_size (2 moves)
                    if start == 16 and length == 8:
                        return 100  # start_serial
                    if start == 24 and length == 3:
                        return 1  # face for move 1
                    if start == 27 and length == 1:
                        return 1  # direction for move 1
                    if start == 28 and length == 3:
                        return 7  # face for move 2, out of the table
                    if start == 31 and length == 1:
                        return 0  # direction for move 2
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                with (
                    patch.object(
                        self.driver,
                        'inject_missed_move_to_buffer',
                    ) as mock_inject,
                    self.assertLogs(
                        'term_timer.bluetooth.drivers.gan_gen3',
                        level='DEBUG',
                    ) as logged,
                ):
                    result = await self.driver.event_handler(
                        Mock(), test_data,
                    )

        self.assertIn('out of domain move at index 1', logged.output[0])
        self.assertIn('face "7"', logged.output[0])
        # The shared handler names the opcode of the message it read
        self.assertIn('Move history message "0x06"', logged.output[0])
        # Only the move the driver could name has been injected
        self.assertEqual(mock_inject.call_count, 1)
        self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_hardware_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler hardware event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(  # noqa: PLR0911
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x07  # event type (hardware)
                    if start == 8 and length == 8:
                        return 10  # data_size
                    if start == 64 and length == 4:
                        return 1  # sw_major
                    if start == 68 and length == 4:
                        return 2  # sw_minor
                    if start == 72 and length == 4:
                        return 3  # hw_major
                    if start == 76 and length == 4:
                        return 4  # hw_minor
                    return ord('G')  # Hardware name characters

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventDict', event)
                self.assertEqual(hw_event['hardware_version'], '3.4')
                self.assertEqual(hw_event['software_version'], '1.2')
                # Gen3 carries no gyroscope: the two bits are the
                # constants the driver publishes, not a reading.
                self.assertFalse(hw_event['gyroscope_enabled'])
                self.assertFalse(hw_event['gyroscope_ready'])

    async def test_event_handler_hardware_captured_frame(self) -> None:
        """Test the hardware message a real GAN i carry 2 answered."""
        # Captured the 2026-09-02 on GANicV2S_8CA9, CRC-16 verified :
        # head 55, proto 07, dataLength 0e, then 14 bytes of payload
        # and the two bytes of the checksum.
        test_data = bytearray(
            bytes.fromhex('55070e06696356325355f0e7070c110f0ab6c7'),
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen3',
                    level='DEBUG',
            ) as logs:
                result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(len(result), 1)
        hw_event = cast('HardwareEventDict', result[0])
        self.assertEqual(hw_event['event'], 'hardware')
        self.assertEqual(hw_event['restart_no_power'], 6)
        self.assertEqual(hw_event['hardware_name'], 'icV2S')
        self.assertEqual(hw_event['software_version'], '5.5')
        self.assertEqual(hw_event['hardware_version'], '15.0')

        # buildTime lies at the offset 88 and carries the five fields
        # of V3, not the 32 bits the descriptor declares : read as one
        # word it would yield 286001127, and the descriptor offset 80
        # would put the year on the byte before it.
        self.assertIn(
            'Build time: 2023-12-17 15:10',
            '\n'.join(logs.output),
        )
        # Decoded, therefore published : the journal is not where a
        # firmware date belongs, and the field rides the hardware event
        # the handler was already sending
        self.assertEqual(hw_event['build_time'], '2023-12-17 15:10')

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_battery_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler battery event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x10  # event type (battery)
                    if start == 8 and length == 8:
                        return 5  # data_size
                    if start == 16 and length == 8:
                        return 80  # battery level
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'battery')
                battery_event = cast('BatteryEventDict', event)
                self.assertEqual(battery_event['level'], 80)

    async def test_event_handler_reset_accepted(self) -> None:
        """Test event handler reset event carrying a success."""
        # head 55, proto 08, dataLength 01, then the boolean result
        test_data = bytearray(bytes.fromhex('55080101'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(len(result), 1)
        reset_event = cast('ResetEventDict', result[0])
        self.assertEqual(reset_event['event'], 'reset')
        self.assertEqual(reset_event['result'], 1)

    async def test_event_handler_reset_refused(self) -> None:
        """Test event handler reset event carrying a refusal."""
        test_data = bytearray(bytes.fromhex('55080100'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            result = await self.driver.event_handler(Mock(), test_data)

        # A refused reset is published too : the subscriber is the one
        # that knows what to do with it, the driver only reports it.
        self.assertEqual(len(result), 1)
        reset_event = cast('ResetEventDict', result[0])
        self.assertEqual(reset_event['event'], 'reset')
        self.assertEqual(reset_event['result'], 0)

    async def test_event_handler_account_binding(self) -> None:
        """Test the account binding answer is journaled, not published."""
        # head 55, proto 09, dataLength 04, result 32 bits little endian
        test_data = bytearray(bytes.fromhex('5509042A000000'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen3',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        # V2 declares isBigEndia 0 where V1 declares 1, so the same
        # field is not read as the Gen2 handler reads it
        self.assertIn('Account binding result: 42', logged.output[0])
        self.assertEqual(result, [])

    async def test_event_handler_flag(self) -> None:
        """Test the flag message is journaled, not published."""
        test_data = bytearray(bytes.fromhex('550F012A'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen3',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        self.assertIn('Flag message "0x0F": flag 42', logged.output[0])
        self.assertEqual(result, [])

    async def test_event_handler_result(self) -> None:
        """Test the result message is journaled, not published."""
        test_data = bytearray(bytes.fromhex('55120101'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen3',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        self.assertIn('Result message "0x12": result 1', logged.output[0])
        self.assertEqual(result, [])

    async def test_event_handler_solved(self) -> None:
        """Test the solve the cube announces is published."""
        # head 55, proto 14, dataLength 04, time 32 bits little endian
        test_data = bytearray(bytes.fromhex('551404391C0000'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'solved')
        self.assertEqual(
            cast('SolvedEventDict', result[0])['cube_timestamp'],
            7225,
        )

    async def test_disconnect_journals_the_status_of_v2(self) -> None:
        """Test the status V2 declares is journaled before the cut."""
        # head 55, proto 11, dataLength 01, status 03
        test_data = bytearray(bytes.fromhex('55110103'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.base',
                    level='WARNING',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        # The generic handler reads its byte at payload_offset, which is
        # exactly where V2 declares its status : question 2 is armed
        self.assertIn('payload starts with "0x03"', logged.output[0])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'disconnect')
        self.mock_client.disconnect.assert_awaited_once()

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_disconnect_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler disconnect event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x11  # event type (disconnect)
                    if start == 8 and length == 8:
                        return 1  # data_size
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'disconnect')
                self.mock_client.disconnect.assert_called_once()

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_invalid_magic_or_size(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler invalid magic or size."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0x01  # event type
                    if start == 8 and length == 8:
                        return 0  # invalid data_size (0)
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    @patch('term_timer.bluetooth.drivers.base.logger')
    async def test_event_handler_unknown_event(
            self, mock_logger: Mock, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler unknown event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)
        # The head opens the notification and is stripped from it
        # before any message is read.
        test_data[0] = 0x55

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    if start == 0 and length == 8:
                        return 0xFF  # unknown event type
                    if start == 8 and length == 8:
                        return 5  # data_size
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])
                mock_logger.debug.assert_called_once()

    def test_event_handler_is_async(self) -> None:
        """Test event handler is async."""
        # Verify that event_handler is an async function
        self.assertTrue(asyncio.iscoroutinefunction(self.driver.event_handler))

    def test_request_move_history_is_async(self) -> None:
        """Test request move history is async."""
        # Verify that request_move_history is an async function
        self.assertTrue(
            asyncio.iscoroutinefunction(self.driver.request_move_history),
        )

    def test_face_mapping_gen3(self) -> None:
        """Test the history face table names the six faces."""
        # The firmware orders its faces D, U, B, F, L, R and names one
        # of them by its plain index in a move of the history
        self.assertEqual(
            [FACES[GEN3_HISTORY_FACES[i]] for i in range(6)],
            ['D', 'U', 'B', 'F', 'L', 'R'],
        )
        self.assertEqual(sorted(GEN3_HISTORY_FACES.values()), list(range(6)))

    def test_move_direction_bits(self) -> None:
        """Test the live move face table names the six faces."""
        # A live move names the same six faces by a bit mask
        self.assertEqual(
            [FACES[GEN3_MOVE_FACES[m]] for m in (1, 2, 4, 8, 16, 32)],
            ['D', 'U', 'B', 'F', 'L', 'R'],
        )
        self.assertEqual(sorted(GEN3_MOVE_FACES.values()), list(range(6)))

    def test_serial_arithmetic_wraparound(self) -> None:
        """Test serial arithmetic wraparound."""
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
        """Test evict move buffer integration."""
        # Integration test for the complete move buffer eviction process
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 101, 'event': 'move', 'move': 'U'},
            {'serial': 102, 'event': 'move', 'move': 'R'},
            {'serial': 104, 'event': 'move', 'move': 'F'},  # Gap at 103
        ])

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


class TestGanGen3DriverHistoryRequestRecovery(
        unittest.IsolatedAsyncioTestCase,
):
    """Tests for the recovery of an unanswered move history request."""

    # The machinery of the missed moves lives in the Gen2 driver, which
    # owns it for the three GAN generations : its records carry its name.
    logger_name = 'term_timer.bluetooth.drivers.gan_gen2'

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN356 iCarry2'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
            'term_timer.bluetooth.drivers.base.get_salt',
            return_value=b'salt12',
        ):
            self.driver = GanGen3Driver(
                self.mock_client,
                use_gyroscope=False,
            )

    def stale_history_request(self) -> None:
        """Simulate a history request the cube never answered."""
        self.driver.history_request_pending = True
        self.driver.history_request_clock = (
            time.monotonic() - MOVE_HISTORY_TIMEOUT - 0.1
        )

    def fresh_history_request(self) -> None:
        """Simulate a history request just sent to the cube."""
        self.driver.history_request_pending = True
        self.driver.history_request_clock = time.monotonic()

    async def test_evict_move_buffer_waits_for_fresh_history_request(
            self,
    ) -> None:
        """Test evict move buffer waits for fresh history request."""
        self.fresh_history_request()
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 103, 'event': 'move', 'move': 'U'},
        ])

        with patch.object(self.driver, 'request_move_history') as mock_request:
            result = await self.driver.evict_move_buffer()

            mock_request.assert_not_called()
            self.assertEqual(result, [])

    async def test_evict_move_buffer_retries_stale_history_request(
            self,
    ) -> None:
        """Test evict move buffer retries stale history request."""
        self.stale_history_request()
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 103, 'event': 'move', 'move': 'U'},
        ])

        with patch.object(
                self.driver, 'request_move_history',
        ) as mock_request, self.assertLogs(
            self.logger_name, level='WARNING',
        ) as logs:
            result = await self.driver.evict_move_buffer()

            mock_request.assert_called_once_with(103, 3)
            self.assertEqual(result, [])
            self.assertIn('unanswered', logs.output[0])

        self.assertTrue(self.driver.history_request_pending)
        self.assertTrue(self.driver.history_request_blocking)

    async def test_check_if_move_missed_retries_stale_history_request(
            self,
    ) -> None:
        """Test check if move missed retries stale history request."""
        self.stale_history_request()
        self.driver.last_serial = 100
        self.driver.serial = 103
        self.driver.move_buffer = []

        with patch.object(
                self.driver, 'request_move_history',
        ) as mock_request, self.assertLogs(
            self.logger_name, level='WARNING',
        ):
            await self.driver.check_if_move_missed()

            mock_request.assert_called_once_with(104, 4)

    async def test_check_if_move_missed_waits_for_fresh_history_request(
            self,
    ) -> None:
        """Test check if move missed waits for fresh history request."""
        self.fresh_history_request()
        self.driver.last_serial = 100
        self.driver.serial = 103
        self.driver.move_buffer = []

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            mock_request.assert_not_called()

    async def test_history_response_closes_the_request(self) -> None:
        """Test history response closes the request."""
        self.fresh_history_request()

        self.driver.close_history_request()

        self.assertFalse(self.driver.history_request_pending)
        self.assertFalse(self.driver.history_request_blocking)

    async def test_move_buffer_overflow_emits_disconnect(self) -> None:
        """Test move buffer overflow emits disconnect."""
        self.fresh_history_request()
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            # Gap at 101, 102, nothing can ever be evicted
            {'serial': 103 + i, 'event': 'move', 'move': 'U'}
            for i in range(MOVE_BUFFER_LIMIT + 1)
        ])

        with self.assertLogs(self.logger_name, level='WARNING') as logs:
            result = await self.driver.evict_move_buffer()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'disconnect')
        self.assertIn('clock', result[0])
        self.assertIn('timestamp', result[0])
        self.assertIn('overflowed', logs.output[0])
        self.mock_client.disconnect.assert_awaited_once()

    async def test_move_buffer_under_limit_stays_connected(self) -> None:
        """Test move buffer under limit stays connected."""
        self.fresh_history_request()
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 103 + i, 'event': 'move', 'move': 'U'}
            for i in range(MOVE_BUFFER_LIMIT)
        ])

        result = await self.driver.evict_move_buffer()

        self.assertEqual(result, [])
        self.mock_client.disconnect.assert_not_called()


class TestGanGen3DriverSerialCycle(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the byte the V2 serial cycles on.

    `step` is declared and carried on sixteen bits, and the firmware
    cycles it on its low byte alone : measured on a GAN i carry 2 the
    2026-09-02, the counter went 253 -> 4. A comparison led in sixteen
    bits turns that wrap into a gap of 65281 moves, and the driver
    then asks the cube for a window it can never serve.
    """

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN356 iCarry2'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
            'term_timer.bluetooth.drivers.base.get_salt',
            return_value=b'salt12',
        ):
            self.driver = GanGen3Driver(
                self.mock_client,
                use_gyroscope=False,
            )

    async def test_missed_moves_across_the_wrap_stay_a_small_window(
            self,
    ) -> None:
        """Test missed moves across the wrap stay a small window."""
        self.driver.last_serial = 255
        # The counter cycled and two moves went missing with it : led
        # in 16 bits the same gap would be 65283 moves long
        self.driver.serial = 2

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            mock_request.assert_called_once_with(3, 4)

    async def test_wrap_to_zero_asks_for_nothing(self) -> None:
        """Test wrap to zero asks for nothing."""
        self.driver.last_serial = 255
        self.driver.serial = 0

        with patch.object(self.driver, 'request_move_history') as mock_request:
            await self.driver.check_if_move_missed()

            mock_request.assert_not_called()

    async def test_move_across_the_wrap_is_evicted(self) -> None:
        """Test move across the wrap is evicted."""
        self.driver.last_serial = 255
        self.driver.move_buffer = cast('Any', [
            {'serial': 0, 'event': 'move', 'move': 'U'},
        ])

        with patch.object(self.driver, 'request_move_history') as mock_request:
            result = await self.driver.evict_move_buffer()

            mock_request.assert_not_called()

        self.assertEqual(len(result), 1)
        self.assertEqual(self.driver.last_serial, 0)

    def test_missed_move_injected_across_the_wrap(self) -> None:
        """Test missed move injected across the wrap."""
        self.driver.last_serial = 253
        self.driver.move_buffer = cast('Any', [
            {'serial': 0, 'event': 'move', 'move': 'R'},
        ])

        move = cast('Any', {'serial': 255, 'event': 'move_history'})
        self.driver.inject_missed_move_to_buffer(move)

        self.assertEqual(len(self.driver.move_buffer), 2)
        self.assertEqual(self.driver.move_buffer[0]['serial'], 255)

    async def test_request_move_history_full_cycle(self) -> None:
        """Test request move history full cycle."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            # A whole cycle missed caps the count to 256, one more than
            # the byte the frame used to carry it on
            await self.driver.request_move_history(255, 256)

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][2], 255)
            self.assertEqual(args[0][3], 0)
            self.assertEqual(args[0][4], 0x00)
            self.assertEqual(args[0][5], 0x01)

    async def test_request_move_history_writes_both_fields(self) -> None:
        """Test request move history writes both fields."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            await self.driver.request_move_history(101, 6)

            args = mock_cypher.encrypt.call_args[0]
            # `step` and `count` are declared on 16 bits little endian
            self.assertEqual(list(args[0][2:6]), [101, 0, 6, 0])


class TestGanGen3DriverChainedFrames(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the frames a GAN i carry 2 really chains.

    A chained V2 message carries its bleProtoId and its dataLength
    alone : the head of 0x55 opens the notification, not each message.
    Measured on a GAN i carry 2 the 2026-09-03, when a bench recomputing
    the CRC-16 of every frame found five moves out of 151 whose checksum
    closed six bytes further than the header announced. Each of the
    frames below is a capture of that session, checksum included.
    """

    # A move followed by the solved message the cube chains behind it,
    # both stamped with the same cube clock. The `0x14` was dropped
    # before the walk was corrected.
    # 55 01 07 | 9e5e0000 0600 42 | 14 04 | 9e5e0000 | 341e
    #  header      move payload       header  clock      crc
    MOVE_AND_SOLVED = bytes.fromhex(
        '5501079e5e000006004214049e5e0000341e',
    )

    # A battery, a move and a solved in one notification. The move it
    # carries is the one the session lost, and the history request that
    # followed was the recovery machinery covering for the walk.
    # 55 10 01 | 5a | 01 07 | 3478000036 0042 | 14 04 | 34780000 | fc37
    #  header     lvl  header   move payload      header  clock      crc
    BATTERY_MOVE_AND_SOLVED = bytes.fromhex(
        '5510015a010734780000360042140434780000fc37',
    )

    # A battery alone, its checksum right behind it: the frame the lot 0
    # read as proof that nothing is ever chained on V2.
    BATTERY_ALONE = bytes.fromhex('5510015a7147' + '00' * 10)

    # Facelets whose checksum is 0x4F00: its low byte is the very null
    # byte the Java codec breaks the chain on. The walk has to read it
    # as the terminator it is, and not as an empty message.
    FACELETS_NULL_CRC = bytes.fromhex(
        '55020e0e0005397252018942 2b384d000000 4f'.replace(' ', ''),
    )

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GANicV2S_8CA9'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
            'term_timer.bluetooth.drivers.base.get_salt',
            return_value=b'salt12',
        ):
            self.driver = GanGen3Driver(
                self.mock_client,
                use_gyroscope=False,
            )

    def opcodes(self, frame: bytes) -> list[int]:
        """
        List the opcodes the walk finds in a frame.

        Returns:
            One opcode per message the notification carries.

        """
        return [
            chunk[0]
            for chunk in self.driver.split_messages(
                self.driver.strip_head(frame) or b'',
            )
        ]

    def test_move_and_solved_are_two_messages(self) -> None:
        """Test the solved message chained behind a move is found."""
        self.assertEqual(self.opcodes(self.MOVE_AND_SOLVED), [0x01, 0x14])

    def test_battery_move_and_solved_are_three_messages(self) -> None:
        """Test a notification carrying three messages yields three."""
        self.assertEqual(
            self.opcodes(self.BATTERY_MOVE_AND_SOLVED),
            [0x10, 0x01, 0x14],
        )

    def test_the_closing_crc_is_not_read_as_a_message(self) -> None:
        """Test a lone message stops the walk on its own checksum."""
        self.assertEqual(self.opcodes(self.BATTERY_ALONE), [0x10])

    def test_a_null_low_byte_of_crc_closes_the_chain(self) -> None:
        """Test a checksum ending in a null byte still terminates."""
        frame = self.FACELETS_NULL_CRC

        self.assertEqual(
            self.driver.compute_crc(frame[1:17]),
            int.from_bytes(frame[17:19], 'little'),
        )
        self.assertEqual(self.opcodes(frame), [0x02])

    def test_chained_message_carries_no_head(self) -> None:
        """Test a chained message opens on its opcode, as the first does."""
        chunks = list(
            self.driver.split_messages(
                self.driver.strip_head(self.MOVE_AND_SOLVED) or b'',
            ),
        )

        self.assertEqual(chunks[1][0], 0x14)
        self.assertEqual(chunks[1][1], 4)

    async def test_chained_move_is_decoded_and_published(self) -> None:
        """Test the move chained behind a battery reaches the buffer."""
        self.driver.last_serial = 53
        self.driver.serial = 53

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = self.BATTERY_MOVE_AND_SOLVED

            events = await self.driver.event_handler(
                Mock(), bytearray(self.BATTERY_MOVE_AND_SOLVED),
            )

        battery = [one for one in events if one['event'] == 'battery']
        moves = [one for one in events if one['event'] == 'move']

        self.assertEqual(len(battery), 1)
        self.assertEqual(len(moves), 1)
        self.assertEqual(cast('BatteryEventDict', battery[0])['level'], 90)
        self.assertEqual(cast('MoveEventDict', moves[0])['serial'], 54)

    async def test_chained_solved_is_published(self) -> None:
        """Test the solved message chained behind a move is decoded."""
        self.driver.last_serial = 5
        self.driver.serial = 5

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = self.MOVE_AND_SOLVED

            events = await self.driver.event_handler(
                Mock(), bytearray(self.MOVE_AND_SOLVED),
            )

        moves = [one for one in events if one['event'] == 'move']
        solved = [one for one in events if one['event'] == 'solved']

        self.assertEqual(len(moves), 1)
        self.assertEqual(cast('MoveEventDict', moves[0])['serial'], 6)
        # The cube stamps its solved message with the clock of the move
        # that finished the solve, and both travel in one notification.
        self.assertEqual(len(solved), 1)
        self.assertEqual(
            cast('SolvedEventDict', solved[0])['cube_timestamp'],
            cast('MoveEventDict', moves[0])['cube_timestamp'],
        )
        self.assertEqual(
            cast('SolvedEventDict', solved[0])['cube_timestamp'],
            24222,
        )
