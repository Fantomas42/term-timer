"""Tests for the asynchronous logging configuration."""
import contextlib
import io
import logging
import logging.handlers
import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from term_timer import logger as logger_module
from term_timer.logger import LOGGING_CONF
from term_timer.logger import AsyncioLogListener
from term_timer.logger import GattValueSignalFilter
from term_timer.logger import configure_logging
from term_timer.logger import shutdown_logging

GATT_VALUE_BODY: list[object] = [
    'org.bluez.GattCharacteristic1',
    {'Value': b'\x01\x02\x03'},
    [],
]

CONNECTED_BODY: list[object] = [
    'org.bluez.Device1',
    {'Connected': True},
    [],
]


class RecordCollector(logging.Handler):
    """Logging handler keeping the records it is given."""

    def __init__(self) -> None:
        """Initialize the handler with an empty list of records."""
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        """
        Store the record instead of writing it.

        Args:
            record: The log record to keep.

        """
        self.records.append(record)


class ConfigureLoggingTestCase(unittest.TestCase):
    """Tests for configure_logging and shutdown_logging."""

    def setUp(self) -> None:
        """Save the state of the root logger and prepare a log file."""
        root_logger = logging.getLogger()
        self.root_handlers = root_logger.handlers[:]
        self.root_level = root_logger.level

        self.directory = tempfile.TemporaryDirectory()
        self.log_path = Path(self.directory.name) / 'term-timer.log'

    def tearDown(self) -> None:
        """Restore the root logger and remove the log file."""
        shutdown_logging()

        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = self.root_handlers
        root_logger.setLevel(self.root_level)

        self.directory.cleanup()

    def configure(self, level: str = 'DEBUG') -> None:
        """
        Run configure_logging in debug mode on a temporary log file.

        Args:
            level: Level given to the file handler.

        """
        file_config = LOGGING_CONF['handlers']['fileHandler']  # type: ignore[index]

        with mock.patch.object(logger_module, 'DEBUG', new=True), \
             mock.patch.dict(file_config,
                             {'filename': self.log_path, 'level': level}):
            configure_logging()

    def test_configure_logging_stores_the_listener(self) -> None:
        """The listener is reachable from the module after configuration."""
        self.configure()

        self.assertIsNotNone(logger_module.log_listener)

    def test_configure_logging_queues_the_records(self) -> None:
        """The root logger dispatches to the queue handler only."""
        self.configure()

        handlers = logging.getLogger().handlers

        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0], logging.handlers.QueueHandler)

    def test_configure_logging_carries_the_handler_level(self) -> None:
        """The queue handler is given the level of the file handler."""
        self.configure(level='WARNING')

        handler = logging.getLogger().handlers[0]

        self.assertEqual(handler.level, logging.WARNING)

    def test_configure_logging_honours_the_handler_level(self) -> None:
        """A record below the level of the file handler is not written."""
        self.configure(level='WARNING')

        logger = logging.getLogger('term_timer.tests.logger')
        logger.info('below the level')
        logger.warning('above the level')

        shutdown_logging()
        content = self.log_path.read_text()

        self.assertNotIn('below the level', content)
        self.assertIn('above the level', content)

    def test_configure_logging_filters_upstream_of_the_queue(self) -> None:
        """The signal filter sits on the queue handler, not on the file."""
        self.configure()

        queue_handler = logging.getLogger().handlers[0]
        listener = logger_module.log_listener
        if listener is None:
            self.fail('The listener has not been stored')

        self.assertEqual(len(queue_handler.filters), 1)
        self.assertIsInstance(queue_handler.filters[0], GattValueSignalFilter)
        self.assertEqual(listener.handler.filters, [])

    def test_configure_logging_drops_the_gatt_values_only(self) -> None:
        """A value notification is dropped, the life cycle is written."""
        self.configure()

        logger = logging.getLogger('bleak.backends.bluezdbus.manager')
        for body in (GATT_VALUE_BODY, CONNECTED_BODY):
            logger.debug(
                'received D-Bus signal: %s.%s (%s): %s',
                'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                '/org/bluez/hci0/dev_F7_32_D0_D2_02_EE', body,
            )

        shutdown_logging()
        content = self.log_path.read_text()

        self.assertNotIn('GattCharacteristic1', content)
        self.assertIn('Connected', content)

    def test_shutdown_logging_stops_the_listener(self) -> None:
        """Shutting down joins the listener thread and forgets it."""
        self.configure()

        listener = logger_module.log_listener
        if listener is None:
            self.fail('The listener has not been stored')

        thread = listener._thread  # noqa: SLF001
        if thread is None:
            self.fail('The listener thread has not been started')

        shutdown_logging()

        self.assertIsNone(logger_module.log_listener)
        self.assertFalse(thread.is_alive())


class ConfigureLoggingWithoutDebugTestCase(unittest.TestCase):
    """Tests for configure_logging outside of a debug session."""

    def setUp(self) -> None:
        """Save the state of the root logger."""
        root_logger = logging.getLogger()
        self.root_handlers = root_logger.handlers[:]
        self.root_level = root_logger.level

    def tearDown(self) -> None:
        """Enable logging again and restore the root logger."""
        # logging.disable is global to the process: left as it is, it
        # would silence every test running after this one
        logging.disable(logging.NOTSET)

        root_logger = logging.getLogger()
        root_logger.handlers = self.root_handlers
        root_logger.setLevel(self.root_level)

    @staticmethod
    def configure() -> None:
        """Run configure_logging outside of debug mode."""
        with mock.patch.object(logger_module, 'DEBUG', new=False):
            configure_logging()

    def test_configure_logging_silences_every_level(self) -> None:
        """No level is left enabled, up to and including critical."""
        self.configure()

        logger = logging.getLogger('term_timer.tests.logger')

        for level in (logging.DEBUG, logging.INFO, logging.WARNING,
                      logging.ERROR, logging.CRITICAL):
            with self.subTest(level=logging.getLevelName(level)):
                self.assertFalse(logger.isEnabledFor(level))

    def test_configure_logging_keeps_stderr_clean(self) -> None:
        """No record reaches the last resort handler on stderr."""
        self.configure()

        logger = logging.getLogger('term_timer.tests.logger')
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            try:
                int('not a number')
            except ValueError:
                logger.exception('Error in getch (Unix)')
            logger.critical('Cube is on fire')

        self.assertEqual(stderr.getvalue(), '')

    def test_configure_logging_starts_no_listener(self) -> None:
        """Nothing is set up to write anything anywhere."""
        self.configure()

        self.assertEqual(logging.getLogger().handlers, self.root_handlers)


class AsyncioLogListenerTestCase(unittest.TestCase):
    """Tests for the AsyncioLogListener."""

    def setUp(self) -> None:
        """Build a listener over a collecting handler."""
        self.queue: queue.Queue[logging.LogRecord] = queue.Queue()
        self.handler = RecordCollector()
        self.listener = AsyncioLogListener(self.queue, self.handler)

    def queue_records(self, count: int) -> None:
        """
        Push numbered records in the queue of the listener.

        Args:
            count: Number of records to push.

        """
        for index in range(count):
            self.queue.put(
                logging.LogRecord(
                    'term_timer', logging.INFO, __file__, index,
                    f'record {index}', None, None,
                ),
            )

    def collected(self) -> list[str]:
        """
        Return the messages handled by the collecting handler.

        Returns:
            The messages, in the order they were handled.

        """
        return [record.getMessage() for record in self.handler.records]

    def test_drain_handles_the_queued_records(self) -> None:
        """Draining hands the queued records to the handler, in order."""
        self.queue_records(3)

        self.listener.drain()

        self.assertEqual(
            self.collected(),
            ['record 0', 'record 1', 'record 2'],
        )
        self.assertTrue(self.queue.empty())

    def test_drain_on_an_empty_queue(self) -> None:
        """Draining an empty queue is a no-op."""
        self.listener.drain()

        self.assertEqual(self.collected(), [])

    def test_stop_handles_the_records_left_in_the_queue(self) -> None:
        """Stopping does not leave the last records behind."""
        self.queue_records(2)

        self.listener.stop()

        self.assertEqual(self.collected(), ['record 0', 'record 1'])


class GattValueSignalFilterTestCase(unittest.TestCase):
    """Tests for the GattValueSignalFilter."""

    def setUp(self) -> None:
        """Build the filter under test."""
        self.filter = GattValueSignalFilter()

    @staticmethod
    def signal_record(
            *args: object,
            func: str = '_parse_msg',
    ) -> logging.LogRecord:
        """
        Build the record bleak emits for a received D-Bus signal.

        Args:
            args: Arguments of the record, the body coming last.
            func: Name of the function said to have emitted the record.

        Returns:
            A record shaped like the ones of the bluezdbus manager.

        """
        return logging.LogRecord(
            'bleak.backends.bluezdbus.manager', logging.DEBUG,
            '/bleak/backends/bluezdbus/manager.py', 926,
            'received D-Bus signal: %s.%s (%s): %s',
            args, None, func,
        )

    def test_drops_a_gatt_value_notification(self) -> None:
        """The payload of a cube notification is not worth writing."""
        record = self.signal_record(
            'org.freedesktop.DBus.Properties', 'PropertiesChanged',
            '/org/bluez/hci0/dev_F7/service0012/char0015', GATT_VALUE_BODY,
        )

        self.assertFalse(self.filter.filter(record))

    def test_keeps_the_connection_life_cycle(self) -> None:
        """The signals explaining a silent cube all go through."""
        bodies: dict[str, list[object]] = {
            'Connected': CONNECTED_BODY,
            'ServicesResolved': [
                'org.bluez.Device1', {'ServicesResolved': True}, [],
            ],
            'Notifying': [
                'org.bluez.GattCharacteristic1', {'Notifying': False}, [],
            ],
            'Discovering': [
                'org.bluez.Adapter1', {'Discovering': True}, [],
            ],
        }

        for name, body in bodies.items():
            with self.subTest(property=name):
                record = self.signal_record(
                    'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                    '/org/bluez/hci0', body,
                )

                self.assertTrue(self.filter.filter(record))

    def test_keeps_a_written_characteristic(self) -> None:
        """What is sent to the cube is kept, it is low volume and useful."""
        record = logging.LogRecord(
            'bleak.backends.bluezdbus.client', logging.DEBUG,
            '/bleak/backends/bluezdbus/client.py', 856,
            'Write Characteristic %s | %s: %s',
            ('0000fff5-0000-1000-8000-00805f9b34fb', '/org/bluez', b'\x01'),
            None, 'write_gatt_char',
        )

        self.assertTrue(self.filter.filter(record))

    def test_keeps_the_records_of_another_shape(self) -> None:
        """Anything that is not a D-Bus body is left alone."""
        records = {
            'no argument': self.signal_record(),
            'body too short': self.signal_record(
                'signal', ['org.bluez.GattCharacteristic1'],
            ),
            'body not a list': self.signal_record(
                'signal', 'org.bluez.GattCharacteristic1',
            ),
            # A lone mapping is unwrapped by LogRecord and stored as is,
            # so record.args is not a tuple at all on this path
            'mapping arguments': logging.LogRecord(
                'term_timer', logging.DEBUG, __file__, 1,
                '%(Value)s', ({'Value': 'a mapping is not a body'},), None,
            ),
        }

        for name, record in records.items():
            with self.subTest(record=name):
                self.assertTrue(self.filter.filter(record))
