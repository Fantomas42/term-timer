"""Formatting utilities for times, algorithms, scores, and display output."""
import difflib
import re
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases.case import Case
from cubing_algs.constants import AUF_CHAR
from cubing_algs.constants import INNER_MOVES
from cubing_algs.constants import OUTER_WIDE_MOVES
from cubing_algs.constants import PAUSE_CHAR
from cubing_algs.constants import ROTATIONS
from fsrs import State

from term_timer.config import SERVER_CONFIG
from term_timer.constants import DNF
from term_timer.constants import FLUENCY_LOW_THRESHOLD
from term_timer.constants import FLUENCY_MEDIUM_THRESHOLD
from term_timer.constants import FLUENCY_STEP_LOW_THRESHOLD
from term_timer.constants import FLUENCY_STEP_MEDIUM_THRESHOLD
from term_timer.constants import GHOST_DELTA_WIDTH
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import RESUME_LABEL_WIDTH
from term_timer.constants import RESUME_VALUE_WIDTH
from term_timer.constants import SECOND
from term_timer.constants import SolveFlag
from term_timer.methods.annotations import StepSummary
from term_timer.triggers import TRIGGERS_REGEX
from term_timer.triggers import apply_trigger_outside_blocks

if TYPE_CHECKING:
    from fsrs import Card

    from term_timer.solve import Solve


def compute_padding(max_value: float) -> int:
    """
    Compute padding width based on maximum value.

    Args:
        max_value: The maximum value to determine padding for.

    Returns:
        Number of characters needed for padding (1 for < 10, 2 for < 100,
        3 for < 1000, 4 for >= 1000).

    """
    padding = 1
    if max_value >= 1000:
        padding = 4
    elif max_value >= 100:
        padding = 3
    elif max_value >= 10:
        padding = 2

    return padding


def format_float(value: float, precision: int = 2) -> str:
    """
    Format float value with specified precision, removing trailing zeros.

    Args:
        value: The float value to format.
        precision: Number of decimal places to include (default: 2).

    Returns:
        Formatted string with trailing zeros and decimal point removed.

    """
    return f'{value:.{precision}f}'.rstrip('0').rstrip('.')


def format_time(elapsed_ns: int, *, allow_dnf: bool = True) -> str:
    """
    Format elapsed time in nanoseconds to MM:SS.mmm format.

    Args:
        elapsed_ns: Time in nanoseconds to format.
        allow_dnf: Whether to display DNF for zero time (default: True).

    Returns:
        Formatted time string as MM:SS.mmm or HH:MM:SS.mmm for times
        over 1 hour, or DNF string if elapsed_ns is 0 and allow_dnf
        is True.

    """
    if not elapsed_ns and allow_dnf:
        return f'{ DNF:>9}'

    elapsed_sec = elapsed_ns / SECOND
    mins, secs = divmod(int(elapsed_sec), 60)
    hours, mins = divmod(mins, 60)
    milliseconds = (elapsed_ns // MS_TO_NS_FACTOR) % 1_000
    if hours:
        return f'{hours:02}:{mins:02}:{secs:02}.{milliseconds:03}'
    return f'{mins:02}:{secs:02}.{milliseconds:03}'


def format_duration(elapsed_ns: int) -> str:
    """
    Format duration in nanoseconds to seconds with 2 decimal places.

    Args:
        elapsed_ns: Duration in nanoseconds to format.

    Returns:
        Formatted duration string in seconds with 2 decimal places.

    """
    return f'{ elapsed_ns / SECOND:.2f}'


def format_edge(edge: float, max_edge: float, decimals: int = 0) -> str:
    """
    Format time edge value for graph display.

    Args:
        edge: The time edge value in seconds.
        max_edge: Maximum edge value to determine formatting style.
        decimals: Number of decimal places for sub-second bins. When
            greater than zero, sub-minute edges keep their fractional
            part (e.g. ``+08.5s``) so finer histograms stay readable.

    Returns:
        Formatted edge string with appropriate padding and units.

    """
    mins, secs = divmod(int(edge), 60)

    if max_edge < 60:
        if decimals:
            return f'+{edge:0{3 + decimals}.{decimals}f}s'
        return f'+{secs:02}s'

    _, mins = divmod(mins, 60)

    padding = 1
    if max_edge >= 600:
        padding = 2

    return f'+{mins:0{padding}}:{secs:02}'


def format_delta(delta: int) -> str:
    """
    Format time delta with color coding.

    Args:
        delta: Time delta in nanoseconds (positive for slower,
            negative for faster).

    Returns:
        Formatted delta string with Rich markup for color (red for
        positive, green for negative), or empty string if delta is 0.

    """
    if delta == 0:
        return ''
    style = (delta > 0 and 'red') or 'green'
    sign = ''
    if delta > 0:
        sign = '+'

    return f'[{ style }]{ sign }{ format_duration(delta) }[/{ style }]'


def format_ghost_delta(delta: int) -> str:
    """
    Format a ghost-race delta as a directional, color-coded segment.

    Negative means ahead of the ghost (green ▲); positive means behind
    (red ▼). A tie counts as ahead. The magnitude is shown in seconds
    with its sign, matching ``format_delta``, right-aligned so the deltas
    of successive checkpoints stack in a single column.

    Args:
        delta: Signed delta in nanoseconds (live time minus ghost split).

    Returns:
        Rich-markup string such as ``[green]▲  -0.39[/green]`` or
        ``[red]▼  +0.39[/red]``.

    """
    if delta > 0:
        value = f'+{ format_duration(delta) }'
        return f'[red]▼ { value:>{ GHOST_DELTA_WIDTH }}[/red]'

    value = format_duration(delta)
    return f'[green]▲ { value:>{ GHOST_DELTA_WIDTH }}[/green]'


def format_resume_row(
        cells: tuple[tuple[str, str, str], ...],
        detail: str = '',
        prefix: str = '',
        style: str = 'stats',
) -> str:
    """
    Format a line of labelled values as fixed width columns.

    Args:
        cells: Label, formatted value and value style of each cell of the
            line, every value being padded so that the next cell always
            opens on the same column.
        detail: Rich markup closing the line, qualifying its values.
        prefix: String to prepend to the line for indentation.
        style: Rich console style name for formatting labels.

    Returns:
        Rich markup of the line, trimmed of the padding of its last cell.

    """
    line = f'[{ style }]{ prefix }[/{ style }]' if prefix else ''

    for label, value, value_style in cells:
        padding = ' ' * max(RESUME_VALUE_WIDTH - len(value), 0)
        line += (
            f'[{ style }]{ label:<{RESUME_LABEL_WIDTH}}:[/{ style }] '
            f'[{ value_style }]{ value }[/{ value_style }]{ padding }'
        )

    return f'{ line }{ detail }'.rstrip()


def format_score(score: float) -> str:
    """
    Format solve score with color coding based on quality.

    Args:
        score: Numeric solve score to format.

    Returns:
        Formatted score string with Rich markup for color coding
        (green for score >= 14, orange for 8-14, red for < 8).

    """
    style = 'green'
    if score < 14:
        style = 'orange'
    if score < 8:
        style = 'red'

    return f'[{ style }]{ score:.2f}[/{ style }]'


def format_grade(score: float) -> str:  # noqa: PLR0911
    """
    Convert numeric score to letter grade.

    Args:
        score: Numeric score to convert to letter grade.

    Returns:
        Letter grade from S (20+) to F (< 4), including plus grades.

    """
    if score >= 20:
        return 'S'
    if score >= 18:
        return 'A+'
    if score >= 16:
        return 'A'
    if score >= 14:
        return 'B+'
    if score >= 12:
        return 'B'
    if score >= 10:
        return 'C+'
    if score >= 8:
        return 'C'
    if score >= 6:
        return 'D'
    if score >= 4:
        return 'E'
    return 'F'


def format_flag(flag: SolveFlag) -> str:
    """
    Format flag from his value.

    Args:
        flag: Flag value to format.

    Returns:
        Flag value formatted.

    """
    flag_klass = 'result'
    if flag == DNF:
        flag_klass = 'dnf'
    if flag == PLUS_TWO:
        flag_klass = 'plus-two'

    return f'[{ flag_klass }]{ flag }[/{ flag_klass }]'


def fsrs_state_label(card: 'Card') -> tuple[str, str]:
    """
    Resolve the display label and theme class of an FSRS card state.

    A Review card is only labelled Review once its due date has passed,
    so that Review keeps its call to action meaning. While the review is
    still scheduled in the future the memory is considered consolidated
    and the card is labelled Stable instead.

    Args:
        card: Card to label.

    Returns:
        Tuple of the label to display and its theme class.

    """
    if card.state == State.Review and card.due > datetime.now(UTC):
        return 'Stable', 'stable'

    return card.state.name, card.state.name.lower()


def format_fsrs_state(card: 'Card | None') -> str:
    """
    Format the learning state of an FSRS card.

    Args:
        card: Card to format, or None when the case has no card yet.

    Returns:
        Card state formatted, or N/A when the case has no card.

    """
    if card is None:
        return '[no-ao]N/A[/no-ao]'

    label, state_klass = fsrs_state_label(card)

    return f'[{ state_klass }]{ label }[/{ state_klass }]'


def format_fsrs_due(card: 'Card | None') -> str:
    """
    Format the next review date of an FSRS card.

    Args:
        card: Card to format, or None when the case has no card yet.

    Returns:
        Due date formatted in local time, Overdue when the review date
        has passed, or N/A when the case has no card.

    """
    if card is None:
        return '[no-ao]N/A[/no-ao]'

    due = card.due.astimezone()
    if due <= datetime.now(UTC).astimezone():
        return '[warning]Overdue[/warning]'

    return f'[no-ao]{ due.strftime("%Y-%m-%d") }[/no-ao]'


def format_fluency(fluency: int, *, step: bool = False) -> str:
    """
    Format fluency score from his value.

    Args:
        fluency: Fluency value to format.
        step: Whether the value comes from a single step rather than a
            whole solve, selecting the higher step thresholds.

    Returns:
        Fluency value formatted.

    """
    medium = FLUENCY_MEDIUM_THRESHOLD
    low = FLUENCY_LOW_THRESHOLD
    if step:
        medium = FLUENCY_STEP_MEDIUM_THRESHOLD
        low = FLUENCY_STEP_LOW_THRESHOLD

    fluency_klass = 'warning'
    if fluency >= medium:
        fluency_klass = 'success'
    elif fluency >= low:
        fluency_klass = 'caution'

    return (
        f'[{ fluency_klass }]'
        f'{ fluency }% Fluency'
        f'[/{ fluency_klass }]'
    )


def format_metric(metric_name: str, value: float) -> str:
    """
    Format a doctor metric value with its natural unit.

    Args:
        metric_name: Name of the metric as used by the doctor checks.
        value: Metric value to format.

    Returns:
        Metric value formatted with its unit.

    """
    if metric_name == 'tps':
        return f'{ value:.2f} TPS'
    if metric_name == 'fluency':
        return f'{ value:g}%'
    if metric_name.endswith('percent'):
        return f'{ value:.1f}%'

    suffixes = {
        'htm': ' HTM',
        'aufs': ' QTM',
        'step_missed_moves': ' QTM',
        'transition_missed_moves': ' QTM',
        'rotations': ' rotations',
    }

    return f'{ value:g}{ suffixes.get(metric_name, "") }'


def format_session_name(session_name: str) -> str:
    """
    Format session name to a prettier version.

    Args:
        session_name: Name of the session.

    Returns:
        Session's name formatted.

    """
    return session_name.replace('-', ' ').title()


def clean_url(string: str) -> str:
    """
    URL-encode special characters in string for use in URLs.

    Args:
        string: The string to URL-encode.

    Returns:
        URL-encoded string with special characters replaced.

    """
    return string.replace(
        ' ', '_',
    ).replace(
        "'", '-',
    ).replace(
        '/', '%2F',
    ).replace(
        '\n', '%0A',
    ).replace(
        '+', '%26%232b%3B',
    ).replace(
        '-AUF', '%26%2345%3BAUF',
    )


def format_alg_cubing_url(title: str, setup: str, alg: str) -> str:
    """
    Generate alg.cubing.net URL for algorithm visualization.

    Args:
        title: Title for the algorithm visualization.
        setup: Setup moves to apply before the algorithm.
        alg: The algorithm to visualize.

    Returns:
        Complete URL for alg.cubing.net with encoded parameters.

    """
    return (
        'https://alg.cubing.net/?view=playback'
        f'&title={ title }'
        f'&alg={ clean_url(alg) }'
        f'&setup={ clean_url(setup) }'
    )


def format_cube_db_url(title: str, setup: str, alg: str) -> str:
    """
    Generate cubedb.net URL for algorithm visualization.

    Args:
        title: Title for the algorithm visualization.
        setup: Setup moves to apply before the algorithm.
        alg: The algorithm to visualize.

    Returns:
        Complete URL for cubedb.net with encoded parameters.

    """
    return (
        'https://cubedb.net/'
        f'?title={ title }'
        f'&alg={ clean_url(alg) }'
        f'&scramble={ clean_url(setup) }'
    )


def format_term_timer_session_url(cube_size: int, session_name: str) -> str:
    """
    Generate URL for local Term Timer web interface session.

    Args:
        cube_size: Cube size of the session.
        session_name: Name of the session.

    Returns:
        Local HTTP URL to view this session in the web interface.

    """
    domain = SERVER_CONFIG.get('domain', 'localhost')
    port = SERVER_CONFIG.get('port', 8333)

    return (
        f'http://{ domain }:{ port }'
        f'/{ cube_size }/{ session_name }/'
    )


def format_term_timer_case_url(case: Case) -> str:
    """
    Generate URL for local Term Timer web interface case.

    Args:
        case: The case to link.

    Returns:
        Local HTTP URL to view this case in the web interface.

    """
    domain = SERVER_CONFIG.get('domain', 'localhost')
    port = SERVER_CONFIG.get('port', 8333)

    if not case.method:
        return ''

    return (
        f'http://{ domain }:{ port }'
        f'/academy/{ case.method }/{ case.step }/{ case.code }/'
    )


def format_alg_diff(algo_a: Algorithm, algo_b: Algorithm) -> str:
    """
    Format diff between two algorithms with markup.

    Args:
        algo_a: First algorithm for comparison.
        algo_b: Second algorithm for comparison.

    Returns:
        Formatted string showing differences with Rich markup tags for
        additions and deletions.

    """
    moves: list[str] = []
    matcher = difflib.SequenceMatcher(None, algo_a, algo_b)

    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'equal':
            moves.extend(str(move) for move in algo_a[i1:i2])
        elif opcode == 'delete':
            moves.extend(
                [
                    f'[deletion]{ item }[/deletion]'
                    for item in algo_a[i1:i2]
                ],
            )
        elif opcode == 'insert':
            moves.extend(
                [
                    f'[addition]{ item }[/addition]'
                    for item in algo_b[j1:j2]
                ],
            )

        elif opcode == 'replace':
            moves.extend(
                [
                    f'[deletion]{ item }[/deletion]'
                    for item in algo_a[i1:i2]
                ],
            )
            moves.extend(
                [
                    f'[addition]{ item }[/addition]'
                    for item in algo_b[j1:j2]
                ],
            )

    return ' '.join(moves)


def format_alg_triggers(algorithm: str, trigger_names: list[str]) -> str:
    """
    Add markup to highlight trigger patterns in algorithm string.

    Args:
        algorithm: Algorithm string to add markup to.
        trigger_names: List of trigger pattern names to highlight.

    Returns:
        Algorithm string with Rich markup tags around trigger patterns.

    """
    for trigger_name in trigger_names:
        regex = TRIGGERS_REGEX[trigger_name]

        def replacer(matchobj: re.Match[str]) -> str:
            return (
                f'[{ trigger_name }]'   # noqa: B023
                f'{ matchobj.group(0) }'
                f'[/{ trigger_name }]'  # noqa: B023
            )

        algorithm = apply_trigger_outside_blocks(
            algorithm, regex, replacer,
        )

    return algorithm


def format_alg_aufs(algorithm: str, pre_auf: int, post_auf: int) -> str:
    """
    Add markup to highlight pre-AUF and post-AUF moves in algorithm.

    Args:
        algorithm: Algorithm string to add markup to.
        pre_auf: Number of pre-AUF moves present.
        post_auf: Number of post-AUF moves present.

    Returns:
        Algorithm string with Rich markup tags around AUF moves.

    """
    if pre_auf and algorithm:
        algorithm_parts = algorithm.split(' ')
        for i, move in enumerate(algorithm_parts):
            if move[0] == AUF_CHAR:
                algorithm_parts[i] = f'[pre-auf]{ move }[/pre-auf]'
            elif move != PAUSE_CHAR:
                break
        algorithm = ' '.join(algorithm_parts)

    if post_auf and algorithm:
        algorithm_parts = list(reversed(algorithm.split(' ')))
        for i, move in enumerate(algorithm_parts):
            if move[0] == AUF_CHAR:
                algorithm_parts[i] = f'[post-auf]{ move }[/post-auf]'
            elif move != PAUSE_CHAR:
                break
        algorithm = ' '.join(reversed(algorithm_parts))

    return algorithm


def format_alg_pauses(algorithm: str, solve: 'Solve', step: StepSummary,
                      *, multiple: bool = False) -> str:
    """
    Add markup to highlight pauses in algorithm execution.

    Args:
        algorithm: Algorithm string to add markup to.
        solve: Solve object containing pause threshold information.
        step: Step summary containing post-pause timing data.
        multiple: Whether to show multiple pause markers (default: False).

    Returns:
        Algorithm string with Rich markup tags around pause markers.

    """
    post = int(step['post_pause'] / solve.pause_threshold)
    if post:
        algorithm += f' [reco-pause]{ PAUSE_CHAR }[/reco-pause]' * (
            post if multiple else 1
        )

    return algorithm.replace(
        ' .',
        ' [pause].[/pause]',
    )


def format_alg_moves(algorithm: str) -> str:
    """
    Add markup to highlight different move types.

    Args:
        algorithm: Algorithm string to add markup to.

    Returns:
        Algorithm string with Rich markup tags around wide moves,
        slice moves, and rotations, or empty string if algorithm
        is empty.

    """
    if not algorithm:
        return ''

    algorithm_parts = algorithm.split(' ')

    for i, move in enumerate(algorithm_parts):
        if move[0] in OUTER_WIDE_MOVES:
            algorithm_parts[i] = f'[wide]{ move }[/wide]'
        elif move[0] in INNER_MOVES:
            algorithm_parts[i] = f'[slice]{ move }[/slice]'
        elif move[0] in ROTATIONS:
            algorithm_parts[i] = (
                f'[rotation_{ move[0] }]{ move }[/rotation_{ move[0] }]'
            )

    return ' '.join(algorithm_parts)
