import os
from importlib.util import find_spec
from typing import Any
from typing import Final

from term_timer.constants import CONFIG_FILE

if find_spec('tomllib') is not None:
    import tomllib
else:
    import pip._vendor.tomli as tomllib  # type: ignore[import-not-found, no-redef] # noqa: PLC2701


DEFAULT_CONFIG: Final = """[timer]
countdown = 0.0
metronome = 0.0

[cube]
orientation = "DF"
method = "cf4op"
palette = ""
effect = "face-visible"
right-handed = true

[trainer]
step = "oll"

[display]
scramble = true
reconstruction = true
time_graph = true
tps_graph = true
recognition_graph = true

[bluetooth]
address = ""
use_gyroscope = true
rotation_threshold = 75.0

[statistics]
distribution = 0
metrics = ["htm", "qtm", "stm"]

[server]
domain = "localhost"
port = 8333

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

DISPLAY_CONFIG = CONFIG.get('display', {})

UI_CONFIG = CONFIG.get('ui', {})

BLUETOOTH_CONFIG = CONFIG.get('bluetooth', {})

CUBE_CONFIG = CONFIG.get('cube', {})

TRAINER_CONFIG = CONFIG.get('trainer', {})

SERVER_CONFIG = CONFIG.get('server', {})

CUBE_ORIENTATION: str = CUBE_CONFIG.get('orientation', '')

CUBE_METHOD: str = CUBE_CONFIG.get('method', '')

CUBE_PALETTE: str = CUBE_CONFIG.get('palette', '')

CUBE_EFFECT: str = CUBE_CONFIG.get('effect', '')

CUBE_RIGHT_HANDED: bool = CUBE_CONFIG.get('right-handed', True)

USE_GYROSCOPE: bool = BLUETOOTH_CONFIG.get('use_gyroscope', True)

ROTATION_THRESHOLD: float = BLUETOOTH_CONFIG.get('rotation_threshold', 75.0)

TRAINER_STEP = TRAINER_CONFIG.get('step')

DEBUG = bool(os.getenv('TERM_TIMER_DEBUG', None))
