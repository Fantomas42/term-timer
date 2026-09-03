"""Tests for driver gan gen4."""
import asyncio
import unittest
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import GAN_GEN4_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN4_ENGINE_ECO
from term_timer.bluetooth.constants import GAN_GEN4_ENGINE_PERF
from term_timer.bluetooth.constants import GAN_GEN4_SERVICE
from term_timer.bluetooth.constants import GAN_GEN4_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.drivers.gan_gen4 import GanGen4Driver

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import FaceletsEventDict
    from term_timer.bluetooth.annotations import GyroConfigEventDict
    from term_timer.bluetooth.annotations import HardwareEventDict
    from term_timer.bluetooth.annotations import HardwareEventPartialDict
    from term_timer.bluetooth.annotations import (
        HardwareEventSoftwareVersionOnlyDict,
    )
    from term_timer.bluetooth.annotations import HardwareEventVersionOnlyDict
    from term_timer.bluetooth.annotations import MoveEventDict
    from term_timer.bluetooth.annotations import ResetEventDict
    from term_timer.bluetooth.annotations import SolvedEventDict


class TestGanGen4Driver(unittest.IsolatedAsyncioTestCase):  # noqa: PLR0904
    """Tests for GanGen4Driver class."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN12 uiM'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
            'term_timer.bluetooth.drivers.gan_gen2.get_salt',
            return_value=b'salt12',
        ):
            self.driver = GanGen4Driver(
                self.mock_client,
                use_gyroscope=False,
            )

    def test_inherits_from_gan_gen3(self) -> None:
        """Test inherits from gan gen3."""
        self.assertIsInstance(self.driver, GanGen3Driver)

    def test_class_constants(self) -> None:
        """Test class constants."""
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

    def test_shared_handlers_are_the_ones_of_the_gen3(self) -> None:
        """Test the three handlers V3 shares with V2 are not copied."""
        for name in ('handle_move', 'handle_facelets',
                     'handle_move_history', 'handle_solved'):
            with self.subTest(handler=name):
                self.assertIs(
                    getattr(GanGen4Driver, name),
                    getattr(GanGen3Driver, name),
                )

    def test_both_generations_share_their_message_header(self) -> None:
        """Test the head of V2 is not counted in its payload offset."""
        self.assertEqual(GanGen4Driver.payload_offset, 16)
        self.assertEqual(
            GanGen3Driver.payload_offset,
            GanGen4Driver.payload_offset,
        )

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_move_frame_decodes_as_before_the_factorisation(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a real V3 move frame still decodes the same three fields."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = 101
        self.driver.serial = 101

        # proto 01, dataLength 07, the cube clock on four bytes little
        # endian, the serial on two, then direction and face packed in
        # the last byte : 0b01_000010 is the mask of U, turned counter
        # clockwise. The two bytes of CRC-16 close the frame.
        body = bytes.fromhex('010739300000660042')
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            events = await self.driver.event_handler(Mock(), bytearray(frame))

        self.assertEqual(len(events), 1)
        move = cast('MoveEventDict', events[0])
        self.assertEqual(move['serial'], 102)
        self.assertEqual(move['cube_timestamp'], 12345)
        self.assertEqual(move['move'], "U'")

    def test_send_command_handler_request_facelets(self) -> None:
        """Test send command handler request facelets."""
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
        """Test send command handler request hardware."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_HARDWARE')

            args = mock_cypher.encrypt.call_args[0]
            expected_values = [0xDF, 0x03, 0x00, 0x00, 0x00]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_battery(self) -> None:
        """Test send command handler request battery."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_BATTERY')

            args = mock_cypher.encrypt.call_args[0]
            expected_values = [0xDD, 0x04, 0x00, 0xEF, 0x00, 0x00]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_reset(self) -> None:
        """Test send command handler request reset."""
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
        """Test send command handler invalid command."""
        result = self.driver.send_command_handler('INVALID_COMMAND')
        self.assertFalse(result)

    def test_send_command_handler_gyro_commands_need_a_gan_i4(self) -> None:
        """Test send command handler gyro commands need a gan i4."""
        for name in ('GAN12uiM_1234', 'GANi4v2_1234', 'GANic4_1234', None):
            with self.subTest(name=name):
                self.mock_client.name = name

                with patch.object(self.driver, 'cypher') as mock_cypher:
                    for command in (
                            'REQUEST_ENABLE_GYRO', 'REQUEST_DISABLE_GYRO',
                    ):
                        result = self.driver.send_command_handler(command)
                        self.assertFalse(result)

                    mock_cypher.encrypt.assert_not_called()

    def test_send_command_handler_request_enable_gyro(self) -> None:
        """Test send command handler request enable gyro."""
        self.mock_client.name = 'GANi4_1234'

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_ENABLE_GYRO')

            args = mock_cypher.encrypt.call_args[0]
            expected_values = [0xD4, 0x01, GAN_GEN4_ENGINE_PERF]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_disable_gyro(self) -> None:
        """Test send command handler request disable gyro."""
        self.mock_client.name = 'gani4_1234'

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_DISABLE_GYRO')

            args = mock_cypher.encrypt.call_args[0]
            expected_values = [0xD4, 0x01, GAN_GEN4_ENGINE_ECO]
            for i, expected in enumerate(expected_values):
                self.assertEqual(args[0][i], expected)
            self.assertEqual(result, b'encrypted_data')

    async def test_request_move_history_odd_serial(self) -> None:
        """Test request move history odd serial."""
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

        self.driver.last_serial = -1

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
                facelets_event = cast('FaceletsEventDict', event)
                self.assertEqual(facelets_event['serial'], 50)
                self.assertEqual(self.driver.serial, 50)
                self.assertEqual(self.driver.last_serial, 50)

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

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_hardware_product_date(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler hardware product date."""
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
                        return 0xFA  # event type (product date)
                    if start == 8 and length == 8:
                        return 4  # data_size
                    if start == 24 and length == 16:
                        return 2023  # year
                    if start == 40 and length == 8:
                        return 6  # month
                    if start == 48 and length == 8:
                        return 15  # day
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventPartialDict', event)
                self.assertEqual(hw_event['product_date'], '2023-06-15')

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_hardware_name(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler hardware name."""
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

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0xFC  # event type (hardware name)
                    if start == 8 and length == 8:
                        return 9  # data_size, index byte included
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
                hw_event = cast('HardwareEventDict', event)
                self.assertEqual(hw_event['hardware_name'], 'GAN12uiM')
                # GAN12uiM supports gyro
                self.assertTrue(hw_event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_hardware_name_without_gyro(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler hardware name without gyro."""
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

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0xFC  # event type (hardware name)
                    if start == 8 and length == 8:
                        return 8  # data_size, index byte included
                    # Return characters for "GANicE2"
                    chars = 'GANicE2'
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
                hw_event = cast('HardwareEventDict', event)
                self.assertEqual(hw_event['hardware_name'], 'GANicE2')
                # GANicE2 is one of the two proto 3 rows without a gyro
                self.assertFalse(hw_event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_hardware_name_gan_i4(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler hardware name gan i4."""
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

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0xFC  # event type (hardware name)
                    if start == 8 and length == 8:
                        return 6  # data_size, index byte included
                    # Return characters for "GANi4"
                    chars = 'GANi4'
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
                hw_event = cast('HardwareEventDict', event)
                self.assertEqual(hw_event['hardware_name'], 'GANi4')
                # The whitelist of one used to deny the gyro of the i4
                self.assertTrue(hw_event['gyroscope_supported'])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_hardware_name_full_length(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler hardware name of the longest model."""
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

                def mock_get_bit_word(start: int, length: int) -> int:
                    if start == 0 and length == 8:
                        return 0xFC  # event type (hardware name)
                    if start == 8 and length == 8:
                        return 12  # data_size, index byte included
                    # Return characters for "GAN12uiM2_A", the eleven
                    # characters the descriptor declares, then a
                    # twelfth byte no name ever contains
                    chars = 'GAN12uiM2_A'
                    char_index = (start - 24) // 8
                    if 0 <= char_index < len(chars):
                        return ord(chars[char_index])
                    return 0xFF

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventDict', event)
                self.assertEqual(hw_event['hardware_name'], 'GAN12uiM2_A')
                self.assertNotIn(chr(0xFF), hw_event['hardware_name'])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_software_version(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler software version."""
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
                        return 0xFD  # event type (software version)
                    if start == 8 and length == 8:
                        return 4  # data_size
                    if start == 24 and length == 4:
                        return 5  # sw_major
                    if start == 28 and length == 4:
                        return 3  # sw_minor
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventSoftwareVersionOnlyDict', event)
                self.assertEqual(hw_event['software_version'], '5.3')

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_hardware_version(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler hardware version."""
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
                        return 0xFE  # event type (hardware version)
                    if start == 8 and length == 8:
                        return 4  # data_size
                    if start == 24 and length == 4:
                        return 2  # hw_major
                    if start == 28 and length == 4:
                        return 1  # hw_minor
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventVersionOnlyDict', event)
                self.assertEqual(hw_event['hardware_version'], '2.1')

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_hardware_version_journals_its_whole_field(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the sixteen bits of deviceVersion reach the journal."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        # proto FE, dataLength 03, index 00, then the two bytes of the
        # deviceVersion the descriptor declares as one field of sixteen
        # bits. They differ, so a reading that drops the second one is
        # visible : the rendering keeps the nibbles of the first.
        body = bytes.fromhex('FE03002143')
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen4',
                    level='DEBUG',
            ) as logged:
                events = await self.driver.event_handler(
                    Mock(), bytearray(frame),
                )

        self.assertEqual(len(events), 1)
        hw_event = cast('HardwareEventVersionOnlyDict', events[0])
        self.assertEqual(hw_event['hardware_version'], '2.1.67')
        self.assertIn(
            'Hardware version field: 0x4321, bytes 0x21 0x43',
            logged.output[0],
        )

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_hardware_version_of_a_null_second_byte(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the rendering a cube filling one byte gets is unchanged."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        # What the GAN i4 really sends, measured the 2026-09-03 : the
        # second byte is null, and the rendering keeps its two parts
        body = bytes.fromhex('FE03001000')
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            events = await self.driver.event_handler(Mock(), bytearray(frame))

        self.assertEqual(len(events), 1)
        hw_event = cast('HardwareEventVersionOnlyDict', events[0])
        self.assertEqual(hw_event['hardware_version'], '1.0')

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_mac_address_reads_the_seven_bytes_declared(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the MAC is read on the seven bytes the descriptor gives."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        # proto FF, dataLength 08, index 00, then *seven* bytes :
        # `bleProtoId 255` declares `elementCount: 7` for `macAddress`,
        # and reading six would drop the last one on the floor
        body = bytes.fromhex('FF0800AABBCCDDEEFF11')
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen4',
                    level='DEBUG',
            ) as logged:
                events = await self.driver.event_handler(
                    Mock(), bytearray(frame),
                )

        self.assertEqual(events, [])
        self.assertIn('MAC Address: AA:BB:CC:DD:EE:FF:11', logged.output[0])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_gyroscope_disabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler gyroscope disabled."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = False

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0xEC  # gyroscope event

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_gyroscope_enabled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler gyroscope enabled."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.use_gyroscope = True

        test_data = bytearray(20)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                fields: dict[tuple[int, int], int] = {
                    (0, 8): 0xEC,  # event type (gyroscope)
                    (8, 8): 4,  # data_size
                    (16, 16): 0x8000,  # qw (signed bit set)
                    (32, 16): 0x4000,  # qx
                    (48, 16): 0x2000,  # qy
                    (64, 16): 0x1000,  # qz
                    (80, 4): 0x08,  # vx (signed bit set)
                    (84, 4): 0x04,  # vy
                    (88, 4): 0x02,  # vz
                }

                def mock_get_bit_word(
                        start: int, length: int, *,
                        little_endian: bool = False) -> int:  # noqa: ARG001
                    return fields.get((start, length), 0)

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

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_gyroscope_config(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler gyroscope config."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        test_data = bytearray(20)

        # The answer is a flag and not the mode the command carries :
        # 1, 0, 1 read on a GAN i4 for a Perf, Eco, Perf session
        cases = [
            (1, True),
            (0, False),
        ]

        for flag, expected_enabled in cases:
            words = {
                (0, 8): 0xD4,  # event type (engine config)
                (8, 8): 1,  # dataLength
                (16, 8): flag,
            }

            with (
                self.subTest(flag=flag),
                patch.object(self.driver, 'cypher') as mock_cypher,
                patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
                ) as mock_msg_class,
            ):
                mock_cypher.decrypt.return_value = test_data

                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = (
                    lambda start, length, table=words: table.get(
                        (start, length), 0,
                    )
                )

                mock_sender = Mock()
                result = await self.driver.event_handler(
                    mock_sender, test_data,
                )

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'gyro-config')
                gyro_event = cast('GyroConfigEventDict', event)
                self.assertEqual(
                    gyro_event['gyroscope_enabled'],
                    expected_enabled,
                )
                # The cube answered, so it has a gyroscope
                self.assertTrue(gyro_event['gyroscope_ready'])
                self.assertTrue(gyro_event['gyroscope_supported'])
                self.assertEqual(gyro_event['clock'], 123456789)
                self.assertEqual(gyro_event['timestamp'], mock_timestamp)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_face_rotation_is_not_a_gyroscope_message(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the 0xEE reads the seven fields of appProtoId 14."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        # proto EE, dataLength 0A, then tag, faceOld, faceCur, three
        # angles of sixteen bits little endian, and the parallel flag
        body = bytes.fromhex('EE0A07020503001A00B40001')
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen4',
                    level='DEBUG',
            ) as logged:
                events = await self.driver.event_handler(
                    Mock(), bytearray(frame),
                )

        self.assertEqual(events, [])
        self.assertIn(
            'Face rotation - tag:7, face:2->5, '
            'angles:3/26/180, parallel:1',
            logged.output[0],
        )

    def test_face_rotation_is_the_handler_of_the_0xee(self) -> None:
        """Test the dispatch table carries no gyroscope name for 0xEE."""
        self.assertEqual(
            GanGen4Driver.MESSAGE_HANDLERS[0xEE],
            'handle_face_rotation',
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
                        return 0xEF  # event type (battery)
                    if start == 8 and length == 8:
                        return 4  # data_size
                    if start == 16 and length == 8:
                        return 1  # battery index
                    if start == 24 and length == 8:
                        return 85  # battery level
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'battery')
                battery_event = cast('BatteryEventDict', event)
                self.assertEqual(battery_event['level'], 85)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_battery_level_capped(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler battery level capped."""
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
                        return 0xEF  # event type (battery)
                    if start == 8 and length == 8:
                        return 4  # data_size
                    if start == 16 and length == 8:
                        return 1  # battery index
                    if start == 24 and length == 8:
                        return 150  # battery level > 100
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                battery_event = cast('BatteryEventDict', event)
                self.assertEqual(battery_event['level'], 100)

    async def test_event_handler_reset_accepted(self) -> None:
        """Test event handler reset event carrying a success."""
        # proto D2, dataLength 04, the result on four bytes little
        # endian, then the two bytes of CRC-16 closing every V3 frame.
        test_data = bytearray(bytes.fromhex('d20401000000de56'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(len(result), 1)
        reset_event = cast('ResetEventDict', result[0])
        self.assertEqual(reset_event['event'], 'reset')
        self.assertEqual(reset_event['result'], 1)

    async def test_event_handler_reset_refused(self) -> None:
        """Test event handler reset event carrying a refusal."""
        test_data = bytearray(bytes.fromhex('d20400000000a8e2'))

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(test_data)

            result = await self.driver.event_handler(Mock(), test_data)

        # V3 declares its result on thirty-two bits where V2 declares
        # eight : the two domains differ, the published key does not.
        self.assertEqual(len(result), 1)
        reset_event = cast('ResetEventDict', result[0])
        self.assertEqual(reset_event['event'], 'reset')
        self.assertEqual(reset_event['result'], 0)

    async def test_event_handler_solved(self) -> None:
        """Test the solve the cube announces on its own is published."""
        # proto 02, dataLength 04, the cube clock on four bytes little
        # endian, then the two bytes of CRC-16 closing every V3 frame.
        body = bytes.fromhex('020439300000')
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            events = await self.driver.event_handler(Mock(), bytearray(frame))

        self.assertEqual(len(events), 1)
        solved = cast('SolvedEventDict', events[0])
        self.assertEqual(solved['event'], 'solved')
        self.assertEqual(solved['cube_timestamp'], 12345)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_chained_solved_carries_the_clock_of_its_move(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the solved message chained behind a move is decoded."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.last_serial = 101
        self.driver.serial = 101

        # The shape the nine solved messages of the 2026-09-03 session
        # had, and the one the V2 shows too : the move that closes the
        # solve, then the announcement chained behind it, both stamped
        # with the same cube clock.
        body = bytes.fromhex('010739300000660042') + bytes.fromhex(
            '020439300000',
        )
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            events = await self.driver.event_handler(Mock(), bytearray(frame))

        moves = [one for one in events if one['event'] == 'move']
        solved = [one for one in events if one['event'] == 'solved']

        self.assertEqual(len(moves), 1)
        self.assertEqual(len(solved), 1)
        self.assertEqual(
            cast('SolvedEventDict', solved[0])['cube_timestamp'],
            cast('MoveEventDict', moves[0])['cube_timestamp'],
        )

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
                        return 0xEA  # event type (disconnect)
                    if start == 8 and length == 8:
                        return 4  # data_size
                    return 0

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'disconnect')
                self.mock_client.disconnect.assert_called_once()

    async def test_disconnect_journals_the_type_of_v3(self) -> None:
        """Test the type V3 declares is journaled before the cut."""
        # proto EA, dataLength 01, type 07, then the CRC-16 of the body
        body = bytes.fromhex('EA0107')
        frame = body + self.driver.compute_crc(body).to_bytes(2, 'little')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = frame

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen2',
                    level='WARNING',
            ) as logged:
                events = await self.driver.event_handler(
                    Mock(), bytearray(frame),
                )

        # The generic handler reads its byte at payload_offset, which is
        # exactly where V3 declares its type : question 2 is armed
        self.assertIn('payload starts with "0x07"', logged.output[0])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event'], 'disconnect')
        self.mock_client.disconnect.assert_awaited_once()

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
                        return 0x99  # unknown event type
                    if start == 8 and length == 8:
                        return 4  # data_size
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

    def test_hardware_event_range(self) -> None:
        """Test hardware event range."""
        # Test the hardware event range (0xFA to 0xFE)
        hardware_events = [0xFA, 0xFB, 0xFC, 0xFD, 0xFE]
        for event in hardware_events:
            self.assertTrue(0xFA <= event <= 0xFE)

        # Test events outside the range
        non_hardware_events = [0xF9, 0xFF]
        for event in non_hardware_events:
            self.assertFalse(0xFA <= event <= 0xFE)

    def test_gyroscope_support_detection(self) -> None:
        """Test gyroscope support detection."""
        # Every proto 3 row carries a gyroscope but the two GANicE ones
        test_cases = [
            ('GAN12uiM', True),
            ('GAN12ui', True),
            ('GAN14ui', True),
            ('GANi4', True),
            ('GANicE', False),
            ('GANicE2', False),
            # The case of a GAN name is not authoritative
            ('GANice2', False),
            ('ganice', False),
        ]

        for hardware_name, expected_gyro_support in test_cases:
            has_gyro = not hardware_name.upper().startswith('GANICE')
            self.assertEqual(has_gyro, expected_gyro_support)

    def test_quaternion_calculation_gen4(self) -> None:
        """Test quaternion calculation gen4."""
        # Test quaternion calculation logic for Gen4 (same as Gen2)
        test_value = 0x4000  # Positive value (bit 15 is 0)
        sign = 1 - ((test_value >> 15) * 2)  # Should be 1
        magnitude = (test_value & 0x7FFF) / 0x7FFF  # Should be 0x4000 / 0x7FFF
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertAlmostEqual(expected, 0.5, places=4)

    def test_velocity_calculation_gen4(self) -> None:
        """Test velocity calculation gen4."""
        # Test velocity calculation logic for Gen4 (same as Gen2)
        test_value = 0x04  # Positive value (bit 3 is 0)
        sign = 1 - ((test_value >> 3) * 2)  # Should be 1
        magnitude = test_value & 0x7  # Should be 4
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertEqual(expected, 4)

    def test_face_mapping_gen4_move_history(self) -> None:
        """Test face mapping gen4 move history."""
        # Test the Gen4 face mapping for move history (same as Gen3)
        # [1, 5, 3, 0, 4, 2] maps to URFDLB
        face_indices = [1, 5, 3, 0, 4, 2]
        face_names = 'URFDLB'
        expected_mapping = ['R', 'B', 'D', 'U', 'L', 'F']

        for i, expected_face in enumerate(expected_mapping):
            self.assertEqual(face_names[face_indices[i]], expected_face)

    def test_face_mapping_gen4_move_event(self) -> None:
        """Test face mapping gen4 move event."""
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
        """Test hardware version formatting."""
        # Test hardware version string formatting
        major, minor = 2, 5
        version_string = f'{major}.{minor}'
        self.assertEqual(version_string, '2.5')

    def test_software_version_formatting(self) -> None:
        """Test software version formatting."""
        # Test software version string formatting
        major, minor = 1, 3
        version_string = f'{major}.{minor}'
        self.assertEqual(version_string, '1.3')

    def test_product_date_formatting(self) -> None:
        """Test product date formatting."""
        # Test product date string formatting
        year, month, day = 2023, 6, 15
        date_string = f'{year:04d}-{month:02d}-{day:02d}'
        self.assertEqual(date_string, '2023-06-15')

    def test_battery_calculation_with_data_size_offset(self) -> None:
        """Test battery calculation with data size offset."""
        # Test battery level calculation with data_size offset
        # Battery level is at position: 8 + data_size * 8
        data_size = 3
        battery_bit_position = 8 + data_size * 8
        self.assertEqual(battery_bit_position, 32)

    async def test_event_handler_with_invalid_data(self) -> None:
        """Test event handler with invalid data."""
        # Test with empty data
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytearray()

            with patch(
                'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg_class.side_effect = ValueError('Invalid data')

                with self.assertRaises(ValueError):
                    mock_sender = Mock()
                    await self.driver.event_handler(mock_sender, bytearray())

    def test_command_byte_sequences(self) -> None:
        """Test command byte sequences."""
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
