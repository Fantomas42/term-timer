"""Tests for the asynchronous logging configuration."""
import logging
import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from term_timer import logger as logger_module
from term_timer.logger import LOGGING_CONF
from term_timer.logger import AsyncioLogHandler
from term_timer.logger import AsyncioLogListener
from term_timer.logger import configure_logging
from term_timer.logger import shutdown_logging


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
        self.assertIsInstance(handlers[0], AsyncioLogHandler)

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
