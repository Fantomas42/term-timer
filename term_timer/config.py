"""Configuration loading and management from TOML files."""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Final
from typing import cast

import rtoml

from term_timer.constants import CONFIG_FILE
from term_timer.constants import CONFIG_FILE_FROM_ENV

SERIES_RE: Final = re.compile(r'^(mo|ao|mb|mw)(\d+)$')

# Selector disabling the Bluetooth cube entirely
CUBE_SELECTOR_OFF: Final = 'off'

# Selector forcing a scan accepting any cube, configured or not
CUBE_SELECTOR_AUTO: Final = 'auto'

CUBE_SELECTORS: Final = (CUBE_SELECTOR_OFF, CUBE_SELECTOR_AUTO)

# Bleak exposes a MAC address on Linux and Windows, but a system UUID
# on macOS, so both spellings are accepted wherever an address is read
MAC_ADDRESS_RE: Final = re.compile(
    r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$', re.IGNORECASE,
)

UUID_ADDRESS_RE: Final = re.compile(
    r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$', re.IGNORECASE,
)

# Kinds accepted in any configurable series
SERIES_KINDS: Final = ('mo', 'ao', 'mb', 'mw')

# Kinds meaningful as rolling averages (session table and live line):
# their best counterparts (best_mo/best_ao) exist for record tracking
SERIES_AVERAGE_KINDS: Final = ('mo', 'ao')

DEFAULT_CONFIG: Final = """[timer]
motto = "Go Go Go:"
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
fsrs-rating = "auto"
step = "oll"
ecross-difficulty = "normal"
xcross-difficulty = "normal"
xcross-slots = ["FR"]

[display]
banner = true
scramble = true
reconstruction = true
highlights = true
doctor = true
time_graph = true
tps_graph = true
fluency_graph = true
recognition_graph = true

[bluetooth]
default = ""
use_gyroscope = true
rotation_threshold = 75.0

# Declare one table per cube, then select one with -b <label>
# [bluetooth.cubes.gan12]
# name = "GAN 12 ui FreePlay"
# address = "AA:BB:CC:DD:EE:FF"

[statistics]
trim = "p5"
distribution = 0
solve_metrics = ["htm", "qtm", "stm"]
ao_projections = []
live_series = ["mo3", "ao5", "ao12"]
session_series = ["mo3", "ao5", "ao12", "ao100", "ao1000"]
graph_series = ["ao5", "ao12", "ao100", "ao1000"]

[server]
domain = "localhost"
port = 8333

[publisher]
active = false
endpoints = [
  "ipc://~/.term_timer/cube.ipc",
  "tcp://127.0.0.1:5333",
]

[ui]

"""


def parse_series(
        tokens: list[str],
        kinds: tuple[str, ...] = SERIES_KINDS,
) -> list[tuple[str, int]]:
    """
    Parse configurable series tokens into kind/size pairs.

    Each token is a kind (``mo``, ``ao``, ``mb`` or ``mw``) followed by
    an integer size (e.g. ``ao5``, ``mb3``), per ``SERIES_RE``. The order
    given by the user is preserved as-is; duplicates are dropped on their
    first occurrence and unrecognised tokens are silently ignored. Tokens
    whose kind is not in ``kinds`` are also ignored, which lets callers
    restrict a series to a subset (e.g. only ``mo``/``ao``).

    Shared by every configurable series: trend graphs, the session table
    and the per-solve live line.

    Args:
        tokens: Raw series tokens from the configuration.
        kinds: Kinds to accept; defaults to every supported kind.

    Returns:
        List of ``(kind, size)`` pairs, kept in their original order.

    """
    series: list[tuple[str, int]] = []
    seen: set[str] = set()

    for token in tokens:
        match = SERIES_RE.match(str(token).strip().lower())
        if match is None:
            continue

        kind = match.group(1)
        if kind not in kinds:
            continue

        size = int(match.group(2))
        key = f'{ kind }{ size }'
        if key in seen:
            continue

        seen.add(key)
        series.append((kind, size))

    return series


def parse_endpoints(tokens: list[str]) -> list[str]:
    """
    Parse the endpoints the event publisher binds.

    Each token is a ZeroMQ endpoint, ``<transport>://<address>``. The
    address of an ``ipc`` endpoint is a file path, so its leading ``~``
    is expanded: the configuration file is written by hand and a literal
    tilde would be taken as a directory name.

    Tokens carrying no transport are ignored rather than handed to
    ZeroMQ, and duplicates are dropped: binding the same endpoint twice
    is an error the publisher has no reason to report.

    Args:
        tokens: Raw endpoints from the configuration.

    Returns:
        The endpoints to bind, in the order the file lists them.

    """
    endpoints: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        transport, separator, address = str(token).strip().partition('://')
        if not separator or not address:
            continue

        if transport == 'ipc':
            address = str(Path(address).expanduser())

        endpoint = f'{ transport }://{ address }'
        if endpoint in seen:
            continue

        seen.add(endpoint)
        endpoints.append(endpoint)

    return endpoints


def env_flag(name: str, *, default: bool = False) -> bool:
    """
    Read a boolean flag from the environment.

    Accepts the usual truthy and falsy spellings so that an explicit
    ``0``, ``false`` or ``no`` really disables the flag instead of being
    read as "the variable is set".

    Args:
        name: Environment variable name.
        default: Value returned when the variable is unset or empty.

    Returns:
        The boolean value carried by the environment variable.

    """
    value = os.getenv(name)
    if value is None or not value.strip():
        return default

    return value.strip().lower() not in {'0', 'false', 'no', 'off'}


def env_string(name: str, default: str) -> str:
    """
    Read a string setting from the environment.

    An unset or empty variable falls back to the default, so that
    exporting an empty value never blanks a setting. The value is
    returned verbatim: its spacing can be meaningful.

    Args:
        name: Environment variable name.
        default: Value returned when the variable is unset or empty.

    Returns:
        The string value carried by the environment variable.

    """
    return os.getenv(name) or default


def load_config() -> dict[str, Any]:
    """
    Load configuration from TOML file or create default.

    Returns:
        Dictionary containing configuration settings.

    Raises:
        FileNotFoundError: If TERM_TIMER_CONFIG points to a missing file.

    """
    if not CONFIG_FILE.exists():
        if CONFIG_FILE_FROM_ENV:
            msg = (
                f'TERM_TIMER_CONFIG points to a missing file: {CONFIG_FILE}'
            )
            raise FileNotFoundError(msg)

        with CONFIG_FILE.open('w+', encoding='utf-8') as fd:
            fd.write(DEFAULT_CONFIG)

        return rtoml.loads(DEFAULT_CONFIG)

    return rtoml.load(CONFIG_FILE)


CONFIG = load_config()

STATS_CONFIG = CONFIG.get('statistics', {})

STATS_TRIM: str = str(STATS_CONFIG.get('trim', 'p5'))

STATS_DISTRIBUTION: int = STATS_CONFIG.get('distribution', 0)

STATS_SOLVE_METRICS: list[str] = STATS_CONFIG.get(
    'solve_metrics', ['htm', 'qtm', 'stm'],
)

STATS_AO_PROJECTIONS: list[int] = STATS_CONFIG.get('ao_projections', [])

STATS_LIVE_SERIES: list[tuple[str, int]] = parse_series(
    STATS_CONFIG.get('live_series', ['mo3', 'ao5', 'ao12']),
    SERIES_AVERAGE_KINDS,
)

STATS_SESSION_SERIES: list[tuple[str, int]] = parse_series(
    STATS_CONFIG.get(
        'session_series', ['mo3', 'ao5', 'ao12', 'ao100', 'ao1000'],
    ),
    SERIES_AVERAGE_KINDS,
)

STATS_GRAPH_SERIES: list[tuple[str, int]] = parse_series(
    STATS_CONFIG.get('graph_series', ['ao5', 'ao12', 'ao100', 'ao1000']),
)


TIMER_CONFIG = CONFIG.get('timer', {})

TIMER_SOUND: str = env_string(
    'TERM_TIMER_SOUND',
    str(TIMER_CONFIG.get('sound', 'audio')),
)

# The motto carries its own separator, so that a custom one is free to
# drop the colon or to be an emoji. Its padding is meaningful too and
# is never stripped: it is what aligns the column.
TIMER_MOTTO: str = env_string(
    'TERM_TIMER_MOTTO',
    str(TIMER_CONFIG.get('motto', 'Go Go Go:')),
)

DISPLAY_CONFIG = CONFIG.get('display', {})

DISPLAY_BANNER: bool = (
    DISPLAY_CONFIG.get('banner', True)
    and not env_flag('TERM_TIMER_NO_BANNER')
)

UI_CONFIG = CONFIG.get('ui', {})

BLUETOOTH_CONFIG = CONFIG.get('bluetooth', {})

CUBE_CONFIG = CONFIG.get('cube', {})

TRAINER_CONFIG = CONFIG.get('trainer', {})

SERVER_CONFIG = CONFIG.get('server', {})

PUBLISHER_CONFIG = CONFIG.get('publisher', {})

CUBE_ORIENTATION: str = CUBE_CONFIG.get('orientation', '')

CUBE_METHOD: str = CUBE_CONFIG.get('method', '')

CUBE_PALETTE: str = CUBE_CONFIG.get('palette', '')

CUBE_EFFECT: str = CUBE_CONFIG.get('effect', '')

CUBE_STYLE: str = CUBE_CONFIG.get('style', '')

CUBE_LINEAR: bool = CUBE_CONFIG.get('linear', False)

CUBE_RIGHT_HANDED: bool = CUBE_CONFIG.get('right-handed', True)

USE_GYROSCOPE: bool = BLUETOOTH_CONFIG.get('use_gyroscope', True)

ROTATION_THRESHOLD: float = BLUETOOTH_CONFIG.get('rotation_threshold', 75.0)


def is_cube_address(value: str) -> bool:
    """
    Tell whether a selector spells a Bluetooth address.

    Args:
        value: Raw selector given on the command line or in a routine.

    Returns:
        True for a MAC address or a macOS device UUID.

    """
    return bool(
        MAC_ADDRESS_RE.match(value) or UUID_ADDRESS_RE.match(value),
    )


@dataclass(frozen=True)
class CubeDevice:
    """
    A Bluetooth cube the application may connect to.

    A device carries both its identity and the settings that vary from
    one cube to the next, so that owning several cubes never requires
    editing the configuration between two sessions.

    An empty ``address`` means the cube is still to be discovered: the
    connection scans instead of dialing an address directly.

    Attributes:
        label: Short key naming the cube in the configuration and on the
            command line.
        name: Human readable name, only ever displayed.
        address: MAC address, or system UUID on macOS. Empty to scan.
        use_gyroscope: Whether the driver should use gyroscope data.
        rotation_threshold: Gyroscope rotation detection threshold.
        prefer_known: Whether a scan should favour a configured cube over
            any other cube it discovers.

    """

    label: str = ''
    name: str = ''
    address: str = ''
    use_gyroscope: bool = True
    rotation_threshold: float = 75.0
    prefer_known: bool = True

    @classmethod
    def from_config(cls, label: str, data: dict[str, Any]) -> 'CubeDevice':
        """
        Build a cube from its configuration table.

        Settings left out of the cube table fall back on the global
        Bluetooth settings.

        Args:
            label: Key naming the cube in the configuration.
            data: Contents of the cube table.

        Returns:
            The configured cube.

        """
        return cls(
            label=label,
            name=str(data.get('name', '')),
            address=str(data.get('address', '')),
            use_gyroscope=bool(
                data.get('use_gyroscope', USE_GYROSCOPE),
            ),
            rotation_threshold=float(
                data.get('rotation_threshold', ROTATION_THRESHOLD),
            ),
        )

    @classmethod
    def discovered(cls, label: str = '', *, prefer_known: bool) -> 'CubeDevice':
        """
        Build a cube left to be discovered by a scan.

        Args:
            label: Key naming the cube, empty when scanning.
            prefer_known: Whether the scan favours a configured cube.

        Returns:
            An address-less cube carrying the global settings.

        """
        return cls(
            label=label,
            use_gyroscope=USE_GYROSCOPE,
            rotation_threshold=ROTATION_THRESHOLD,
            prefer_known=prefer_known,
        )

    @staticmethod
    def clean_selector(value: str) -> str:
        """
        Normalise a cube selector, rejecting what names no cube.

        Args:
            value: Raw selector from the command line or a routine file.

        Returns:
            The selector, lowercased when it names a configured cube or a
            reserved keyword, empty when it reaches nothing.

        """
        selector = value.strip()

        if selector.lower() in CUBE_SELECTORS:
            return selector.lower()

        if selector.lower() in BLUETOOTH_CUBES:
            return selector.lower()

        if is_cube_address(selector):
            return selector

        return ''

    @classmethod
    def resolve(cls, selector: str | None) -> 'CubeDevice | None':
        """
        Resolve a cube selector into the cube to connect to.

        The selector comes from the ``-b`` option or from a routine file.
        ``None`` means nothing was asked for and the configuration
        decides: the default cube when one is designated, the only
        configured cube when there is a single one, a scan restricted to
        the configured cubes when several are listed, and no cube at all
        when none is configured.

        Args:
            selector: Cube label, address, ``auto``, ``off``, or None.

        Returns:
            The cube to connect to, or None when Bluetooth stays off.

        """
        if selector == CUBE_SELECTOR_OFF:
            return None

        if selector == CUBE_SELECTOR_AUTO:
            return cls.discovered(CUBE_SELECTOR_AUTO, prefer_known=False)

        if selector:
            return BLUETOOTH_CUBES.get(selector.lower()) or cls(
                label=selector,
                address=selector,
                use_gyroscope=USE_GYROSCOPE,
                rotation_threshold=ROTATION_THRESHOLD,
            )

        if BLUETOOTH_DEFAULT:
            return BLUETOOTH_CUBES[BLUETOOTH_DEFAULT]

        if BLUETOOTH_CUBES:
            return cls.discovered(prefer_known=True)

        return None

    @property
    def display_name(self) -> str:
        """Get the most telling name known before the cube answers."""
        return self.name or self.label or self.address

    @property
    def scan_addresses(self) -> tuple[str, ...]:
        """Get the addresses a scan favours, empty to take any cube."""
        if not self.prefer_known:
            return ()

        return tuple(
            cube.address
            for cube in BLUETOOTH_CUBES.values()
            if cube.address
        )

    @staticmethod
    def adopt(address: str) -> 'CubeDevice | None':
        """
        Find the configured cube answering at an address.

        A scan may land on any of the configured cubes, so the settings
        of the one actually discovered take over those of the placeholder
        the scan started from.

        Args:
            address: Address of the discovered device.

        Returns:
            The configured cube at that address, None when unknown.

        """
        for cube in BLUETOOTH_CUBES.values():
            if cube.address and cube.address.lower() == address.lower():
                return cube

        return None


def load_cubes(config: dict[str, Any]) -> dict[str, CubeDevice]:
    """
    Load the configured Bluetooth cubes, keyed by label.

    Cubes are read from the ``[bluetooth.cubes.<label>]`` tables.

    Args:
        config: Contents of the ``[bluetooth]`` table.

    Returns:
        The configured cubes, in the order the file lists them.

    """
    configured: dict[str, Any] = config.get('cubes', {})

    cubes: dict[str, CubeDevice] = {}
    for label, data in configured.items():
        if not isinstance(data, dict):
            continue

        key = str(label).lower()
        cubes[key] = CubeDevice.from_config(
            key, cast('dict[str, Any]', data),
        )

    return cubes


def load_default_cube(
        config: dict[str, Any],
        cubes: dict[str, CubeDevice],
) -> str:
    """
    Resolve the label of the cube to connect to by default.

    A cube designated by the ``default`` key wins. Failing that, a lone
    configured cube is its own default, which keeps a single-cube setup
    dialing its address directly instead of scanning. Several cubes with
    no designated default leave the choice to the scan.

    Args:
        config: Contents of the ``[bluetooth]`` table.
        cubes: The configured cubes, keyed by label.

    Returns:
        The default cube label, empty when there is none.

    """
    default = str(config.get('default', '')).lower()

    if default in cubes:
        return default

    if len(cubes) == 1:
        return next(iter(cubes))

    return ''


BLUETOOTH_CUBES: dict[str, CubeDevice] = load_cubes(BLUETOOTH_CONFIG)

BLUETOOTH_DEFAULT: str = load_default_cube(BLUETOOTH_CONFIG, BLUETOOTH_CUBES)

TRAINER_FSRS: bool = TRAINER_CONFIG.get('fsrs', True)

TRAINER_FSRS_RATING: str = TRAINER_CONFIG.get('fsrs-rating', 'auto')

TRAINER_STEP = TRAINER_CONFIG.get('step')

TRAINER_ECROSS_DIFFICULTY: str = TRAINER_CONFIG.get(
    'ecross-difficulty', 'normal',
)

TRAINER_XCROSS_DIFFICULTY: str = TRAINER_CONFIG.get(
    'xcross-difficulty', 'normal',
)

TRAINER_XCROSS_SLOTS: list[str] = TRAINER_CONFIG.get('xcross-slots', ['FR'])

# Publication stays off unless asked for: a session never depends on it
PUBLISHER_ACTIVE: bool = env_flag(
    'TERM_TIMER_PUBLISH',
    default=bool(PUBLISHER_CONFIG.get('active', False)),
)

# No endpoint configured means nothing to bind, hence nothing published:
# the endpoints are named by the configuration file and by it only
PUBLISHER_ENDPOINTS: list[str] = parse_endpoints(
    PUBLISHER_CONFIG.get('endpoints', []),
)

DEBUG: bool = env_flag('TERM_TIMER_DEBUG')
