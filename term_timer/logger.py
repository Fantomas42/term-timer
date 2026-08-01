"""Asynchronous logging configuration and setup."""
import atexit
import logging
import logging.config
import logging.handlers
import os
import queue
import sys
from datetime import datetime
from typing import Final
from typing import cast
from typing import override

from term_timer import __version__
from term_timer.config import DEBUG
from term_timer.constants import LOGGING_DIRECTORY

# The date is taken once, at import: a run started before midnight keeps
# writing in the file of the day it was launched, which is what makes a
# file readable as a sequence of sessions
LOGGING_FILE: Final = datetime.now().strftime(  # noqa: DTZ005
    'term-timer-%Y-%m-%d.log',
)

LOGGING_PATH: Final = LOGGING_DIRECTORY / LOGGING_FILE

FILE_HANDLER_NAME: Final = 'fileHandler'

logger = logging.getLogger(__name__)


GATT_VALUE_INTERFACE: Final = 'org.bluez.GattCharacteristic1'

INITIAL_PROPERTIES_MESSAGE: Final = 'initial properties: %s'


class BleakInitialPropertiesFilter(logging.Filter):
    """
    Drops the dump bleak takes of every D-Bus object it can see.

    A single record of 15 KB, emitted once per launch by the manager:
    34% of a measured session, and more bytes per day than everything
    else put together. It lists what BlueZ knows of every adapter and
    every paired device, none of which says anything about this cube.
    The connection life cycle is logged elsewhere, signal by signal.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Determine whether a log record should be logged.

        The raw format string of the record is compared, before any
        formatting: the 15 KB are in the arguments, and they are never
        touched.

        Args:
            record: The log record to evaluate.

        Returns:
            False for the initial properties dump, True otherwise.

        """
        return record.msg != INITIAL_PROPERTIES_MESSAGE


class GattValueSignalFilter(logging.Filter):
    """
    Drops the D-Bus signals carrying a GATT characteristic value.

    Bleak logs one record per notification received from the cube, each
    holding the whole D-Bus message body: 84% of the records and 96% of
    the bytes of a debug session, for data the decoded cube events say
    better. Every other D-Bus signal is kept, and the connection life
    cycle above all — Connected, ServicesResolved, Notifying — which is
    what tells a cube gone silent from a cube left alone.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Determine whether a log record should be logged.

        The body of the signal is read from the arguments of the record,
        not from its message, so nothing has to be formatted to decide.

        Args:
            record: The log record to evaluate.

        Returns:
            False for a GATT characteristic value notification, True
            otherwise.

        """
        args = record.args

        if not isinstance(args, tuple) or not args:
            return True

        body = args[-1]

        if not isinstance(body, list):
            return True

        signal = cast('list[object]', body)

        if len(signal) < 2:
            return True

        interface, changed = signal[0], signal[1]

        return not (
            interface == GATT_VALUE_INTERFACE
            and isinstance(changed, dict)
            and 'Value' in changed
        )


LOGGING_CONF: Final = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'class': 'logging.Formatter',
            # The second of resolution of the previous format was
            # unusable: at 41 records per second, forty lines carried the
            # same stamp. funcName:lineno finally displays what
            # findCaller collects on every record anyway. No thread name:
            # a whole session was measured at 171 records out of 171 on
            # MainThread, dbus_fast running on the asyncio loop and the
            # listener thread consuming records without ever emitting one
            'format': (
                '%(asctime)s.%(msecs)03d %(levelname).1s '
                '%(name)-32s %(funcName)s:%(lineno)d %(message)s'
            ),
            'datefmt': '%H:%M:%S',
        },
    },
    'handlers': {
        FILE_HANDLER_NAME: {
            'formatter': 'standard',
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': LOGGING_PATH,
        },
    },
    'loggers': {
        '': {
            'level': 'DEBUG',
            'handlers': [
                FILE_HANDLER_NAME,
            ],
        },
    },
}

log_listener: logging.handlers.QueueListener | None = None


def log_session_header() -> None:
    """
    Write the line opening a session in the log file.

    A file holds one day of runs appended one after the other, and the
    time stamps of the records carry no date: without this line nothing
    tells where a run begins, nor which one of them is being read.
    """
    logger.info(
        'Term Timer %s started on %s, pid %d, command: %s',
        __version__,
        datetime.now().isoformat(timespec='seconds'),  # noqa: DTZ005
        os.getpid(),
        ' '.join(sys.argv),
    )


def configure_logging() -> None:
    """Configure async logging with queue handler."""
    global log_listener  # noqa: PLW0603

    if DEBUG:
        logging.config.dictConfig(LOGGING_CONF)

        root_logger = logging.getLogger()
        file_handler = logging.getHandlerByName(FILE_HANDLER_NAME)

        if file_handler:
            root_logger.removeHandler(file_handler)

            log_queue: queue.Queue[logging.LogRecord] = queue.Queue()
            queue_handler = logging.handlers.QueueHandler(log_queue)
            # The level of a handler is honoured by the logger dispatching
            # to it, not by the handler itself: queueing the records is
            # what dispatches them now, so the level has to be carried over
            queue_handler.setLevel(file_handler.level)
            # Filtering belongs upstream of the queue: QueueHandler clears
            # record.args when it enqueues, so the body of the signal is
            # already gone on the other side, and a record dropped there
            # has paid the queue and the thread wake-up for nothing
            queue_handler.addFilter(GattValueSignalFilter())
            queue_handler.addFilter(BleakInitialPropertiesFilter())
            root_logger.addHandler(queue_handler)

            log_listener = logging.handlers.QueueListener(
                log_queue, file_handler,
            )
            log_listener.start()

            atexit.register(shutdown_logging)

            log_session_header()

    else:
        logging.disable(logging.CRITICAL)


def shutdown_logging() -> None:
    """Shut down logging handlers and queue listener."""
    global log_listener  # noqa: PLW0603

    if log_listener:
        log_listener.stop()
        log_listener = None
