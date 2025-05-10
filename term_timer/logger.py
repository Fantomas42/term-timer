import logging
import logging.config
from pathlib import Path

from term_timer.config import DEBUG

LOGGING_DIR = Path(__file__).parent.parent / 'logs'

LOGGING_FILE = 'term-timer.log'

LOGGING_PATH = LOGGING_DIR / LOGGING_FILE


class DbusSignalFilter(logging.Filter):
    def filter(self, record):
        return record.funcName not in {'_parse_msg', 'write_gatt_char'}


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


def configure_logging() -> None:
    if DEBUG:
        Path(LOGGING_DIR).mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(LOGGING_CONF)
    else:
        logging.disable(logging.INFO)
