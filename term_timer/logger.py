import logging
import logging.config
from datetime import datetime
from datetime import timezone
from pathlib import Path

from term_timer.config import DEBUG

LOGGING_DIR = Path(__file__).parent.parent / 'logs'

LOGGING_FILE = datetime.now(
    tz=timezone.utc,  # noqa: UP017
).strftime('%Y%m%d_%H%M%S') + '.log'

LOGGING_PATH = LOGGING_DIR / LOGGING_FILE

LOGGING_CONF = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'class': 'logging.Formatter',
            'format': (
                '%(levelname)-8s; [%(process)d]; %(threadName)s; %(name)s; '
                '%(module)s:%(funcName)s;%(lineno)d: %(message)s'
            ),
        },
    },
    'handlers': {
        'fileHandler': {
            'formatter': 'verbose',
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': LOGGING_PATH,
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
