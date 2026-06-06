"""Configuration loading and management from TOML files."""
import os
from typing import Any
from typing import Final

import rtoml

from term_timer.constants import CONFIG_FILE

DEFAULT_CONFIG: Final = """[timer]
sound = "audio"
countdown = 0.0
metronome = 0.0
steps = true

[cube]
orientation = "DF"
method = "cf4op"
palette = "default"
effect = "face-visible"
style = "default"
linear = false
right-handed = true

[trainer]
fsrs = true
step = "oll"
ecross-difficulty = "normal"
xcross-difficulty = "normal"
xcross-slots = ["FR"]

[display]
scramble = true
reconstruction = true
highlights = true
doctor = true
time_graph = true
tps_graph = true
fluency_graph = true
recognition_graph = true

[bluetooth]
name = ""
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
    """
    Load configuration from TOML file or create default.

    Returns:
        Dictionary containing configuration settings.

    """
    if not CONFIG_FILE.exists():
        with CONFIG_FILE.open('w+', encoding='utf-8') as fd:
            fd.write(DEFAULT_CONFIG)

        return rtoml.loads(DEFAULT_CONFIG)

    return rtoml.load(CONFIG_FILE)


CONFIG = load_config()

STATS_CONFIG = CONFIG.get('statistics', {})

TIMER_CONFIG = CONFIG.get('timer', {})

TIMER_SOUND: str = TIMER_CONFIG.get('sound', 'audio')

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

CUBE_STYLE: str = CUBE_CONFIG.get('style', '')

CUBE_LINEAR: bool = CUBE_CONFIG.get('linear', False)

CUBE_RIGHT_HANDED: bool = CUBE_CONFIG.get('right-handed', True)

DEVICE_NAME: str = BLUETOOTH_CONFIG.get('name', '')

DEVICE_ADDRESS: str = BLUETOOTH_CONFIG.get('address', '')

USE_GYROSCOPE: bool = BLUETOOTH_CONFIG.get('use_gyroscope', True)

ROTATION_THRESHOLD: float = BLUETOOTH_CONFIG.get('rotation_threshold', 75.0)

TRAINER_FSRS: bool = TRAINER_CONFIG.get('fsrs', True)

TRAINER_STEP = TRAINER_CONFIG.get('step')

TRAINER_ECROSS_DIFFICULTY: str = TRAINER_CONFIG.get(
    'ecross-difficulty', 'normal',
)

TRAINER_XCROSS_DIFFICULTY: str = TRAINER_CONFIG.get(
    'xcross-difficulty', 'normal',
)

TRAINER_XCROSS_SLOTS: list[str] = TRAINER_CONFIG.get('xcross-slots', ['FR'])

DEBUG = bool(os.getenv('TERM_TIMER_DEBUG', None))
