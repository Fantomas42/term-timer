"""Application-wide constants and type definitions."""
import os
from pathlib import Path
from typing import Final
from typing import Literal
from typing import NamedTuple

from cubing_algs.cases.case import Case
from cubing_algs.cases.case import CaseData

SECOND: Final = 1_000_000_000  # In nano seconds

MS_TO_NS_FACTOR: Final = 1_000_000

PAUSE_FACTOR: Final = 2

# Minimum number of solves to aggregate before spawning a process pool.
# Below it the fork cost exceeds the analysis itself, and a session round
# would fork while an asyncio loop and a BLE connection are running.
MULTIPROCESSING_MIN_SOLVES: Final = 16

# Minimum number of prior connected solves required to draw session-end
# doctor trend markers. The comparison baseline is max(round size, this),
# so short rounds still contrast against a stable reference; when fewer
# than this many prior solves exist, no trend is shown at all.
DOCTOR_SESSION_BASELINE_MIN: Final = 12

# Stability (days) past which a case is considered anchored in long-term
# muscle memory. Used both as the FSRS mastery threshold (fsrs/scheduler.py)
# and as the floor protecting clean-but-slow reps from a speed-driven Again.
STABILITY_LONG_TERM_DAYS: Final = 14.0

# Card states of the recap table, ordered as a learning funnel from
# never seen to consolidated. Labels come from fsrs_state_label(), which
# splits the FSRS Review state into Review (due) and Stable (scheduled).
FSRS_STATE_LABELS: Final[tuple[str, ...]] = (
    'New', 'Learning', 'Relearning', 'Review', 'Stable',
)

# Same states as accepted on the command line by "train --state".
FSRS_STATE_CHOICES: Final[tuple[str, ...]] = tuple(
    label.lower() for label in FSRS_STATE_LABELS
)

STEP_BAR: Final = 17

# Maximum number of average curves drawn on the console trend graph
# (in addition to the always-plotted Time curve).
GRAPH_CONSOLE_LIMIT: Final = 2

# Per-token plotext colors for the console trend graph, with a fallback
# for tokens without a dedicated color.
GRAPH_CONSOLE_COLORS: Final = {
    'ao5': 196,
    'ao12': 119,
    'ao100': 244,
    'ao1000': 231,
}
GRAPH_CONSOLE_FALLBACK: Final = 213

WEEK_DAYS: Final = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

MONTH_INITIALS: Final = 'JFMAMJJASOND'

# A full block filling its cell, twice per week so the punchcard reads as
# squares. Weeks are capped to keep the widest grid under 80 characters,
# the missed and blank cells matching the width of a played one.
PUNCHCARD_CELL: Final = '██'
PUNCHCARD_WEEKS: Final = 38

PUNCHCARD_LEVELS: Final = (1, 2, 4, 6)
PUNCHCARD_STYLES: Final = (
    'punchcard-1',
    'punchcard-2',
    'punchcard-3',
    'punchcard-4',
)

DAILY_DAYS_LISTED: Final = 14

RESUME_LABEL_WIDTH: Final = 6
RESUME_VALUE_WIDTH: Final = 13

STEP_DELTA_WIDTH: Final = 6
GHOST_SPLIT_WIDTH: Final = 6
GHOST_DELTA_WIDTH: Final = 6
GHOST_EMOJI: Final = '👻'

TT_DIRECTORY: Final = Path(
    os.getenv(
        'TERM_TIMER_HOME',
        str(Path.home() / '.term_timer'),
    ),
)

SOLVES_DIRECTORY: Final = TT_DIRECTORY / 'solves'

DAILY_DIRECTORY: Final = SOLVES_DIRECTORY / 'daily'

GHOSTS_DIRECTORY: Final = SOLVES_DIRECTORY / 'ghosts'

TRAININGS_DIRECTORY: Final = TT_DIRECTORY / 'trainings'

ROUTINES_DIRECTORY: Final = TT_DIRECTORY / 'routines'

LOGGING_DIRECTORY: Final = TT_DIRECTORY / 'logs'

CONFIG_FILE_ENV: Final = os.getenv('TERM_TIMER_CONFIG')

# A config path given by the environment is never created on the fly:
# a missing file there means a misconfiguration, not a first run.
CONFIG_FILE_FROM_ENV: Final = bool(CONFIG_FILE_ENV)

CONFIG_FILE: Final = (
    Path(CONFIG_FILE_ENV).expanduser()
    if CONFIG_FILE_ENV
    else TT_DIRECTORY / 'config.toml'
)

# Version of the published event protocol. Bumped only when a topic or
# a field is renamed or removed: adding either never breaks a client.
PROTOCOL_VERSION: Final = 1

# Send buffer of the PUB socket, in messages. Set wide on purpose: the
# stream peaks at a few dozen messages per second, so reaching it means
# a subscriber stopped reading entirely, which is an incident already.
PUBLISH_HIGH_WATER_MARK: Final = 10_000

# How long a subscriber waits on the socket before looking at its own
# state again, in milliseconds. It is what a reader loop costs to stop:
# short enough to close a window without a pause, long enough to leave
# an idle stream alone.
STREAM_POLL_TIMEOUT: Final = 200

TEMPLATES_DIRECTORY: Final = Path(__file__).parent / 'server' / 'templates'

STATIC_DIRECTORY: Final = Path(__file__).parent / 'server' / 'static'

DNF: Final = 'DNF'

PLUS_TWO: Final = '+2'

CUBE_SIZES: Final = list(range(2, 8))

SECOND_BINS: Final = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]

REFRESH: Final = 0.01

BLUETOOTH_CONSUMER_STOP_TIMEOUT: Final = 2.0

# Guard against a hung D-Bus call while tearing the BLE link down.
# Kept above the 10s bleak waits internally for the disconnection to
# be signaled, so a healthy teardown is never truncated
BLUETOOTH_DISCONNECT_TIMEOUT: Final = 12.0

RESLICE_THRESHOLD: Final = 70

RESLICE_THRESHOLD_GYROSCOPE: Final = 120

REWIDE_THRESHOLD_GYROSCOPE: Final = 180

ESCAPE_CHAR: Final = '\x1b'

HELP_CHAR: Final = '?'


class Command(NamedTuple):
    """One command of the save prompt, keyboard side and cube side."""

    short: str
    label: str
    keyboard: str
    cube: str
    group: str


# Commands of the save prompt. `short` builds the one line kept on
# screen, the other fields the block the help key unfolds. An empty
# `short` means the command is already carried by the prompt lead, an
# empty `cube` that no gesture triggers it. Cube gestures are two moves
# of the same face undoing each other, see interface/gesture.py.
# `group` gathers the commands answering the same question: consecutive
# commands sharing it are rendered together, the groups apart. It is a
# property of the command, not of the prompt, so a command keeps its
# neighbours wherever it is offered.
COMMANDS: Final[dict[str, Command]] = {
    'rate': Command(
        '1-4', 'Rate', '1/2/3/4', '', 'rate',
    ),
    'dnf': Command(
        'd', 'Set DNF & continue', 'd', '', 'flag',
    ),
    'plus_two': Command(
        '2', 'Set +2 & continue', '2', '', 'flag',
    ),
    'retry': Command(
        'r', 'Discard & retry', 'r', '', 'cancel',
    ),
    'quit': Command(
        'k', 'Discard & quit', 'k', 'E', 'cancel',
    ),
    'discard': Command(
        'z', 'Discard & continue', 'z', 'M S', 'cancel',
    ),
    'save_quit': Command(
        'q', 'Save & quit', 'q/Esc', 'D', 'exit',
    ),
    'save': Command(
        '', 'Save & continue', 'any key', 'U R F L B', 'save',
    ),
    'help': Command(
        HELP_CHAR, 'Help', HELP_CHAR, '', 'help',
    ),
}

FLUENCY_EXPONENTIAL_DECAY: Final = -0.00111571775657105

FLUENCY_LOW_THRESHOLD: Final = 55
FLUENCY_MEDIUM_THRESHOLD: Final = 60

FLUENCY_STEP_LOW_THRESHOLD: Final = 65
FLUENCY_STEP_MEDIUM_THRESHOLD: Final = 75

Face = Literal['U', 'D', 'R', 'L', 'F', 'B']

SolveFlag = Literal['', 'DNF', '+2']

SolveFlagInput = Literal['OK', 'DNF', '+2']

CROSS_CASE = Case(
    '', 'Cross',
    CaseData(
        name='Cross',
        code='cross',
    ),
)

EASY_CROSS_CASE = Case(
    '', 'Easy Cross',
    CaseData(
        name='Easy Cross',
        code='ecross',
    ),
)

X_CROSS_CASE = Case(
    '', 'X-Cross',
    CaseData(
        name='X-Cross',
        code='xcross',
    ),
)

LL_CASE = Case(
    '', 'LL',
    CaseData(
        name='LL',
        code='ll',
    ),
)

for directory in (
        SOLVES_DIRECTORY,
        DAILY_DIRECTORY,
        GHOSTS_DIRECTORY,
        TRAININGS_DIRECTORY,
        ROUTINES_DIRECTORY,
        LOGGING_DIRECTORY,
):
    directory.mkdir(parents=True, exist_ok=True)
