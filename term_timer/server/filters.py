"""Template filter functions for server views."""
import re
from typing import Final

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_case
from cubing_algs.cases import get_collection
from cubing_algs.cases.case import Case
from cubing_algs.transform.auf import remove_auf_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.pause import pause_moves
from cubing_algs.transform.size import compress_moves
from cubing_algs.transform.timing import untime_moves

from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PAUSE_FACTOR
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_diff
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_pauses
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_duration
from term_timer.methods.annotations import StepSummary
from term_timer.methods.base import Analyser
from term_timer.methods.base import get_step_config
from term_timer.solve import Solve
from term_timer.transform import humanize_moves
from term_timer.triggers import DEFAULT_TRIGGERS

SPAN_REGEX: Final = re.compile(r'(<span[^>]*>.*?</span>)')
BLOCK_REGEX: Final = re.compile(r'\[([\w-]+)\](.*?)\[/([\w-]+)\]')

CLASS_CONVERTION: Final = {
    'red': 'deletion',
    'green': 'addition',
}

LEGENDS: Final = {
    'slot-extract': 'Slot Extract',
    'slot-insert': 'Slot Insert',
    'sexy-move': 'Sexy Move',
    'pre-auf': 'Pre-AUF',
    'post-auf': 'Post-AUF',
    'reco-pause': 'Recognition pause',
}


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


def format_score(score: float, title: str = '') -> str:
    """
    Format score value as HTML span with color-coded class.

    Args:
        score: Numeric score to format.
        title: Optional prefix text to display before the score.

    Returns:
        HTML span element with score colored based on thresholds:
        good (>=14), danger (8-13), warning (<8).

    """
    klass = 'good'
    if score < 14:
        klass = 'danger'
    if score < 8:
        klass = 'warning'

    return f'<span class="stat-{ klass }">{ title }{ score:.2f}</span>'


def format_line(value: str) -> str:
    """
    Format algorithm notation string into styled HTML spans.

    Converts cube algorithm notation into HTML with semantic markup for
    individual moves and triggers, adding CSS classes and tooltips.

    Args:
        value: Algorithm string with optional block markup like
            [sexy-move]R U R' U'[/sexy-move].

    Returns:
        HTML string with each move wrapped in styled span elements.

    """
    if not value:
        return ''

    def replacer(matchobj: re.Match[str]) -> str:
        moves = matchobj.group(2)
        markup = matchobj.group(1)
        legend = LEGENDS.get(markup, markup.title())

        klass = 'move'
        move_name = ''
        if len(moves.split(' ')) > 1:
            klass = 'trigger'
        else:
            move_name = moves.lower().replace(
                "'", '',
            ).replace(
                '2', '',
            )

        return (
            f'<span class="{ klass } { markup } { move_name }"'
            f' title="{ legend }">{ moves }</span>'
        )

    result = BLOCK_REGEX.sub(replacer, value)

    processed_parts = []
    for part in SPAN_REGEX.split(result):
        if part.startswith('<span'):
            processed_parts.append(part)
        else:
            moves = part.split()
            processed_parts.extend(
                f'<span class="move">{ move }</span>'
                for move in moves if move.strip()
            )

    return ' '.join(processed_parts)


def format_algorithm(algorithm: Algorithm) -> str:
    """
    Format algorithm into styled HTML spans.

    Converts algorithm into HTML with semantic markup for
    individual moves and triggers, adding CSS classes and tooltips.

    Args:
        algorithm: Algorithm to format.

    Returns:
        HTML string with each move wrapped in styled span elements.

    """
    algorithm_string = format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                str(algorithm),
                1,
                1,
            ),
        ),
        DEFAULT_TRIGGERS,
    )

    return format_line(algorithm_string)


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


def normalize_value(value: float, method_applied: Analyser,
                    metric: str, name: str) -> str:
    """
    Format metric value as HTML with normalized quality indicator.

    Args:
        value: Numeric metric value to format.
        method_applied: Method analyser instance for normalization.
        metric: Metric type identifier.
        name: Metric name for classification.

    Returns:
        HTML span element with value and quality-based CSS class.

    """
    klass = method_applied.normalize_value(metric, name, value, '')

    return f'<span class="metric-{ klass }">{ value }</span>'


def normalize_percent(value: float, method_applied: Analyser,
                      metric: str, name: str) -> str:
    """
    Format percentage metric as HTML with normalized quality indicator.

    Args:
        value: Numeric percentage value to format.
        method_applied: Method analyser instance for normalization.
        metric: Metric type identifier.
        name: Metric name for classification.

    Returns:
        HTML span element with percentage value and quality-based CSS class.

    """
    klass = method_applied.normalize_value(metric, name, value, '')

    return f'<span class="metric-{ klass }">{ value:.2f}%</span>'


def reconstruction_step(step: StepSummary) -> str:
    """
    Format solve step into styled HTML reconstruction display.

    Args:
        step: Step summary containing move sequences and AUF information.

    Returns:
        HTML-formatted algorithm string with styled move annotations.

    """
    algorithm = str(step['moves_prettified'])

    pre_auf, post_auf = step['aufs']
    algorithm = format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                algorithm,
                pre_auf or 0,
                post_auf or 0,
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )

    return format_line(algorithm)


def reconstruction_overheads(step: StepSummary, solve: Solve) -> str:
    """
    Format step reconstruction showing efficiency overheads.

    Compares executed moves with optimal solution to highlight unnecessary
    moves and inefficiencies in the solve.

    Args:
        step: Step summary containing move sequences and AUF information.
        solve: Solve instance for calculating move optimizations.

    Returns:
        HTML-formatted algorithm with highlighted overhead moves.

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
    algo = format_alg_triggers(
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

    return format_line(algo)


def reconstruction_pauses(step: StepSummary, solve: Solve) -> str:
    """
    Format step reconstruction with pause markers for timing analysis.

    Annotates algorithm with pause indicators based on move execution timing
    to identify hesitations and recognition delays.

    Args:
        step: Step summary containing move sequences and AUF information.
        solve: Solve instance providing timing data for pause detection.

    Returns:
        HTML-formatted algorithm with pause annotations highlighted.

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
    source_paused_str = format_alg_pauses(
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

    return format_line(source_paused_str)


def optimized_step(step: StepSummary) -> tuple[str, Algorithm]:
    """
    Generate optimized version of solve step algorithm.

    Applies step-specific optimizations to produce a more efficient
    algorithm sequence for the given case.

    Args:
        step: Step summary containing move sequences and case information.

    Returns:
        Tuple of (formatted_html_string, algorithm_object) where the HTML
        string includes styled move annotations and the algorithm is the
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
    algorithm_string = format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                str(algorithm),
                pre_auf or 0,
                post_auf or 0,
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )

    return format_line(algorithm_string), algorithm


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
            x.memory.memory_score,
        ),
    )


def first_case(method_name: str, step_name: str) -> Case:
    """
    Return first case of a step name method.

    Returns:
        The first case of the step.

    """
    return next(
        iter(
            get_collection(f'{ method_name }/{ step_name }').cases.values(),
        ),
    )


def case_number(method_name: str, step_name: str) -> int:
    """
    Return case number of a step name method.

    Returns:
        The number of case of the step.

    """
    return len(
        get_collection(f'{ method_name }/{ step_name }').cases,
    )
