import atexit
import logging
import logging.config
import logging.handlers
import queue
import threading
from pathlib import Path

from term_timer.config import DEBUG

LOGGING_DIR = Path(__file__).parent.parent / 'logs'

LOGGING_FILE = 'term-timer.log'

LOGGING_PATH = LOGGING_DIR / LOGGING_FILE


class DbusSignalFilter(logging.Filter):
    def filter(self, record) -> bool:
        return record.funcName not in {'_parse_msg', 'write_gatt_char'}


class AsyncioLogHandler(logging.handlers.QueueHandler):

    def __init__(self, log_queue):
        super().__init__(log_queue)


class AsyncioLogListener:

    def __init__(self, queue, handler):
        self.queue = queue
        self.handler = handler
        self._stop_event = threading.Event()
        self._thread = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._process_logs)
        self._thread.daemon = True
        self._thread.start()

    def stop(self) -> None:
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


LOGGING_CONF = {
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

log_listener = None


def configure_logging() -> None:
    if DEBUG:
        Path(LOGGING_DIR).mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(LOGGING_CONF)

        root_logger = logging.getLogger()
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        if file_handler:
            root_logger.removeHandler(file_handler)

            log_queue = queue.Queue()
            queue_handler = AsyncioLogHandler(log_queue)
            root_logger.addHandler(queue_handler)

            log_listener = AsyncioLogListener(log_queue, file_handler)
            log_listener.start()

            atexit.register(shutdown_logging)

    else:
        logging.disable(logging.INFO)


def shutdown_logging() -> None:
    global log_listener  # noqa PLW0603

    if log_listener:
        log_listener.stop()
        log_listener = None
