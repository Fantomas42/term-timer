"""Formatting utilities for times, algorithms, scores, and display output."""

import difflib
import re
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import AUF_CHAR
from cubing_algs.constants import INNER_MOVES
from cubing_algs.constants import OUTER_WIDE_MOVES
from cubing_algs.constants import PAUSE_CHAR
from cubing_algs.constants import ROTATIONS

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.constants import SolveFlag
from term_timer.methods.types import StepSummary
from term_timer.triggers import TRIGGERS_REGEX
from term_timer.triggers import apply_trigger_outside_blocks

if TYPE_CHECKING:
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


def format_edge(edge: int, max_edge: int) -> str:
    """
    Format time edge value for graph display.

    Args:
        edge: The time edge value in seconds.
        max_edge: Maximum edge value to determine formatting style.

    Returns:
        Formatted edge string with appropriate padding and units.

    """
    mins, secs = divmod(int(edge), 60)

    if max_edge < 60:
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
        Flag value formatted

    """
    flag_class = 'result'
    if flag == DNF:
        flag_class = 'dnf'
    if flag == PLUS_TWO:
        flag_class = 'plus-two'

    return f'[{ flag_class }]{ flag }[/{ flag_class }]'


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
