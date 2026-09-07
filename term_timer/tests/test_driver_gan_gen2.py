"""Tests for driver gan gen2."""
import asyncio
import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from itertools import starmap
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import GAN_GEN2_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import GAN_GEN2_SERVICE
from term_timer.bluetooth.constants import GAN_GEN2_STATE_CHARACTERISTIC
from term_timer.bluetooth.constants import GEN2_MOVE_HISTORY_CAPACITY
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import FaceletsEventDict
    from term_timer.bluetooth.annotations import HardwareEventDict
    from term_timer.bluetooth.annotations import MoveEventDict


class TestGanGen2Driver(unittest.IsolatedAsyncioTestCase):  # noqa: PLR0904
    """Tests for GanGen2Driver class."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'GAN356 i'
        self.mock_client.write_gatt_char = AsyncMock()
        self.mock_client.disconnect = AsyncMock()

        with patch(
                'term_timer.bluetooth.drivers.base.get_salt',
                return_value=b'salt12',
        ):
            self.driver = GanGen2Driver(
                self.mock_client,
                use_gyroscope=False,
            )

    def test_init_sets_correct_attributes(self) -> None:
        """Test init sets correct attributes."""
        self.assertEqual(self.driver.client, self.mock_client)
        self.assertEqual(self.driver.serial, -1)
        self.assertEqual(self.driver.last_serial, -1)
        self.assertEqual(self.driver.cube_timestamp, 0)
        self.assertEqual(self.driver.last_move_timestamp, None)
        self.assertEqual(self.driver.move_buffer, [])
        self.assertFalse(self.driver.history_request_pending)

    def test_class_constants(self) -> None:
        """Test class constants."""
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
        """Test init cypher gan cube."""
        # Test that init_cypher returns the encrypter for GAN cube
        self.mock_client.name = 'GAN356 i'

        # Test calling init_cypher directly
        result = self.driver.init_cypher()
        self.assertIsNotNone(result)

        # Test that cypher was set during initialization
        self.assertIsNotNone(self.driver.cypher)

    def test_init_cypher_aicube(self) -> None:
        """Test init cypher aicube."""
        # Create a new driver with AiCube name
        # to test the different encryption key path
        mock_aicube_client = Mock()
        mock_aicube_client.address = 'AA:BB:CC:DD:EE:FF'
        mock_aicube_client.name = 'AiCube_TEST'

        with patch(
                'term_timer.bluetooth.drivers.base.get_salt',
                return_value=b'salt12',
        ):
            aicube_driver = GanGen2Driver(
                mock_aicube_client,
                use_gyroscope=False,
            )

        # Test that init_cypher is called and returns the encrypter
        self.assertIsNotNone(aicube_driver.cypher)

        # Test calling init_cypher directly
        result = aicube_driver.init_cypher()
        self.assertIsNotNone(result)

    def test_send_command_handler_request_facelets(self) -> None:
        """Test send command handler request facelets."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_FACELETS')

            mock_cypher.encrypt.assert_called_once()
            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x04)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_hardware(self) -> None:
        """Test send command handler request hardware."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_HARDWARE')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x05)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_battery(self) -> None:
        """Test send command handler request battery."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_BATTERY')

            args = mock_cypher.encrypt.call_args[0]
            self.assertEqual(args[0][0], 0x09)
            self.assertEqual(result, b'encrypted_data')

    def test_send_command_handler_request_reset(self) -> None:
        """Test send command handler request reset."""
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
        """Test send command handler invalid command."""
        result = self.driver.send_command_handler('INVALID_COMMAND')
        self.assertFalse(result)

    def test_send_command_handler_empty_command(self) -> None:
        """Test send command handler empty command."""
        result = self.driver.send_command_handler('')
        self.assertFalse(result)

    def test_send_command_handler_none_command(self) -> None:
        """Test send command handler none command."""
        result = self.driver.send_command_handler(None)  # type: ignore[arg-type]
        self.assertFalse(result)

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

        # Create mock data that represents a gyro event (0x01)
        encrypted_data = bytearray(20)
        decrypted_data = bytearray([0x01] + [0] * 19)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = decrypted_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0x01

                mock_sender = Mock()
                result = await self.driver.event_handler(
                    mock_sender, encrypted_data,
                )

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
        test_data[0] = 0x01  # Lower 4 bits are 0x01 for gyro

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
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

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_moves_blocked_before_facelets(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler moves blocked before facelets."""
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
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0x02

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler move event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        # Set the serials so moves are not blocked : the last one the
        # cube announced, and the last one delivered
        self.driver.serial = 100
        self.driver.last_serial = 100
        self.driver.last_move_timestamp = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x02  # Lower 4 bits are 0x02 for move

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
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
                move_event_0 = cast('MoveEventDict', result[0])
                self.assertEqual(move_event_0['move'], "U'")
                self.assertEqual(result[1]['event'], 'move')
                move_event_1 = cast('MoveEventDict', result[1])
                self.assertEqual(move_event_1['move'], 'D')

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_with_zero_elapsed_time(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler move with zero elapsed time."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.serial = 100
        self.driver.last_serial = 100
        self.driver.last_move_timestamp = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x02

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
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
                move_event = cast('MoveEventDict', event)
                self.assertEqual(move_event['move'], 'U')
                cube_timestamp = move_event['cube_timestamp']
                self.assertIsNotNone(cube_timestamp)
                cube_timestamp = cast('int', cube_timestamp)
                # Should have computed elapsed time from timestamp difference
                self.assertGreater(cube_timestamp, 0)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_overflow_elapsed_in_milliseconds(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the overflow fallback counts in milliseconds."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.serial = 100
        self.driver.last_serial = 100
        self.driver.last_move_timestamp = mock_timestamp - timedelta(
            seconds=2,
        )

        test_data = bytearray(20)
        test_data[0] = 0x02

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x02,  # event type
                    101,   # serial (diff of 1)
                    0,     # face (U)
                    0,     # direction (normal)
                    0,     # elapsed time, the register has overflowed
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                move_event = cast('MoveEventDict', result[0])
                # Two seconds of local time are 2000 ms of cube clock,
                # the unit every other move of the protocol counts in.
                self.assertEqual(move_event['cube_timestamp'], 2000.0)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_out_of_domain_face(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a face out of domain emits nothing and does not raise."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.driver.serial = 100
        self.driver.last_serial = 100
        self.driver.last_move_timestamp = mock_timestamp

        test_data = bytearray(20)
        test_data[0] = 0x02

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.side_effect = [
                    0x02,  # event type
                    101,   # serial (diff of 1)
                    6,     # face, read on 4 bits, out of the six faces
                    0,     # direction (normal)
                    1000,  # elapsed time
                ]

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])
                # The clock of the cube kept advancing, so the moves
                # coming after this one stay in place.
                self.assertEqual(self.driver.cube_timestamp, 1000.0)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_out_of_domain_face_leaves_a_gap(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test one undecodable move is treated as a missed one."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100

        # The newest move is decodable, the one before it is not
        moves = self.move_frame(102, [(3, 0), (15, 0)], [500, 500])
        history = self.move_history_frame(102, [(3, 0), (0, 1)])

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = moves
            held = await self.driver.event_handler(Mock(), moves)

            mock_cypher.decrypt.return_value = history
            result = await self.driver.event_handler(Mock(), history)

        # A move the driver cannot name is a hole in the serials, which
        # holds the eviction back exactly like a move never received
        self.assertEqual(held, [])
        self.mock_client.write_gatt_char.assert_called_once()

        # The clock of the cube kept advancing over the two of them
        self.assertEqual(self.driver.cube_timestamp, 1000.0)

        # And the cube names the missed one in its answer
        self.assertEqual(len(result), 2)
        self.assertEqual(
            [cast('MoveEventDict', event)['move'] for event in result],
            ["U'", 'D'],
        )
        self.assertEqual(
            [cast('MoveEventDict', event)['serial'] for event in result],
            [101, 102],
        )

    @staticmethod
    def build_frame(bits: str) -> bytearray:
        """
        Build the 20 bytes of a notification out of its leading bits.

        Returns:
            The frame, zero padded up to its full length.

        """
        padded = bits.ljust(160, '0')

        return bytearray(
            int(padded[i:i + 8], 2)
            for i in range(0, 160, 8)
        )

    @staticmethod
    def face_angles_record(pos: int, face1: int, angle1: int,
                           face2: int, angle2: int) -> str:
        """
        Build the 25 bits of one face angles record.

        Returns:
            The bits of the record, most significant first.

        """
        return (
            f'{pos:01b}{face1:03b}{angle1:09b}'
            f'{face2:03b}{angle2:09b}'
        )

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_face_angles_journaled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a face angles message is journaled and emits nothing."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        test_data = self.build_frame(
            '0011'       # opcode 0x03
            '101'        # step
            '010'        # count of 2 records
            + self.face_angles_record(1, 2, 300, 5, 45)
            + self.face_angles_record(0, 0, 511, 3, 0),
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen2',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(result, [])
        self.assertEqual(len(logged.records), 1)
        self.assertIn('step:5', logged.output[0])
        self.assertIn('count:2', logged.output[0])
        self.assertIn('(1, 2, 300, 5, 45)', logged.output[0])
        self.assertIn('(0, 0, 511, 3, 0)', logged.output[0])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_face_angles_count_over_capacity(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a count wider than the notification reads no further."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        test_data = self.build_frame(
            '0011'  # opcode 0x03
            '000'   # step
            '111'   # count of 7 records, one more than the frame holds
            + self.face_angles_record(1, 1, 1, 1, 1) * 6,
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen2',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(result, [])
        self.assertEqual(logged.output[0].count('(1, 1, 1, 1, 1)'), 6)
        self.assertIn('only 6 fit', logged.output[1])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_account_binding_journaled(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test an account binding answer is journaled and emits nothing."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        test_data = self.build_frame(
            '1110'  # opcode 0x0E
            f'{0x12345678:032b}',
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen2',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(result, [])
        self.assertIn(str(0x12345678), logged.output[0])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_disconnect_journals_its_payload(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the payload of a disconnect is journaled before cutting."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.mock_client.disconnect = AsyncMock()

        test_data = self.build_frame(
            '1101'  # opcode 0x0D
            '10100101',
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.base',
                    level='WARNING',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'disconnect')
        self.assertIn('0xA5', logged.output[0])
        self.mock_client.disconnect.assert_called_once()

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen2.cubies_to_facelets')
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

        test_data = bytearray(20)
        test_data[0] = 0x04  # Lower 4 bits are 0x04 for facelets

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                # Mock corner and edge data
                def mock_get_bit_word(start: int, length: int) -> int:  # noqa: PLR0911
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
                facelets_event = cast('FaceletsEventDict', event)
                self.assertEqual(facelets_event['serial'], 50)
                self.assertIn('facelets', facelets_event)
                self.assertIn('state', facelets_event)
                self.assertIn('CP', facelets_event['state'])
                self.assertIn('CO', facelets_event['state'])
                self.assertIn('EP', facelets_event['state'])
                self.assertIn('EO', facelets_event['state'])

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    @patch('term_timer.bluetooth.drivers.gan_gen2.cubies_to_facelets')
    async def test_event_handler_facelets_leaves_the_counters_alone(
        self, mock_cubies_to_facelets: Mock,
        mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a facelets answer mid session does not rewind the serials."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_cubies_to_facelets.return_value = (
            'UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB'
        )

        # The counters have started already : only the very first
        # facelets sets them, and this one carries an older serial
        self.driver.serial = 100
        self.driver.last_serial = 100

        serial = 50
        test_data = self.build_frame(f'0100{serial:08b}')

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(len(result), 1)
        facelets_event = cast('FaceletsEventDict', result[0])
        self.assertEqual(facelets_event['event'], 'facelets')
        self.assertEqual(facelets_event['serial'], 50)
        self.assertEqual(self.driver.serial, 100)
        self.assertEqual(self.driver.last_serial, 100)

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
        test_data[0] = 0x05  # Lower 4 bits are 0x05 for hardware

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg

                def mock_get_bit_word(start: int, length: int) -> int:  # noqa: PLR0911
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
                        return 1  # gyro_enabled
                    if start == 105 and length == 1:
                        return 1  # gyro_ready
                    # Hardware name characters
                    return ord('A')

                mock_msg.get_bit_word.side_effect = mock_get_bit_word

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(len(result), 1)
                event = result[0]
                self.assertEqual(event['event'], 'hardware')
                hw_event = cast('HardwareEventDict', event)
                self.assertEqual(hw_event['hardware_version'], '1.2')
                self.assertEqual(hw_event['software_version'], '3.4')
                self.assertTrue(hw_event['gyroscope_enabled'])
                self.assertTrue(hw_event['gyroscope_ready'])

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
        test_data[0] = 0x09  # Lower 4 bits are 0x09 for battery

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
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
                battery_event = cast('BatteryEventDict', event)
                self.assertEqual(battery_event['level'], 85)
                self.assertEqual(battery_event['charging_state'], 1)

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
        test_data[0] = 0x09

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
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
                battery_event = cast('BatteryEventDict', event)
                self.assertEqual(battery_event['level'], 100)
                self.assertEqual(battery_event['charging_state'], 1)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_disconnect_event(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test event handler disconnect event."""
        mock_time.return_value = 123456789
        mock_timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017
        mock_datetime.now.return_value = mock_timestamp

        self.mock_client.disconnect = AsyncMock()

        test_data = bytearray(20)
        test_data[0] = 0x0D  # Lower 4 bits are 0x0D for disconnect

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
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
        test_data[0] = 0x0F  # Unknown event

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            with patch(
                    'term_timer.bluetooth.drivers.base.GanProtocolMessage',
            ) as mock_msg_class:
                mock_msg = Mock()
                mock_msg_class.return_value = mock_msg
                mock_msg.get_bit_word.return_value = 0x0F

                mock_sender = Mock()
                result = await self.driver.event_handler(mock_sender, test_data)

                self.assertEqual(result, [])
                mock_logger.debug.assert_called_once()

    def test_event_handler_is_async(self) -> None:
        """Test event handler is async."""
        # Verify that event_handler is an async function
        self.assertTrue(asyncio.iscoroutinefunction(self.driver.event_handler))

    def test_quaternion_calculation_positive_values(self) -> None:
        """Test quaternion calculation positive values."""
        # Test quaternion calculation logic for positive values
        test_value = 0x4000  # Positive value (bit 15 is 0)
        sign = 1 - ((test_value >> 15) * 2)  # Should be 1
        magnitude = (test_value & 0x7FFF) / 0x7FFF  # Should be 0x4000 / 0x7FFF
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertAlmostEqual(expected, 0.5, places=4)

    def test_quaternion_calculation_negative_values(self) -> None:
        """Test quaternion calculation negative values."""
        # Test quaternion calculation logic for negative values
        test_value = 0x8000  # Negative value (bit 15 is 1)
        sign = 1 - ((test_value >> 15) * 2)  # Should be -1
        magnitude = (test_value & 0x7FFF) / 0x7FFF  # Should be 0 / 0x7FFF
        expected = sign * magnitude

        self.assertEqual(sign, -1)
        self.assertEqual(expected, 0.0)

    def test_velocity_calculation_positive_values(self) -> None:
        """Test velocity calculation positive values."""
        # Test velocity calculation logic for positive values
        test_value = 0x04  # Positive value (bit 3 is 0)
        sign = 1 - ((test_value >> 3) * 2)  # Should be 1
        magnitude = test_value & 0x7  # Should be 4
        expected = sign * magnitude

        self.assertEqual(sign, 1)
        self.assertEqual(expected, 4)

    def test_velocity_calculation_negative_values(self) -> None:
        """Test velocity calculation negative values."""
        # Test velocity calculation logic for negative values
        test_value = 0x08  # Negative value (bit 3 is 1)
        sign = 1 - ((test_value >> 3) * 2)  # Should be -1
        magnitude = test_value & 0x7  # Should be 0
        expected = sign * magnitude

        self.assertEqual(sign, -1)
        self.assertEqual(expected, 0)

    def test_corner_permutation_calculation(self) -> None:
        """Test corner permutation calculation."""
        # Test that corner permutation is correctly calculated
        # The last corner is calculated as 28 - sum(first 7)
        cp_values = [0, 1, 2, 3, 4, 5, 6]
        last_cp = 28 - sum(cp_values)
        self.assertEqual(last_cp, 7)  # 28 - 21 = 7

    def test_corner_orientation_calculation(self) -> None:
        """Test corner orientation calculation."""
        # Test that corner orientation is correctly calculated
        # The last corner orientation is calculated as (3 - (sum % 3)) % 3
        co_values = [0, 1, 2, 0, 1, 2, 0]
        last_co = (3 - (sum(co_values) % 3)) % 3
        self.assertEqual(last_co, 0)  # (3 - (6 % 3)) % 3 = (3 - 0) % 3 = 0

    def test_edge_permutation_calculation(self) -> None:
        """Test edge permutation calculation."""
        # Test that edge permutation is correctly calculated
        # The last edge is calculated as 66 - sum(first 11)
        ep_values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        last_ep = 66 - sum(ep_values)
        self.assertEqual(last_ep, 11)  # 66 - 55 = 11

    def test_edge_orientation_calculation(self) -> None:
        """Test edge orientation calculation."""
        # Test that edge orientation is correctly calculated
        # The last edge orientation is calculated as (2 - (sum % 2)) % 2
        eo_values = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        last_eo = (2 - (sum(eo_values) % 2)) % 2
        self.assertEqual(last_eo, 1)  # (2 - (5 % 2)) % 2 = (2 - 1) % 2 = 1

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

    @staticmethod
    def move_record(face: int, direction: int) -> str:
        """
        Build the five bits naming one move.

        Returns:
            The bits of the move, face first, most significant first.

        """
        return f'{face:04b}{direction:01b}'

    def move_frame(self, serial: int, moves: list[tuple[int, int]],
                   durations: list[int]) -> bytearray:
        """
        Build the 20 bytes of a move notification.

        The newest move comes first, as the protocol packs it: the move
        of index i is the one of serial `serial - i`, and its duration
        sits in the block starting at the bit 47.

        Returns:
            The frame, zero padded up to its full length.

        """
        records = ''.join(
            starmap(self.move_record, moves),
        ).ljust(35, '0')
        times = ''.join(f'{duration:016b}' for duration in durations)

        return self.build_frame(
            f'0010{serial:08b}{ records }{ times }',
        )

    def move_history_frame(self, start_serial: int,
                           moves: list[tuple[int, int]],
                           count: int | None = None) -> bytearray:
        """
        Build the 20 bytes of a move history answer.

        Returns:
            The frame, zero padded up to its full length.

        """
        announced = len(moves) if count is None else count
        records = ''.join(starmap(self.move_record, moves))

        return self.build_frame(
            f'0111{start_serial:08b}{announced:05b}{ records }',
        )

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_evicted_without_gap(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the nominal move is delivered without asking anything."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100

        test_data = self.move_frame(101, [(0, 0)], [1000])

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(len(result), 1)
        move_event = cast('MoveEventDict', result[0])
        self.assertEqual(move_event['event'], 'move')
        self.assertEqual(move_event['move'], 'U')
        self.assertEqual(move_event['serial'], 101)
        # The buffer is emptied as it is filled, and the cube is left
        # alone: the latency of a nominal move does not change.
        self.assertEqual(self.driver.move_buffer, [])
        self.assertEqual(self.driver.last_serial, 101)
        self.mock_client.write_gatt_char.assert_not_called()

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_message_repeating_its_serial(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a message announcing no new move delivers nothing."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100

        # The serial the driver already holds : the message carries a
        # move record, but none of it is new
        test_data = self.move_frame(100, [(0, 0)], [1000])

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data

            result = await self.driver.event_handler(Mock(), test_data)

        self.assertEqual(result, [])
        self.assertEqual(self.driver.move_buffer, [])
        self.assertEqual(self.driver.serial, 100)
        self.assertEqual(self.driver.last_serial, 100)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_gap_requests_history(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a gap wider than the message asks the cube for the rest."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100

        # Ten moves announced, seven carried: 101, 102 and 103 are only
        # recoverable through a history request
        test_data = self.move_frame(
            110, [(0, 0)] * 7, [100] * 7,
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = test_data
            mock_cypher.encrypt.return_value = b'encrypted_data'

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen2',
                    level='WARNING',
            ) as logged:
                result = await self.driver.event_handler(Mock(), test_data)

            request = mock_cypher.encrypt.call_args[0][0]

        self.assertIn('announces 10 moves', logged.output[0])
        self.assertIn('3 of them beyond', logged.output[0])

        # Nothing is delivered while the hole is not filled
        self.assertEqual(result, [])
        self.assertEqual(len(self.driver.move_buffer), 7)
        self.assertTrue(self.driver.history_request_pending)

        self.mock_client.write_gatt_char.assert_called_once()
        self.assertEqual(request[0], 0x07)
        self.assertEqual(request[1], 104)  # oldest move carried
        self.assertEqual(request[2], 4)  # 104 is four moves after 100

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_history_recovers_in_order(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test the recovered moves come out in the order of the cube."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100

        moves = self.move_frame(110, [(0, 0)] * 7, [100] * 7)
        # The window the driver asks for starts on the oldest move it
        # carries, which the answer repeats before the missed ones
        history = self.move_history_frame(
            104, [(0, 0), (1, 0), (2, 1), (3, 0)],
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = moves
            await self.driver.event_handler(Mock(), moves)

            mock_cypher.decrypt.return_value = history
            result = await self.driver.event_handler(Mock(), history)

        self.assertEqual(len(result), 10)
        self.assertEqual(
            [cast('MoveEventDict', event)['serial'] for event in result],
            list(range(101, 111)),
        )
        self.assertEqual(
            [event['event'] for event in result[:3]],
            ['move_history'] * 3,
        )
        self.assertEqual(
            [cast('MoveEventDict', event)['move'] for event in result[:3]],
            ['D', "F'", 'R'],
        )
        # A recovered move carries no timestamp of any kind
        recovered = cast('MoveEventDict', result[0])
        self.assertIsNone(recovered['local_timestamp'])
        self.assertIsNone(recovered['cube_timestamp'])

        self.assertEqual(self.driver.move_buffer, [])
        self.assertEqual(self.driver.last_serial, 110)
        self.assertFalse(self.driver.history_request_pending)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_history_out_of_domain_move(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test an unnamable recovered move is journaled, not injected."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 103, 'event': 'move', 'move': 'U'},
        ])

        history = self.move_history_frame(103, [(0, 0), (15, 0)])

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = history

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen2',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), history)

        self.assertIn('out of domain move at index 1', logged.output[0])
        self.assertIn('face "15"', logged.output[0])
        # The hole is still there, so nothing is delivered
        self.assertEqual(result, [])
        self.assertEqual(len(self.driver.move_buffer), 1)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_history_not_the_missing_one(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a recovered move that does not close the hole is dropped."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100
        self.driver.move_buffer = cast('Any', [
            {'serial': 105, 'event': 'move', 'move': 'U'},
        ])

        # The move belongs to the window, but the buffer waits for the
        # 104 : inserting the 103 in front of it would deliver the two
        # out of order
        history = self.move_history_frame(103, [(0, 0)])

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = history

            result = await self.driver.event_handler(Mock(), history)

        self.assertEqual(result, [])
        self.assertEqual(len(self.driver.move_buffer), 1)
        self.assertEqual(self.driver.move_buffer[0]['serial'], 105)

    @patch('term_timer.bluetooth.drivers.base.time.perf_counter_ns')
    @patch('term_timer.bluetooth.drivers.base.datetime')
    async def test_event_handler_move_history_count_over_capacity(
            self, mock_datetime: Mock, mock_time: Mock,
    ) -> None:
        """Test a count wider than the notification reads no further."""
        mock_time.return_value = 123456789
        mock_datetime.now.return_value = datetime.now(tz=timezone.utc)  # noqa: UP017

        self.driver.serial = 100
        self.driver.last_serial = 100

        # Thirty one moves announced, twenty height carried at most
        history = self.move_history_frame(
            90, [(0, 0)] * GEN2_MOVE_HISTORY_CAPACITY, count=31,
        )

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = history

            with self.assertLogs(
                    'term_timer.bluetooth.drivers.gan_gen2',
                    level='DEBUG',
            ) as logged:
                result = await self.driver.event_handler(Mock(), history)

        self.assertEqual(result, [])
        self.assertIn('announces 31 moves', logged.output[0])
        self.assertIn(
            f'only { GEN2_MOVE_HISTORY_CAPACITY } fit', logged.output[0],
        )

    async def test_request_move_history_caps_the_window(self) -> None:
        """Test a window wider than the answer is capped, not sent."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            await self.driver.request_move_history(50, 40)

            request = mock_cypher.encrypt.call_args[0][0]

        self.mock_client.write_gatt_char.assert_called_once()
        self.assertEqual(len(request), 20)
        self.assertEqual(request[0], 0x07)
        self.assertEqual(request[1], 50)
        self.assertEqual(request[2], GEN2_MOVE_HISTORY_CAPACITY)
