"""Splash screen banner with a time-of-day color palette."""
from datetime import UTC
from datetime import datetime
from pathlib import Path

from rich.text import Text

from term_timer import __version__
from term_timer.interface.console import console

RESET = '\033[0m'

GIT_DIR = Path(__file__).resolve().parent.parent / '.git'
SHORT_HASH_LENGTH = 7

TERM_LINES = [
    '  ______',
    ' /_  __/__  _________ ___',
    '  / / / _ \\/ ___/ __ `__ \\',
    ' / / /  __/ /  / / / / / /',
    '/_/  \\___/_/  /_/ /_/ /_/',
]

TIMER_LINES = [
    '  ______',
    ' /_  __(_)___ ___  ___  _____',
    '  / / / / __ `__ \\/ _ \\/ ___/',
    ' / / / / / / / / /  __/ /',
    '/_/ /_/_/ /_/ /_/\\___/_/',
]

WORD_GAP = 1

LOGO_LINES = [
    term.ljust(max(len(line) for line in TERM_LINES) + WORD_GAP) + timer
    for term, timer in zip(TERM_LINES, TIMER_LINES, strict=True)
]

# Diagonal 256-color ramps, one per time of day
NIGHT_RAMP = (27, 63, 99, 135, 171, 207, 201)
MORNING_RAMP = (199, 205, 211, 217, 195, 123, 51)
AFTERNOON_RAMP = (226, 220, 214, 208, 204, 199, 165, 129)
EVENING_RAMP = (51, 45, 39, 69, 99, 135, 171, 201)

MORNING_START = 6
AFTERNOON_START = 12
EVENING_START = 18
NIGHT_START = 22

GRADIENT_SLOPE = 3


def palette_for_hour(hour: int) -> tuple[int, ...]:
    """
    Select the color ramp matching an hour of the day.

    Args:
        hour: Hour of the day (0-23).

    Returns:
        The 256-color ramp of the corresponding time of day.

    """
    if MORNING_START <= hour < AFTERNOON_START:
        return MORNING_RAMP
    if AFTERNOON_START <= hour < EVENING_START:
        return AFTERNOON_RAMP
    if EVENING_START <= hour < NIGHT_START:
        return EVENING_RAMP
    return NIGHT_RAMP


def colorize(lines: list[str], ramp: tuple[int, ...]) -> str:
    """
    Apply a diagonal 256-color gradient to text lines.

    Args:
        lines: Text lines to colorize.
        ramp: 256-color indexes of the gradient.

    Returns:
        ANSI-colorized text.

    """
    width = max(len(line) for line in lines)
    colorized = []
    for row, line in enumerate(lines):
        parts = []
        for col, char in enumerate(line):
            if char == ' ':
                parts.append(char)
                continue
            position = col + row * GRADIENT_SLOPE
            index = max(
                0, min(position * len(ramp) // width, len(ramp) - 1),
            )
            parts.append(f'\033[38;5;{ ramp[index] }m{ char }')
        parts.append(RESET)
        colorized.append(''.join(parts))
    return '\n'.join(colorized)


def get_commit_hash() -> str | None:
    """
    Read the short hash of the current commit for git installations.

    The git refs are read directly from the .git directory to avoid
    spawning an external process. Both loose and packed refs are
    supported.

    Returns:
        The short commit hash, or None if not installed from git.

    """
    head = GIT_DIR / 'HEAD'
    try:
        content = head.read_text().strip()
    except OSError:
        return None

    if not content.startswith('ref:'):
        return content[:SHORT_HASH_LENGTH] or None

    ref = content.removeprefix('ref:').strip()

    loose = GIT_DIR / ref
    try:
        return loose.read_text().strip()[:SHORT_HASH_LENGTH] or None
    except OSError:
        pass

    packed = GIT_DIR / 'packed-refs'
    try:
        lines = packed.read_text().splitlines()
    except OSError:
        return None

    for line in lines:
        if line.startswith(('#', '^')):
            continue
        commit, _, name = line.partition(' ')
        if name == ref:
            return commit[:SHORT_HASH_LENGTH] or None

    return None


COMMIT_HASH = get_commit_hash()


def get_banner(mode: str | None = None, hour: int | None = None) -> str:
    """
    Build the colorized splash screen banner.

    Args:
        mode: Optional mode label displayed next to the version.
        hour: Hour used to pick the palette (default: current local hour).

    Returns:
        ANSI-colorized banner.

    """
    if hour is None:
        hour = datetime.now(UTC).astimezone().hour

    footer = f'v{ COMMIT_HASH or __version__ }'
    if mode:
        footer += f' [{ mode.upper() }]'

    lines = LOGO_LINES.copy()
    lines[-1] += f'  { footer }'
    width = max(len(line) for line in lines)
    lines.append('═' * width)

    return colorize(lines, palette_for_hour(hour))


def show_banner(mode: str | None = None, hour: int | None = None) -> None:
    """
    Display the splash screen banner on the console.

    Args:
        mode: Optional mode label displayed next to the version.
        hour: Hour used to pick the palette (default: current local hour).

    """
    console.print(Text.from_ansi(get_banner(mode=mode, hour=hour)))
