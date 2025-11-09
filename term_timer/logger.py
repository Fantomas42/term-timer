"""Asynchronous logging configuration and setup."""

import atexit
import logging
import logging.config
import logging.handlers
import queue
import threading
from pathlib import Path
from typing import Final

from term_timer.config import DEBUG

LOGGING_DIR: Final = Path(__file__).parent.parent / 'logs'

LOGGING_FILE: Final = 'term-timer.log'

LOGGING_PATH: Final = LOGGING_DIR / LOGGING_FILE


class DbusSignalFilter(logging.Filter):
    """
    Filters out noisy D-Bus signal log messages.

    Prevents logging of frequently called D-Bus internal functions to reduce
    log verbosity and improve readability.
    """

    @staticmethod
    def filter(record: logging.LogRecord) -> bool:
        """
        Determine whether a log record should be logged.

        Args:
            record: The log record to evaluate.

        Returns:
            False if the record is from a filtered function, True otherwise.

        """
        return record.funcName not in {'_parse_msg', 'write_gatt_char'}


class AsyncioLogHandler(logging.handlers.QueueHandler):
    """
    Queue-based log handler for asynchronous logging.

    Sends log records to a queue for processing by a separate thread,
    preventing blocking of the main application during log I/O operations.
    """

    def __init__(self, log_queue: queue.Queue[logging.LogRecord]) -> None:
        """
        Initialize the async log handler with a queue.

        Args:
            log_queue: Queue to receive log records for async processing.

        """
        super().__init__(log_queue)


class AsyncioLogListener:
    """
    Background thread listener that processes log records from a queue.

    Continuously monitors a queue for log records and dispatches them to a
    handler in a separate daemon thread, enabling non-blocking logging.
    """

    def __init__(self, log_queue: queue.Queue[logging.LogRecord],
                 handler: logging.Handler) -> None:
        """
        Initialize the log listener with a queue and handler.

        Args:
            log_queue: Queue from which to read log records.
            handler: Logging handler to process the records.

        """
        self.queue: queue.Queue[logging.LogRecord] = log_queue
        self.handler: logging.Handler = handler
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """
        Start the background logging thread.

        Creates and launches a daemon thread that processes log records
        from the queue until stopped.
        """
        self._thread = threading.Thread(target=self._process_logs)
        self._thread.daemon = True
        self._thread.start()

    def stop(self) -> None:
        """
        Stop the background logging thread gracefully.

        Signals the thread to stop processing and waits for it to complete
        any remaining work before returning.
        """
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def _process_logs(self) -> None:
        while not self._stop_event.is_set():
            try:
                record = self.queue.get(block=True, timeout=0.2)
                self.handler.handle(record)
            except queue.Empty:
                continue


LOGGING_CONF: Final = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'no_dbus_signal': {
            '()': DbusSignalFilter,
        },
    },
    'formatters': {
        'standard': {
            'class': 'logging.Formatter',
            'format': '[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
            'datefmt': '%H:%M:%S',
        },
    },
    'handlers': {
        'fileHandler': {
            'formatter': 'standard',
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': LOGGING_PATH,
            'filters': ['no_dbus_signal'],
        },
    },
    'loggers': {
        '': {
            'level': 'DEBUG',
            'handlers': [
                'fileHandler',
            ],
        },
    },
}

log_listener: AsyncioLogListener | None = None


def configure_logging() -> None:
    """Configure async logging with queue handler."""
    if DEBUG:
        Path(LOGGING_DIR).mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(LOGGING_CONF)

        root_logger = logging.getLogger()
        file_handler: logging.FileHandler | None = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        if file_handler:
            root_logger.removeHandler(file_handler)

            log_queue: queue.Queue[logging.LogRecord] = queue.Queue()
            queue_handler = AsyncioLogHandler(log_queue)
            root_logger.addHandler(queue_handler)

            log_listener = AsyncioLogListener(log_queue, file_handler)
            log_listener.start()

            atexit.register(shutdown_logging)

    else:
        logging.disable(logging.INFO)


def shutdown_logging() -> None:
    """Shut down logging handlers and queue listener."""
    global log_listener  # noqa: PLW0603

    if log_listener:
        log_listener.stop()
        log_listener = None
