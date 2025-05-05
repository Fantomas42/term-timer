import os
from importlib.util import find_spec
from typing import Any

from cubing_algs.parsing import parse_moves

from term_timer.constants import CONFIG_FILE

if find_spec('tomllib') is not None:
    import tomllib
else:
    import pip._vendor.tomli as tomllib  # type: ignore[import-not-found, no-redef] # noqa: PLC2701


DEFAULT_CONFIG = """[timer]
countdown = 0.0
metronome = 0.0

[cube]
orientation = []
method = "cf4op"

[statistics]
distribution = 0
metrics = ["htm", "qtm", "stm"]

[ui]

"""


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        with CONFIG_FILE.open('w+') as fd:
            fd.write(DEFAULT_CONFIG)

        return tomllib.loads(DEFAULT_CONFIG)

    with CONFIG_FILE.open('rb') as fd:
        return tomllib.load(fd)


CONFIG = load_config()

STATS_CONFIG = CONFIG.get('statistics', {})

TIMER_CONFIG = CONFIG.get('timer', {})

UI_CONFIG = CONFIG.get('ui', {})

CUBE_CONFIG = CONFIG.get('cube', {})

CUBE_ORIENTATION = parse_moves(
    CUBE_CONFIG.get('orientation'),
)

CUBE_METHOD = CUBE_CONFIG.get('method')

DEBUG = bool(os.getenv('TERM_TIMER_DEBUG', None))
