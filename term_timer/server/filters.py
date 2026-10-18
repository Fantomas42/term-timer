"""Template filter functions for server views."""
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from typing import Final

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_case
from cubing_algs.cases.case import Case
from cubing_algs.constants import PAUSE_CHAR
from cubing_algs.transform.auf import remove_auf_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.pause import pause_moves
from cubing_algs.transform.size import compress_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.triggers import TRIGGER_PATTERNS

from term_timer.constants import FLUENCY_LOW_THRESHOLD
from term_timer.constants import FLUENCY_MEDIUM_THRESHOLD
from term_timer.constants import FLUENCY_STEP_LOW_THRESHOLD
from term_timer.constants import FLUENCY_STEP_MEDIUM_THRESHOLD
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PAUSE_FACTOR
from term_timer.constants import STATIC_DIRECTORY
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_diff
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_pauses
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_duration
from term_timer.formatter import format_time
from term_timer.methods.annotations import StepSummary
from term_timer.methods.base import Analyser
from term_timer.methods.base import get_step_config
from term_timer.solve import Solve
from term_timer.transform import humanize_moves
from term_timer.triggers import DEFAULT_TRIGGERS
from term_timer.triggers import SLUG_PATTERN

# Box of a sparkline, in SVG user units: the line keeps a margin of
# SPARK_MARGIN at the top and the bottom.
SPARK_WIDTH: Final = 100
SPARK_HEIGHT: Final = 24
SPARK_MARGIN: Final = 2

MINUTES_IN_HOUR: Final = 60
NS_IN_MINUTE: Final = 60_000_000_000
DAYS_AS_DAYS: Final = 14
DAYS_AS_WEEKS: Final = 60

# Characters of the SHA-256 of a static file kept as its version.
ASSET_VERSION_LENGTH: Final = 12

BLOCK_REGEX: Final = re.compile(r'\[([\w-]+)\](.*?)\[/([\w-]+)\]')

MOVE_VARIANTS: Final = {
    'pre-auf': 'pre-auf',
    'post-auf': 'post-auf',
    'wide': 'wide',
    'slice': 'slice',
    'rotation_x': 'rotation',
    'rotation_y': 'rotation',
    'rotation_z': 'rotation',
    'addition': 'addition',
    'deletion': 'deletion',
}

PAUSE_KINDS: Final = {
    'pause': 'execution',
    'reco-pause': 'recognition',
}

TRIGGER_NAMES: Final = {
    SLUG_PATTERN.sub('-', pattern.name.lower()).strip('-'): pattern.name
    for pattern in TRIGGER_PATTERNS
}

# Colour slot of each trigger family, 1 to 4 (the theme trigger-N roles).
TRIGGER_SLOTS: Final = {
    'sexy-move': 1,
    'double-sexy': 1,
    'triple-sexy': 1,
    'wide-sexy': 1,
    'sexy-sledge': 1,
    'slot-insert': 2,
    'slot-extract': 2,
    'slot-extended': 2,
    'sune': 3,
    'anti-sune': 3,
    'sune-trigger': 3,
    'sane-trigger': 3,
    'niklas': 3,
    'sledgehammer': 4,
    'hedgeslammer': 4,
    't-perm-trigger': 4,
}
DEFAULT_TRIGGER_SLOT: Final = 4

# Tone of each status of Analyser.normalize_value.
METRIC_TONES: Final = {
    'success': 'good',
    'caution': 'warn',
    'warning': 'bad',
}


@dataclass(frozen=True)
class AlgMove:
    """One move chip, with the variant it is highlighted as."""

    kind: ClassVar[str] = 'move'

    move: str
    variant: str = ''


@dataclass(frozen=True)
class AlgPause:
    """A pause between two moves, of execution or of recognition."""

    kind: ClassVar[str] = 'pause'

    pause: str = 'execution'


@dataclass(frozen=True)
class AlgTrigger:
    """A named trigger grouping its moves."""

    kind: ClassVar[str] = 'trigger'

    slug: str
    name: str
    slot: int
    moves: tuple[AlgMove, ...]


AlgToken = AlgMove | AlgPause | AlgTrigger


def format_delta(delta: int) -> str:
    """
    Format time delta as a signed duration string.

    Args:
        delta: Time difference in nanoseconds.

    Returns:
        Formatted string with sign prefix ('+' or '-') and duration,
        or empty string if delta is zero.

    """
    if delta == 0:
        return ''
    sign = ''
    if delta > 0:
        sign = '+'

    return f'{ sign }{ format_duration(delta) }'


def plain_tokens(text: str, variant: str = '') -> list[AlgToken]:
    """
    Tokens of a run of moves carrying no trigger.

    Args:
        text: Moves separated by spaces, pauses included.
        variant: Variant given to every move of the run.

    Returns:
        One token per move or pause.

    """
    return [
        AlgPause() if move == PAUSE_CHAR else AlgMove(move, variant)
        for move in text.split()
    ]


def alg_tokens(value: str) -> list[AlgToken]:
    """
    Parse the block markup of an algorithm into tokens.

    Reads the markup produced by the format_alg_* functions and returns
    it as a structure the alg macro renders. Blocks never nest: triggers
    are only marked outside the other blocks.

    Args:
        value: Algorithm string with block markup like
            [sexy-move]R U R' U'[/sexy-move].

    Returns:
        The moves, pauses and triggers in order.

    """
    tokens: list[AlgToken] = []
    position = 0
    for match in BLOCK_REGEX.finditer(value):
        tokens.extend(plain_tokens(value[position:match.start()]))
        position = match.end()

        markup, moves = match.group(1), match.group(2)
        if markup in PAUSE_KINDS:
            tokens.append(AlgPause(PAUSE_KINDS[markup]))
        elif markup in TRIGGER_NAMES:
            tokens.append(AlgTrigger(
                markup,
                TRIGGER_NAMES[markup],
                TRIGGER_SLOTS.get(markup, DEFAULT_TRIGGER_SLOT),
                tuple(AlgMove(move) for move in moves.split()),
            ))
        else:
            tokens.extend(plain_tokens(moves, MOVE_VARIANTS.get(markup, '')))
    tokens.extend(plain_tokens(value[position:]))

    return tokens


def algorithm_tokens(algorithm: Algorithm | str, *,
                     aufs: bool = True) -> list[AlgToken]:
    """
    Tokens of an algorithm, its moves and default triggers marked.

    Args:
        algorithm: Algorithm to tokenize.
        aufs: Whether a leading and a trailing U are marked as AUFs;
            False for a scramble, where they mean nothing.

    Returns:
        The moves, pauses and triggers in order.

    """
    algorithm_string = str(algorithm)
    if aufs:
        algorithm_string = format_alg_aufs(algorithm_string, 1, 1)

    return alg_tokens(
        format_alg_triggers(
            format_alg_moves(algorithm_string),
            DEFAULT_TRIGGERS,
        ),
    )


def alg_text(tokens: list[AlgToken]) -> str:
    """
    Plain notation of tokens, pauses dropped, as copied to the clipboard.

    Returns:
        The moves separated by spaces.

    """
    moves: list[str] = []
    for token in tokens:
        if isinstance(token, AlgMove):
            moves.append(token.move)
        elif isinstance(token, AlgTrigger):
            moves.extend(move.move for move in token.moves)

    return ' '.join(moves)


BREAK_RE: Final = re.compile(r'(?:\s*<br\s*/?>\s*)+', re.IGNORECASE)


def paragraphs(text: str) -> list[str]:
    """
    Split a text of the case database on its line breaks.

    The database breaks its texts with <br> tags, which an escaping
    template would print as they are.

    Returns:
        The non-empty paragraphs of the text, stripped.

    """
    return [
        paragraph.strip()
        for paragraph in BREAK_RE.split(text or '')
        if paragraph.strip()
    ]


def split_time(elapsed_ns: int) -> tuple[str, str]:
    """
    Split a time into its head and its milliseconds, for a big display.

    Leading zero units are dropped: 00:25.108 gives 25 and .108, and
    01:02.345 gives 1:02 and .345.

    Returns:
        The head and the milliseconds with their dot, empty for a DNF.

    """
    text = format_time(elapsed_ns).strip()
    if '.' not in text:
        return text, ''

    head, _dot, millis = text.rpartition('.')
    parts = head.split(':')
    while len(parts) > 1 and parts[0] == '00':
        parts.pop(0)
    parts[0] = str(int(parts[0]))

    return ':'.join(parts), f'.{ millis }'


def short_time(elapsed_ns: int) -> str:
    """
    Format a time without its leading zeros: 28.841, 1:02.345, DNF.

    Returns:
        The time as split_time gives it, in one piece.

    """
    head, millis = split_time(elapsed_ns)
    return f'{ head }{ millis }'


def hours(elapsed_ns: int) -> str:
    """
    Format a long duration in hours and minutes: 1 h 40, or 25 min.

    Returns:
        The hours and the minutes, or the minutes alone.

    """
    minutes = elapsed_ns // NS_IN_MINUTE
    if minutes < MINUTES_IN_HOUR:
        return f'{ minutes } min'
    return f'{ minutes // MINUTES_IN_HOUR } h { minutes % MINUTES_IN_HOUR:02d}'


def day_of(value: date | datetime | str) -> date:
    """
    Give the local day of a date, of a moment or of an ISO day.

    Returns:
        The date itself, the day of the moment in the local timezone, or
        the day parsed.

    """
    if isinstance(value, datetime):
        return value.astimezone().date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def days_ago(value: date | datetime | str,
             today: date | datetime | str) -> str:
    """
    Say how long ago a day is, in words.

    Returns:
        today, yesterday, or a count of days, weeks or months.

    """
    days = (day_of(today) - day_of(value)).days
    if days <= 0:
        return 'today'
    if days == 1:
        return 'yesterday'
    if days < DAYS_AS_DAYS:
        return f'{ days } days ago'
    if days < DAYS_AS_WEEKS:
        return f'{ days // 7 } weeks ago'
    return f'{ days // 30 } months ago'


def short_date(value: date | datetime | str) -> str:
    """
    Format a day as it is read in a list: 26 Sep 2026.

    Returns:
        The day, the abbreviated month and the year.

    """
    day = day_of(value)
    return f'{ day.day } { day:%b %Y}'


def weekday(value: date | datetime | str) -> str:
    """
    Give the initial of the day of the week: M, T, W, T, F, S or S.

    Returns:
        The first letter of the English name of the day.

    """
    return f'{ day_of(value):%a}'[0]


@dataclass(frozen=True)
class SparkLine:
    """A sparkline drawn in its SVG box: the path and its last point."""

    path: str
    x: float
    y: float


def sparkline(points: list[float | None]) -> SparkLine | None:
    """
    Draw times in the sparkline box, the fastest at the bottom.

    A missing point (a DNF) is skipped, the line joining its neighbours.

    Returns:
        The line, or None without any point.

    """
    values = [point for point in points if point is not None]
    if not values:
        return None

    low, high = min(values), max(values)
    span = (high - low) or 1
    step = SPARK_WIDTH / max(1, len(points) - 1)
    drawable = SPARK_HEIGHT - 2 * SPARK_MARGIN
    coordinates = [
        (
            round(index * step, 1),
            round(SPARK_HEIGHT - SPARK_MARGIN
                  - drawable * (point - low) / span, 1),
        )
        for index, point in enumerate(points)
        if point is not None
    ]
    path = ' '.join(
        f'{ "M" if index == 0 else "L" }{ x } { y }'
        for index, (x, y) in enumerate(coordinates)
    )
    x, y = coordinates[-1]
    return SparkLine(path, x, y)


def grade_tone(grade: str) -> str:
    """
    Tone of a letter grade, 'A+' and 'A' alike.

    Returns:
        The grade-x tone, or an empty string without a grade.

    """
    if not grade:
        return ''

    return f'grade-{ grade[0].lower() }'


def metric_tone(value: float, method_applied: Analyser,
                metric: str, name: str) -> str:
    """
    Tone of a metric against the norms of the method.

    Returns:
        good, warn or bad, or an empty string without a norm.

    """
    return METRIC_TONES.get(
        method_applied.normalize_value(metric, name, value, ''), '',
    )


def fluency_tone(fluency: float, *, step: bool = False) -> str:
    """
    Tone of a fluency, in percent, on the thresholds of the terminal.

    Args:
        fluency: Fluency value to tone.
        step: Whether the value comes from a single step rather than a
            whole solve, selecting the higher step thresholds, the norms
            of the doctor.

    Returns:
        good from the medium threshold, warn from the low one, else bad.

    """
    medium = FLUENCY_MEDIUM_THRESHOLD
    low = FLUENCY_LOW_THRESHOLD
    if step:
        medium = FLUENCY_STEP_MEDIUM_THRESHOLD
        low = FLUENCY_STEP_LOW_THRESHOLD

    if fluency >= medium:
        return 'good'
    if fluency >= low:
        return 'warn'
    return 'bad'


def count_tone(value: int, bad: int) -> str:
    """
    Tone of a count of faults, like pauses or AUFs.

    Returns:
        good for none, bad above the bad count, else warn.

    """
    if not value:
        return 'good'
    if value > bad:
        return 'bad'
    return 'warn'


def get_step_case(step_name: str, code_case: str) -> Case:
    """
    Retrieve the Case instance.

    Args:
        step_name: Step to use ('OLL', 'F2L 1').
        code_case: Code of the case.

    Returns:
        Case instance.

    """
    return get_case(f'CFOP/{ step_name.split(" ", maxsplit=1)[0] }', code_case)


def get_ohtm_delta(step_info: StepSummary) -> int:
    """
    Compute optimal HTM case delta.

    Args:
        step_info: Step summary info.

    Returns:
        Number of added HTM.

    """
    if not step_info['case']:
        return -1

    step_case = get_step_case(step_info['name'], step_info['case'])
    optimal_htm = step_case.optimal_htm
    if optimal_htm:
        return step_info['moves_prettified'].transform(
            remove_auf_moves,
        ).metrics.htm - optimal_htm

    return -1


def reconstruction_markup(step: StepSummary) -> str:
    """
    Block markup of a solve step, its AUFs, moves and triggers marked.

    Args:
        step: Step summary containing move sequences and AUF information.

    Returns:
        Algorithm string with block markup, read by alg_tokens.

    """
    algorithm = str(step['moves_prettified'])

    pre_auf, post_auf = step['aufs']
    return format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                algorithm,
                pre_auf or 0,
                post_auf or 0,
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )


def overheads_markup(step: StepSummary, solve: Solve) -> str:
    """
    Block markup of a solve step, its missed and extra moves marked.

    Compares executed moves with optimal solution to highlight unnecessary
    moves and inefficiencies in the solve.

    Args:
        step: Step summary containing move sequences and AUF information.
        solve: Solve instance for calculating move optimizations.

    Returns:
        Algorithm string with block markup.

    """
    source, compressed = solve.missed_moves_pair(
        step['moves_humanized'],
    )
    source_paused = source.transform(
        untime_moves,
        optimize_double_moves,
    )
    compressed_paused = compressed.transform(
        untime_moves,
        optimize_double_moves,
    )

    pre_auf, post_auf = step['aufs']
    return format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                format_alg_diff(
                    source_paused,
                    compressed_paused,
                ),
                pre_auf or 0,
                post_auf or 0,
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )


def pauses_markup(step: StepSummary, solve: Solve) -> str:
    """
    Block markup of a solve step, its pauses marked.

    Annotates algorithm with pause indicators based on move execution timing
    to identify hesitations and recognition delays.

    Args:
        step: Step summary containing move sequences and AUF information.
        solve: Solve instance providing timing data for pause detection.

    Returns:
        Algorithm string with block markup.

    """
    source_paused = step['moves_humanized'].transform(
        pause_moves(
            int(solve.move_speed / MS_TO_NS_FACTOR),
            PAUSE_FACTOR,
            multiple=True,
        ),
        untime_moves,
        optimize_double_moves,
    )

    pre_auf, post_auf = step['aufs']
    return format_alg_pauses(
        format_alg_triggers(
            format_alg_moves(
                format_alg_aufs(
                    str(source_paused),
                    pre_auf or 0,
                    post_auf or 0,
                ),
            ),
            get_step_config(step['name'], 'triggers', []),
        ),
        solve, step, multiple=True,
    )


def optimized_markup(step: StepSummary) -> tuple[str, Algorithm]:
    """
    Block markup of the optimized version of a solve step.

    Applies step-specific optimizations to produce a more efficient
    algorithm sequence for the given case.

    Args:
        step: Step summary containing move sequences and case information.

    Returns:
        Tuple of (markup, algorithm_object) where the algorithm is the
        optimized move sequence.

    """
    optimizers = []

    if 'SKIP' not in step['case']:
        optimizers = get_step_config(step['name'], 'optimizers', [])

    algorithm = humanize_moves(
        step['moves_reoriented'].transform(*optimizers),
    ).transform(
        compress_moves,
        untime_moves,
    )

    pre_auf, post_auf = step['aufs']
    markup = format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                str(algorithm),
                pre_auf or 0,
                post_auf or 0,
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )

    return markup, algorithm


def sort_algorithms(algorithms: list[Algorithm]) -> list[Algorithm]:
    """
    Sort algorithms by the most human optimized versions.

    Args:
        algorithms: Algorithm to sort.

    Returns:
        The algorithms sorted.

    """
    return sorted(
        algorithms,
        key=lambda x: (
            -x.ergonomics.ergonomic_score,
            -x.memory.memory_score,
        ),
    )


class StaticAssets:
    """
    Versioned URLs of the static files, served immutable.

    The version is a fingerprint of the content: a regenerated stylesheet
    gets a new URL at the next render, without a restart. It is computed
    again only when the file's modification time changes.
    """

    def __init__(self, root: Path = STATIC_DIRECTORY) -> None:
        """
        Locate the static files.

        Args:
            root: Folder served under /static/.

        """
        self.root = root
        self.versions: dict[Path, tuple[int, str]] = {}

    def version(self, path: Path) -> str:
        """
        Fingerprint of a static file.

        Returns:
            The start of the SHA-256 of its content, '' when missing.

        """
        try:
            modified = path.stat().st_mtime_ns
        except OSError:
            return ''
        known = self.versions.get(path)
        if known and known[0] == modified:
            return known[1]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        version = digest[:ASSET_VERSION_LENGTH]
        self.versions[path] = (modified, version)
        return version

    def url(self, url: str) -> str:
        """
        URL of a static file carrying its version.

        Returns:
            The URL with ?v=<version>, unchanged for a missing file.

        """
        version = self.version(self.root / url.removeprefix('/static/'))
        if not version:
            return url
        return f'{ url }?v={ version }'

    def import_map(self) -> dict[str, dict[str, str]]:
        """
        Import map sending each module to its versioned URL.

        Only the scripts at the root of static/js/ are modules: the
        vendored libraries sit in their own folders, one of them named
        Chart.js.

        A module imported by another (import './ui.js') resolves to the
        plain URL: mapped, it is the one the page loads, never a second
        copy of the module.

        Returns:
            The import map, ready to serialize.

        """
        return {'imports': {
            url: self.url(url)
            for url in sorted(
                f'/static/{ path.relative_to(self.root).as_posix() }'
                for path in (self.root / 'js').glob('*.js')
                if path.is_file()
            )
        }}


STATIC_ASSETS: Final = StaticAssets()
