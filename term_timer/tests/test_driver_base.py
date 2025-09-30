import unittest
from unittest.mock import Mock

from term_timer.bluetooth.drivers.base import Driver


class TestDriver(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.driver = Driver(self.mock_client)

    def test_init_sets_client(self):
        self.assertEqual(self.driver.client, self.mock_client)

    def test_init_initializes_empty_events_list(self):
        self.assertEqual(self.driver.events, [])

    def test_init_calls_init_cypher(self):
        # init_cypher should be called during initialization
        cypher = self.driver.init_cypher()
        self.assertIsNone(cypher)

    def test_init_cypher_returns_none(self):
        result = self.driver.init_cypher()
        self.assertIsNone(result)

    def test_send_command_handler_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.driver.send_command_handler('test_command')

    def test_notification_handler_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.driver.notification_handler('sender', b'data')

    def test_add_event_with_single_event(self):
        store = []
        event = {'type': 'test', 'data': 'test_data'}

        self.driver.add_event(store, event)

        self.assertEqual(len(store), 1)
        self.assertEqual(store[0], event)
        self.assertEqual(len(self.driver.events), 1)
        self.assertEqual(self.driver.events[0], event)

    def test_add_event_with_list_of_events(self):
        store = []
        events = [
            {'type': 'test1', 'data': 'data1'},
            {'type': 'test2', 'data': 'data2'},
            {'type': 'test3', 'data': 'data3'},
        ]

        self.driver.add_event(store, events)

        self.assertEqual(len(store), 3)
        self.assertEqual(store, events)
        self.assertEqual(len(self.driver.events), 3)
        self.assertEqual(self.driver.events, events)

    def test_add_event_with_empty_list(self):
        store = []
        events = []

        self.driver.add_event(store, events)

        self.assertEqual(len(store), 0)
        self.assertEqual(len(self.driver.events), 0)

    def test_add_event_multiple_calls_accumulate(self):
        store1 = []
        store2 = []
        event1 = {'type': 'test1'}
        event2 = {'type': 'test2'}
        event3 = {'type': 'test3'}

        self.driver.add_event(store1, event1)
        self.driver.add_event(store2, event2)
        self.driver.add_event(store1, event3)

        self.assertEqual(len(store1), 2)
        self.assertEqual(store1, [event1, event3])
        self.assertEqual(len(store2), 1)
        self.assertEqual(store2, [event2])
        self.assertEqual(len(self.driver.events), 3)
        self.assertEqual(self.driver.events, [event1, event2, event3])

    def test_add_event_with_mixed_single_and_list(self):
        store = []
        single_event = {'type': 'single'}
        list_events = [{'type': 'list1'}, {'type': 'list2'}]

        self.driver.add_event(store, single_event)
        self.driver.add_event(store, list_events)

        expected_store = [single_event, *list_events]
        self.assertEqual(store, expected_store)
        self.assertEqual(self.driver.events, expected_store)

    def test_class_attributes_default_values(self):
        self.assertEqual(Driver.service_uid, '')
        self.assertEqual(Driver.state_characteristic_uid, '')
        self.assertEqual(Driver.command_characteristic_uid, '')
        self.assertTrue(Driver.disable_gyro)

    def test_driver_instance_has_cypher_attribute(self):
        self.assertTrue(hasattr(self.driver, 'cypher'))
        # cypher should be the result of init_cypher()
        # which is None in base class
        self.assertIsNone(self.driver.cypher)

    def test_add_event_preserves_original_list_reference(self):
        # Test that the store parameter is modified in place
        original_store = []
        store_reference = original_store
        event = {'type': 'test'}

        self.driver.add_event(store_reference, event)

        # Original list should be modified
        self.assertEqual(len(original_store), 1)
        self.assertEqual(original_store[0], event)
        self.assertIs(original_store, store_reference)

    def test_add_event_with_none_event(self):
        store = []

        # This should work without raising an exception
        self.driver.add_event(store, None)

        self.assertEqual(len(store), 1)
        self.assertIsNone(store[0])
        self.assertEqual(len(self.driver.events), 1)
        self.assertIsNone(self.driver.events[0])

    def test_add_event_with_complex_nested_data(self):
        store = []
        complex_event = {
            'event': 'move',
            'timestamp': 123456789,
            'data': {
                'face': 'U',
                'direction': 1,
                'nested': {
                    'quaternion': {
                        'x': 0.1, 'y': 0.2,
                        'z': 0.3, 'w': 0.4,
                    },
                },
            },
        }

        self.driver.add_event(store, complex_event)

        self.assertEqual(len(store), 1)
        self.assertEqual(store[0], complex_event)
        self.assertEqual(self.driver.events[0], complex_event)
