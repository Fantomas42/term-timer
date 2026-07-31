"""Tests for the asynchronous logging configuration."""
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from term_timer import logger as logger_module
from term_timer.logger import LOGGING_CONF
from term_timer.logger import AsyncioLogHandler
from term_timer.logger import configure_logging
from term_timer.logger import shutdown_logging


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

    def configure(self) -> None:
        """Run configure_logging in debug mode on a temporary log file."""
        file_config = LOGGING_CONF['handlers']['fileHandler']  # type: ignore[index]

        with mock.patch.object(logger_module, 'DEBUG', new=True), \
             mock.patch.dict(file_config, {'filename': self.log_path}):
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
