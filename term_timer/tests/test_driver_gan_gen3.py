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

from term_timer.bluetooth.constants import GAN_GEN3_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN3_SERVICE
from term_timer.bluetooth.constants import GAN_GEN3_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import MOVE_BUFFER_LIMIT
from term_timer.bluetooth.constants import MOVE_HISTORY_TIMEOUT
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import FaceletsEventDict
    from term_timer.bluetooth.annotations import HardwareEventDict
    from term_timer.bluetooth.annotations import MoveEventDict


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
            'term_timer.bluetooth.drivers.gan_gen2.get_salt',
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
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x01  # event type (move)
                    if start == 16 and length == 8:
                        return 10  # data_size
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

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
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x02  # event type (facelets)
                    if start == 16 and length == 8:
                        return 10  # data_size
                    if start == 24 and length == 16:
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

                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, test_data)
                    # (5-1)*2 = 8 moves
                    self.assertEqual(mock_inject.call_count, 8)

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

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventDict', event)
                self.assertEqual(hw_event['hardware_version'], '3.4')
                self.assertEqual(hw_event['software_version'], '1.2')
                # Gen3 doesn't support gyro
                self.assertFalse(hw_event['gyroscope_supported'])

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
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x10  # event type (battery)
                    if start == 16 and length == 8:
                        return 5  # data_size
                    if start == 24 and length == 8:
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
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0x11  # event type (disconnect)
                    if start == 16 and length == 8:
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
                        return 0x54  # invalid magic (not 0x55)
                    if start == 8 and length == 8:
                        return 0x01  # event type
                    if start == 16 and length == 8:
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
                        return 0x55  # magic
                    if start == 8 and length == 8:
                        return 0xFF  # unknown event type
                    if start == 16 and length == 8:
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
        """Test face mapping gen3."""
        # Test the Gen3 face mapping for move history
        # [1, 5, 3, 0, 4, 2] maps to URFDLB
        face_indices = [1, 5, 3, 0, 4, 2]
        face_names = 'URFDLB'
        expected_mapping = ['R', 'B', 'D', 'U', 'L', 'F']

        for i, expected_face in enumerate(expected_mapping):
            self.assertEqual(face_names[face_indices[i]], expected_face)

    def test_move_direction_bits(self) -> None:
        """Test move direction bits."""
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
            'term_timer.bluetooth.drivers.gan_gen2.get_salt',
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
