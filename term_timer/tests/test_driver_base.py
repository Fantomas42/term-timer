"""Tests for driver base."""

import unittest
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from unittest.mock import Mock

from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter

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


class TestAsyncDriver(unittest.IsolatedAsyncioTestCase):
    """Tests for async Driver methods."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'

        self.driver = BaseDriver(self.mock_client, use_gyroscope=False)

    async def test_event_handler_raises_not_implemented(self) -> None:
        """Test event handler raises not implemented."""
        mock_sender = Mock()
        with self.assertRaises(NotImplementedError):
            await self.driver.event_handler(mock_sender, bytearray(b'data'))


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
