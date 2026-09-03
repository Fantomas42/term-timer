"""Tests for driver base."""
import unittest
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from typing import ClassVar
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import GEN3_HISTORY_FACES
from term_timer.bluetooth.constants import GEN3_MOVE_FACES
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.drivers.gan_gen4 import GanGen4Driver
from term_timer.bluetooth.drivers.moyu import MoyuWeilong10Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.message import GanProtocolMessage

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import EventDict
    from term_timer.bluetooth.annotations import GyroEventDict
    from term_timer.bluetooth.annotations import MoveEventDict
    from term_timer.bluetooth.annotations import QuaternionDict
    from term_timer.bluetooth.annotations import VelocityDict


class BaseDriver(Driver):
    """Test driver implementation for base Driver tests."""

    @staticmethod
    def init_cypher() -> GanGen2CubeEncrypter:
        """
        Return a dummy encrypter for testing.

        Returns:
            GanGen2CubeEncrypter instance with dummy keys.

        """
        return GanGen2CubeEncrypter(bytes(16), bytes(16), bytes(6))


class DispatchDriver(BaseDriver):
    """Test driver registering a single handler."""

    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {
        0x01: 'handle_probe',
    }

    async def handle_probe(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list['EventDict']:
        """
        Build one reset event out of the message.

        Returns:
            A single event naming the driver that decoded it.

        """
        return [
            {
                'event': f'probe-{ msg.get_bit_word(8, 8) }',
                'clock': clock,
                'timestamp': timestamp,
            },
        ]


class InheritedDispatchDriver(DispatchDriver):
    """Test driver redefining a handler of its parent."""

    async def handle_probe(  # noqa: PLR6301
            self, msg: GanProtocolMessage,  # noqa: ARG002
            clock: int, timestamp: datetime) -> list['EventDict']:
        """
        Build one event without reading the message.

        Returns:
            A single event naming the subclass that decoded it.

        """
        return [
            {
                'event': 'probe-inherited',
                'clock': clock,
                'timestamp': timestamp,
            },
        ]


class ChainedDriver(BaseDriver):
    """Test driver chaining its messages the way V3 does."""

    payload_offset: ClassVar[int] = 16
    chained: ClassVar[bool] = True
    crc_reserve: ClassVar[int] = 2
    MESSAGE_HANDLERS: ClassVar[dict[int, str]] = {
        0x01: 'handle_probe',
        0x02: 'handle_probe',
    }

    async def handle_probe(  # noqa: PLR6301
            self, msg: GanProtocolMessage,
            clock: int, timestamp: datetime) -> list['EventDict']:
        """
        Build one event out of the first payload byte of the message.

        Returns:
            A single event naming the payload it decoded.

        """
        return [
            {
                'event': f'probe-{ msg.get_bit_word(16, 8) }',
                'clock': clock,
                'timestamp': timestamp,
            },
        ]


class HeadedChainedDriver(ChainedDriver):
    """
    Test driver chaining its messages the way V2 does.

    The head is the only thing separating it from the V3 one : it opens
    the notification and is stripped before the walk, so both share the
    same message header of sixteen bits, and the same handler with it.
    """

    head_magic: ClassVar[int | None] = 0x55
    crc_reserve: ClassVar[int] = 0
    crc_terminator: ClassVar[int] = 2


class TestFormatMove(unittest.TestCase):
    """Tests for the bounded formatting of a move."""

    def test_format_move_clockwise(self) -> None:
        """Test a direction of 0 gives a bare face."""
        self.assertEqual(Driver.format_move(0, 0), 'U')
        self.assertEqual(Driver.format_move(5, 0), 'B')

    def test_format_move_counter_clockwise(self) -> None:
        """Test a direction of 1 gives a primed face."""
        self.assertEqual(Driver.format_move(0, 1), "U'")
        self.assertEqual(Driver.format_move(5, 1), "B'")

    def test_format_move_every_face(self) -> None:
        """Test the six faces are named in the URFDLB order."""
        self.assertEqual(
            [Driver.format_move(face, 0) for face in range(6)],
            ['U', 'R', 'F', 'D', 'L', 'B'],
        )

    def test_format_move_face_out_of_domain(self) -> None:
        """Test a face beyond the sixth is refused."""
        self.assertIsNone(Driver.format_move(6, 0))
        self.assertIsNone(Driver.format_move(15, 0))

    def test_format_move_negative_face(self) -> None:
        """Test a negative face is refused instead of wrapping around."""
        self.assertIsNone(Driver.format_move(-1, 0))

    def test_format_move_direction_out_of_domain(self) -> None:
        """Test a direction beyond the second is refused."""
        self.assertIsNone(Driver.format_move(0, 2))
        self.assertIsNone(Driver.format_move(0, 3))

    def test_format_move_negative_direction(self) -> None:
        """Test a negative direction is refused."""
        self.assertIsNone(Driver.format_move(0, -1))


class TestFaceTables(unittest.TestCase):
    """Tests for the face tables of the V2 and V3 protocols."""

    def test_move_faces_name_every_face_once(self) -> None:
        """Test the live table is a bijection onto the six faces."""
        self.assertEqual(
            sorted(GEN3_MOVE_FACES.values()), list(range(6)),
        )

    def test_history_faces_name_every_face_once(self) -> None:
        """Test the history table is a bijection onto the six faces."""
        self.assertEqual(
            sorted(GEN3_HISTORY_FACES.values()), list(range(6)),
        )

    def test_move_faces_are_single_bit_masks(self) -> None:
        """Test the live table is keyed by the firmware bit masks."""
        self.assertEqual(
            sorted(GEN3_MOVE_FACES), [1, 2, 4, 8, 16, 32],
        )

    def test_history_faces_are_plain_indexes(self) -> None:
        """Test the history table is keyed by plain firmware indexes."""
        self.assertEqual(
            sorted(GEN3_HISTORY_FACES), list(range(6)),
        )

    def test_face_tables_agree_on_the_firmware_order(self) -> None:
        """Test both tables describe the same D, U, B, F, L, R order."""
        by_mask = [
            GEN3_MOVE_FACES[1 << index]
            for index in range(6)
        ]
        by_index = [
            GEN3_HISTORY_FACES[index]
            for index in range(6)
        ]

        self.assertEqual(by_mask, by_index)
        self.assertEqual(
            [Driver.format_move(face, 0) for face in by_mask],
            ['D', 'U', 'B', 'F', 'L', 'R'],
        )


class TestCrc(unittest.TestCase):
    """Tests for the checksum closing a frame."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'

    def test_compute_crc_check_value(self) -> None:
        """Test the check value of CRC-16/CCITT-FALSE."""
        self.assertEqual(Driver.compute_crc(b'123456789'), 0x29B1)

    def test_compute_crc_empty_payload(self) -> None:
        """Test an empty payload gives the initial value back."""
        self.assertEqual(Driver.compute_crc(b''), 0xFFFF)

    def test_check_crc_matching_frame_is_silent(self) -> None:
        """Test a frame carrying its own checksum warns nothing."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        frame = bytes(
            [0x01, 0x02, 0xAA, 0xBB]
            + [0x02, 0x03, 0xCC, 0xDD, 0xEE]
            + [0x00] * 9
            + [0xD4, 0xB5],
        )

        with patch('term_timer.bluetooth.drivers.base.logger') as logger:
            driver.check_crc(frame)

        logger.warning.assert_not_called()

    def test_check_crc_mismatching_frame_warns(self) -> None:
        """Test a frame carrying a wrong checksum is reported."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        frame = bytes(
            [0x01, 0x02, 0xAA, 0xBB]
            + [0x02, 0x03, 0xCC, 0xDD, 0xEE]
            + [0x00] * 9
            + [0x12, 0x34],
        )

        with patch('term_timer.bluetooth.drivers.base.logger') as logger:
            driver.check_crc(frame)

        logger.warning.assert_called_once()

    def test_check_crc_without_reserve_is_silent(self) -> None:
        """Test a protocol without isCRC16 checks nothing."""
        driver = DispatchDriver(self.mock_client, use_gyroscope=False)
        frame = bytes([0x01, 0x02, 0xAA, 0xBB, 0x12, 0x34])

        with patch('term_timer.bluetooth.drivers.base.logger') as logger:
            driver.check_crc(frame)

        logger.warning.assert_not_called()

    def test_check_crc_frame_shorter_than_its_reserve(self) -> None:
        """Test a frame holding nothing but a checksum is left alone."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)

        with patch('term_timer.bluetooth.drivers.base.logger') as logger:
            driver.check_crc(bytes([0x12, 0x34]))

        logger.warning.assert_not_called()


class TestStripHead(unittest.TestCase):
    """Tests for the head taken off a notification."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'

    def test_strip_head_without_head_magic(self) -> None:
        """Test a protocol declaring no head hands the frame back."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        frame = bytes([0x01, 0x02, 0xAA, 0xBB])

        self.assertEqual(driver.strip_head(frame), frame)

    def test_strip_head_removes_the_declared_byte(self) -> None:
        """Test the head of the notification is taken off, once."""
        driver = HeadedChainedDriver(self.mock_client, use_gyroscope=False)
        frame = bytes([0x55, 0x01, 0x02, 0xAA, 0xBB])

        self.assertEqual(driver.strip_head(frame), frame[1:])

    def test_strip_head_refuses_another_byte(self) -> None:
        """Test a notification opening on anything else is dropped."""
        driver = HeadedChainedDriver(self.mock_client, use_gyroscope=False)

        with patch('term_timer.bluetooth.drivers.base.logger') as logger:
            self.assertIsNone(driver.strip_head(bytes([0x66, 0x01, 0x02])))

        logger.debug.assert_called_once()

    def test_strip_head_refuses_an_empty_frame(self) -> None:
        """Test an empty notification carries no head to check."""
        driver = HeadedChainedDriver(self.mock_client, use_gyroscope=False)

        with patch('term_timer.bluetooth.drivers.base.logger'):
            self.assertIsNone(driver.strip_head(b''))


class TestSplitMessages(unittest.TestCase):
    """Tests for the splitting of chained notifications."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'

    def test_split_messages_not_chained(self) -> None:
        """Test a protocol without isCycle yields the frame only once."""
        driver = DispatchDriver(self.mock_client, use_gyroscope=False)
        frame = bytes([0x01, 0x02, 0xAA, 0xBB, 0x02, 0x03, 0xCC, 0xDD])

        self.assertEqual(list(driver.split_messages(frame)), [frame])

    def test_split_messages_chained(self) -> None:
        """Test two chained messages are yielded, in order."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        frame = bytes(
            [0x01, 0x02, 0xAA, 0xBB]
            + [0x02, 0x03, 0xCC, 0xDD, 0xEE]
            + [0x00] * 9
            + [0x12, 0x34],
        )

        self.assertEqual(
            list(driver.split_messages(frame)),
            [frame, frame[4:]],
        )

    def test_split_messages_stops_on_null_head(self) -> None:
        """Test a null byte after a message closes the frame."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        frame = bytes(
            [0x01, 0x02, 0xAA, 0xBB]
            + [0x00] * 14
            + [0x12, 0x34],
        )

        self.assertEqual(list(driver.split_messages(frame)), [frame])

    def test_split_messages_reserves_the_crc_bytes(self) -> None:
        """Test the trailing CRC is never read as another message."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        frame = bytes([0x01, 0x02, 0xAA, 0xBB, 0x12, 0x34])

        self.assertEqual(list(driver.split_messages(frame)), [frame])

    def test_split_messages_chained_behind_a_stripped_head(self) -> None:
        """Test both messages carry the same header once the head is gone."""
        driver = HeadedChainedDriver(self.mock_client, use_gyroscope=False)
        # The head has been taken off the notification already, so the
        # first message reads exactly like the one chained behind it.
        body = bytes([0x01, 0x02, 0xAA, 0xBB, 0x02, 0x03, 0xCC, 0xDD, 0xEE])
        frame = body + driver.compute_crc(body).to_bytes(2, 'little')

        self.assertEqual(
            list(driver.split_messages(frame)),
            [frame, frame[4:]],
        )

    def test_split_messages_stops_on_the_closing_crc(self) -> None:
        """Test the checksum of a lone message closes the notification."""
        driver = HeadedChainedDriver(self.mock_client, use_gyroscope=False)
        body = bytes([0x01, 0x02, 0xAA, 0xBB])
        frame = (
            body
            + driver.compute_crc(body).to_bytes(2, 'little')
            + bytes(9)
        )

        self.assertEqual(list(driver.split_messages(frame)), [frame])

    def test_split_messages_refuses_a_head_without_terminator(self) -> None:
        """Test a head with no terminator stops the walk at once."""
        class Unwalkable(HeadedChainedDriver):
            crc_terminator: ClassVar[int] = 0

        driver = Unwalkable(self.mock_client, use_gyroscope=False)
        frame = bytes(
            [0x01, 0x02, 0xAA, 0xBB]
            + [0x02, 0x03, 0xCC, 0xDD, 0xEE]
            + [0x00] * 9,
        )

        with patch('term_timer.bluetooth.drivers.base.logger') as logger:
            chunks = list(driver.split_messages(frame))

        self.assertEqual(chunks, [frame])
        logger.debug.assert_called_once()


class TestAsyncDriver(unittest.IsolatedAsyncioTestCase):
    """Tests for async Driver methods."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'

        self.driver = BaseDriver(self.mock_client, use_gyroscope=False)

    async def test_event_handler_unknown_event_code(self) -> None:
        """Test event handler with an opcode absent of the table."""
        mock_sender = Mock()

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes([0x99, 0x01, 0x00])

            with patch('term_timer.bluetooth.drivers.base.logger') as logger:
                result = await self.driver.event_handler(
                    mock_sender, bytearray(b'data'),
                )

        self.assertEqual(result, [])
        self.assertEqual(self.driver.events, [])
        logger.debug.assert_called_once()

    async def test_event_handler_dispatches_to_handler(self) -> None:
        """Test event handler dispatches to the registered handler."""
        driver = DispatchDriver(self.mock_client, use_gyroscope=False)
        mock_sender = Mock()

        with patch.object(driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes([0x01, 0x2A, 0x00])

            result = await driver.event_handler(
                mock_sender, bytearray(b'data'),
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'probe-42')
        self.assertEqual(driver.events, result)

    async def test_event_handler_decodes_chained_messages(self) -> None:
        """Test event handler decodes every chained message, in order."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        mock_sender = Mock()

        with patch.object(driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(
                [0x01, 0x02, 0xAA, 0xBB]
                + [0x02, 0x03, 0xCC, 0xDD, 0xEE]
                + [0x00] * 9
                + [0x12, 0x34],
            )

            result = await driver.event_handler(
                mock_sender, bytearray(b'data'),
            )

        self.assertEqual(
            [event['event'] for event in result],
            ['probe-170', 'probe-204'],
        )
        self.assertEqual(driver.events, result)

    async def test_event_handler_stops_on_null_head(self) -> None:
        """Test event handler decodes a single message on a null byte."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        mock_sender = Mock()

        with patch.object(driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(
                [0x01, 0x02, 0xAA, 0xBB]
                + [0x00] * 14
                + [0x12, 0x34],
            )

            result = await driver.event_handler(
                mock_sender, bytearray(b'data'),
            )

        self.assertEqual(
            [event['event'] for event in result],
            ['probe-170'],
        )

    async def test_event_handler_decodes_a_frame_with_a_wrong_crc(
            self) -> None:
        """Test a frame with a wrong checksum is reported, not rejected."""
        driver = ChainedDriver(self.mock_client, use_gyroscope=False)
        mock_sender = Mock()

        with patch.object(driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes(
                [0x01, 0x02, 0xAA, 0xBB]
                + [0x00] * 14
                + [0x12, 0x34],
            )

            with patch('term_timer.bluetooth.drivers.base.logger') as logger:
                result = await driver.event_handler(
                    mock_sender, bytearray(b'data'),
                )

        logger.warning.assert_called_once()
        self.assertEqual(
            [event['event'] for event in result],
            ['probe-170'],
        )

    async def test_event_handler_handler_is_late_bound(self) -> None:
        """Test event handler calls the handler of the subclass."""
        driver = InheritedDispatchDriver(self.mock_client, use_gyroscope=False)
        mock_sender = Mock()

        with patch.object(driver, 'cypher') as mock_cypher:
            mock_cypher.decrypt.return_value = bytes([0x01, 0x2A, 0x00])

            result = await driver.event_handler(
                mock_sender, bytearray(b'data'),
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'probe-inherited')


class TestDriver(unittest.TestCase):
    """Tests for Driver base class."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'

        self.driver = BaseDriver(self.mock_client, use_gyroscope=False)

    def test_init_sets_client(self) -> None:
        """Test init sets client."""
        self.assertEqual(self.driver.client, self.mock_client)
        self.assertFalse(self.driver.use_gyroscope)

    def test_init_initializes_empty_events_list(self) -> None:
        """Test init initializes empty events list."""
        self.assertEqual(self.driver.events, [])
        self.assertFalse(self.driver.use_gyroscope)

    def test_init_calls_init_cypher(self) -> None:
        """Test init calls init cypher."""
        # init_cypher should be called during initialization
        cypher = self.driver.init_cypher()
        self.assertIsInstance(cypher, GanGen2CubeEncrypter)

    def test_init_cypher_raises_not_implemented(self) -> None:
        """Test init cypher raises not implemented."""
        with self.assertRaises(NotImplementedError):
            Driver(self.mock_client, use_gyroscope=False)

    def test_send_command_handler_raises_not_implemented(self) -> None:
        """Test send command handler raises not implemented."""
        with self.assertRaises(NotImplementedError):
            self.driver.send_command_handler('test_command')

    def test_add_event_with_single_event(self) -> None:
        """Test add event with single event."""
        store: list[EventDict] = []
        event: MoveEventDict = {
            'event': 'move',
            'clock': 100,
            'timestamp': datetime.now(tz=timezone.utc),  # noqa: UP017
            'serial': 1,
            'local_timestamp': None,
            'cube_timestamp': None,
            'face': 0,
            'direction': 1,
            'move': 'U',
        }

        self.driver.add_event(store, event)

        self.assertEqual(len(store), 1)
        self.assertEqual(store[0], event)
        self.assertEqual(len(self.driver.events), 1)
        self.assertEqual(self.driver.events[0], event)

    def test_add_event_with_list_of_events(self) -> None:
        """Test add event with list of events."""
        store: list[EventDict] = []
        now = datetime.now(tz=timezone.utc)  # noqa: UP017
        events: list[MoveEventDict] = [
            {
                'event': 'move',
                'clock': 100,
                'timestamp': now,
                'serial': 1,
                'local_timestamp': None,
                'cube_timestamp': None,
                'face': 0,
                'direction': 1,
                'move': 'U',
            },
            {
                'event': 'move',
                'clock': 101,
                'timestamp': now,
                'serial': 2,
                'local_timestamp': None,
                'cube_timestamp': None,
                'face': 1,
                'direction': -1,
                'move': "U'",
            },
            {
                'event': 'move',
                'clock': 102,
                'timestamp': now,
                'serial': 3,
                'local_timestamp': None,
                'cube_timestamp': None,
                'face': 2,
                'direction': 2,
                'move': 'U2',
            },
        ]

        self.driver.add_event(store, events)

        self.assertEqual(len(store), 3)
        self.assertEqual(store, events)
        self.assertEqual(len(self.driver.events), 3)
        self.assertEqual(self.driver.events, events)

    def test_add_event_with_empty_list(self) -> None:
        """Test add event with empty list."""
        store: list[EventDict] = []
        events: list[EventDict] = []

        self.driver.add_event(store, events)

        self.assertEqual(len(store), 0)
        self.assertEqual(len(self.driver.events), 0)

    def test_add_event_multiple_calls_accumulate(self) -> None:
        """Test add event multiple calls accumulate."""
        store1: list[EventDict] = []
        store2: list[EventDict] = []
        now = datetime.now(tz=timezone.utc)  # noqa: UP017
        event1: MoveEventDict = {
            'event': 'move',
            'clock': 100,
            'timestamp': now,
            'serial': 1,
            'local_timestamp': None,
            'cube_timestamp': None,
            'face': 0,
            'direction': 1,
            'move': 'U',
        }
        event2: MoveEventDict = {
            'event': 'move',
            'clock': 101,
            'timestamp': now,
            'serial': 2,
            'local_timestamp': None,
            'cube_timestamp': None,
            'face': 1,
            'direction': 1,
            'move': 'R',
        }
        event3: MoveEventDict = {
            'event': 'move',
            'clock': 102,
            'timestamp': now,
            'serial': 3,
            'local_timestamp': None,
            'cube_timestamp': None,
            'face': 2,
            'direction': 1,
            'move': 'F',
        }

        self.driver.add_event(store1, event1)
        self.driver.add_event(store2, event2)
        self.driver.add_event(store1, event3)

        self.assertEqual(len(store1), 2)
        self.assertEqual(store1, [event1, event3])
        self.assertEqual(len(store2), 1)
        self.assertEqual(store2, [event2])
        self.assertEqual(len(self.driver.events), 3)
        self.assertEqual(self.driver.events, [event1, event2, event3])

    def test_add_event_with_mixed_single_and_list(self) -> None:
        """Test add event with mixed single and list."""
        store: list[EventDict] = []
        now = datetime.now(tz=timezone.utc)  # noqa: UP017
        single_event: MoveEventDict = {
            'event': 'move',
            'clock': 100,
            'timestamp': now,
            'serial': 1,
            'local_timestamp': None,
            'cube_timestamp': None,
            'face': 0,
            'direction': 1,
            'move': 'U',
        }
        list_events: list[MoveEventDict] = [
            {
                'event': 'move',
                'clock': 101,
                'timestamp': now,
                'serial': 2,
                'local_timestamp': None,
                'cube_timestamp': None,
                'face': 1,
                'direction': 1,
                'move': 'R',
            },
            {
                'event': 'move',
                'clock': 102,
                'timestamp': now,
                'serial': 3,
                'local_timestamp': None,
                'cube_timestamp': None,
                'face': 2,
                'direction': 1,
                'move': 'F',
            },
        ]

        self.driver.add_event(store, single_event)
        self.driver.add_event(store, list_events)

        expected_store = [single_event, *list_events]
        self.assertEqual(store, expected_store)
        self.assertEqual(self.driver.events, expected_store)

    def test_class_attributes_default_values(self) -> None:
        """Test class attributes default values."""
        self.assertEqual(Driver.service_uid, '')
        self.assertEqual(Driver.state_characteristic_uid, '')
        self.assertEqual(Driver.command_characteristic_uid, '')

    def test_driver_instance_has_cypher_attribute(self) -> None:
        """Test driver instance has cypher attribute."""
        self.assertTrue(hasattr(self.driver, 'cypher'))
        # cypher should be the result of init_cypher()
        self.assertIsInstance(self.driver.cypher, GanGen2CubeEncrypter)

    def test_add_event_preserves_original_list_reference(self) -> None:
        """Test add event preserves original list reference."""
        # Test that the store parameter is modified in place
        original_store: list[EventDict] = []
        store_reference = original_store
        event: MoveEventDict = {
            'event': 'move',
            'clock': 100,
            'timestamp': datetime.now(tz=timezone.utc),  # noqa: UP017
            'serial': 1,
            'local_timestamp': None,
            'cube_timestamp': None,
            'face': 0,
            'direction': 1,
            'move': 'U',
        }

        self.driver.add_event(store_reference, event)

        # Original list should be modified
        self.assertEqual(len(original_store), 1)
        self.assertEqual(original_store[0], event)
        self.assertIs(original_store, store_reference)

    def test_add_event_with_none_event(self) -> None:
        """Test add event with none event."""
        store: list[EventDict] = []

        # This should work without raising an exception
        self.driver.add_event(store, None)  # type: ignore[arg-type]

        self.assertEqual(len(store), 1)
        self.assertIsNone(store[0])
        self.assertEqual(len(self.driver.events), 1)
        self.assertIsNone(self.driver.events[0])

    def test_add_event_with_complex_nested_data(self) -> None:
        """Test add event with complex nested data."""
        store: list[EventDict] = []
        quaternion: QuaternionDict = {
            'x': 0.1,
            'y': 0.2,
            'z': 0.3,
            'w': 0.4,
        }
        velocity: VelocityDict = {
            'x': 0.5,
            'y': 0.6,
            'z': 0.7,
        }
        complex_event: GyroEventDict = {
            'event': 'gyro',
            'clock': 100,
            'timestamp': datetime.now(tz=timezone.utc),  # noqa: UP017
            'quaternion': quaternion,
            'velocity': velocity,
        }

        self.driver.add_event(store, complex_event)

        self.assertEqual(len(store), 1)
        self.assertEqual(store[0], complex_event)
        self.assertEqual(self.driver.events[0], complex_event)


class TestShippedDispatchTables(unittest.TestCase):
    """Tests for the dispatch tables of the drivers actually shipped."""

    DRIVERS = (
        GanGen2Driver,
        GanGen3Driver,
        GanGen4Driver,
        MoyuWeilong10Driver,
    )

    def test_every_handler_name_resolves(self) -> None:
        """Test every handler name resolves."""
        # The dispatch resolves handlers by name at notification time,
        # so a table entry pointing at a method that no longer exists
        # is a runtime failure on a real cube and nothing before it.
        # Renaming a handler without its entry is the way in.
        for driver in self.DRIVERS:
            for opcode, name in driver.MESSAGE_HANDLERS.items():
                with self.subTest(driver=driver.__name__, opcode=opcode):
                    handler = getattr(driver, name, None)

                    self.assertIsNotNone(
                        handler,
                        f'{ driver.__name__ } dispatches 0x{ opcode:02X} to '
                        f'{ name }, which does not exist',
                    )
                    self.assertTrue(callable(handler))
