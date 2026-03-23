"""Flask web server for solve statistics and visualization."""
import gc
import os
import re
import threading
import webbrowser
from datetime import datetime
from datetime import timezone
from typing import ClassVar
from typing import Final
from typing import cast
from wsgiref.simple_server import WSGIRequestHandler

from bottle import TEMPLATE_PATH
from bottle import Bottle
from bottle import HTTPError
from bottle import HTTPResponse
from bottle import abort
from bottle import jinja2_template
from bottle import redirect
from bottle import request
from bottle import response
from bottle import static_file
from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_case
from cubing_algs.cases import get_collection
from cubing_algs.cases.case import Case
from cubing_algs.display.image import render_cube
from cubing_algs.transform.auf import remove_auf_moves
from cubing_algs.transform.invert import invert_moves
from cubing_algs.transform.offset import offset_y2_moves
from cubing_algs.transform.offset import offset_y_moves
from cubing_algs.transform.offset import offset_yprime_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.pause import pause_moves
from cubing_algs.transform.size import compress_moves
from cubing_algs.transform.symmetry import symmetry_c_moves
from cubing_algs.transform.symmetry import symmetry_m_moves
from cubing_algs.transform.symmetry import symmetry_s_moves
from cubing_algs.transform.timing import untime_moves

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.cheers import generate_solve_cheers
from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.constants import CUBE_SIZES
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PAUSE_FACTOR
from term_timer.constants import SECOND
from term_timer.constants import STATIC_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.constants import SolveFlag
from term_timer.constants import SolveFlagInput
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_diff
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_pauses
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_session_name
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.in_out import save_solves
from term_timer.interface.console import console
from term_timer.methods import METHOD_ANALYSERS
from term_timer.methods.annotations import StepSummary
from term_timer.methods.base import Analyser
from term_timer.methods.base import get_step_config
from term_timer.orientation import ORIENTATION_MOVES
from term_timer.orientation import get_orientation_moves
from term_timer.server.annotations import AcademyCaseContext
from term_timer.server.annotations import AcademyOverviewContext
from term_timer.server.annotations import AcademyStepContext
from term_timer.server.annotations import AlgorithmDetailContext
from term_timer.server.annotations import AlgorithmVariation
from term_timer.server.annotations import DistributionData
from term_timer.server.annotations import Error404Context
from term_timer.server.annotations import Error500Context
from term_timer.server.annotations import FluencyData
from term_timer.server.annotations import MethodInfo
from term_timer.server.annotations import RecognitionData
from term_timer.server.annotations import ScatterPoint
from term_timer.server.annotations import SessionDetailContext
from term_timer.server.annotations import SessionInfo
from term_timer.server.annotations import SessionListContext
from term_timer.server.annotations import SolveDetailContext
from term_timer.server.annotations import StepMarker
from term_timer.server.annotations import TPSData
from term_timer.server.annotations import TrendData
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.stats import Statistics
from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves

SPAN_REGEX: Final = re.compile(r'(<span[^>]*>.*?</span>)')
BLOCK_REGEX: Final = re.compile(r'\[([\w-]+)\](.*?)\[/([\w-]+)\]')

CLASS_CONVERTION: Final = {
    'red': 'deletion',
    'green': 'addition',
}

LEGENDS: Final = {
    'pair-ie': 'Pair insertion/extraction',
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
            -x.ergonomics.comfort_score,
            -x.memory.memory_score,
        ),
    )


class RichHandler(WSGIRequestHandler):
    """Custom WSGI request handler with Rich console logging."""

    def log_request(self, code: int | str = '-', size: int | str = '-') -> None:
        """
        Log HTTP request with colored Rich console output.

        Args:
            code: HTTP status code.
            size: Response size in bytes.

        """
        klass = 'green'
        if int(code) > 400:
            klass = 'red'

        message = (
            f'[server][{ self.log_date_time_string() }][/server] '
            f'[{ klass }]{ code!s }[/{ klass }] '
            f'[result]{ self.requestline }[/result] '
            f'[comment]{ size!s }[/comment]'
        )

        console.print(message)


class View:
    """Base view class for rendering Jinja2 templates with custom filters."""

    template_name = ''

    def get_context(
        self,
    ) -> (
        Error404Context
        | Error500Context
        | SessionListContext
        | SessionDetailContext
        | SolveDetailContext
        | AlgorithmDetailContext
        | AcademyOverviewContext
        | AcademyStepContext
        | AcademyCaseContext
    ):
        """
        Build template context dictionary.

        Returns:
            Dictionary of context variables for template rendering.

        Raises:
            NotImplementedError: Must be implemented by subclasses.

        """
        raise NotImplementedError

    def as_view(self, debug: bool) -> str:  # noqa: FBT001
        """
        Render view template with context data.

        Args:
            debug: Enable debug mode for template rendering.

        Returns:
            Rendered HTML string.

        """
        context = self.get_context()

        content = self.template(
            self.template_name,
            DEBUG=debug,
            **context,
        )
        gc.collect()

        return content

    @staticmethod
    def template(
        template_name: str,
        **context: bool | str | float | datetime | object,
    ) -> str:
        """
        Render Jinja2 template with custom filters and context.

        Args:
            template_name: Name of template file to render.
            **context: Template context variables.

        Returns:
            Rendered template as HTML string.

        """
        context['now'] = datetime.now(tz=timezone.utc)  # noqa: UP017

        return str(
            jinja2_template(
                template_name,
                template_settings={
                    'filters': {
                        'format_delta': format_delta,
                        'format_duration': format_duration,
                        'format_grade': format_grade,
                        'format_time': format_time,
                        'format_score': format_score,
                        'format_line': format_line,
                        'format_session_name': format_session_name,
                        'get_step_case': get_step_case,
                        'get_ohtm_delta': get_ohtm_delta,
                        'normalize_value': normalize_value,
                        'normalize_percent': normalize_percent,
                        'reconstruction_step': reconstruction_step,
                        'reconstruction_overheads': reconstruction_overheads,
                        'reconstruction_pauses': reconstruction_pauses,
                        'optimized_step': optimized_step,
                        'prettify': prettify_moves,
                        'sort_algorithms': sort_algorithms,
                    },
                },
                **context,
            ),
        )


class Error404View(View):
    """View for rendering 404 Not Found error pages."""

    template_name = '404.html'

    def __init__(self, error: HTTPError) -> None:
        """
        Initialize 404 error view.

        Args:
            error: HTTP error object containing error details.

        """
        self.error = error

    def get_context(self) -> Error404Context:
        """
        Build context for 404 error template.

        Returns:
            Dictionary containing error object and message.

        """
        return {
            'error': self.error,
            'message': self.error.body,
        }


class Error500View(View):
    """View for rendering 500 Internal Server Error pages."""

    template_name = '500.html'

    def __init__(self, error: HTTPError) -> None:
        """
        Initialize 500 error view.

        Args:
            error: HTTP error object containing error details.

        """
        self.error = error

    def get_context(self) -> Error500Context:
        """
        Build context for 500 error template.

        Returns:
            Dictionary containing error, message, exception, and traceback.

        """
        return {
            'error': self.error,
            'message': self.error.body,
            'exception': self.error.exception,
            'traceback': self.error.traceback,
        }


class SessionListView(View):
    """View for listing all solve sessions grouped by cube size."""

    template_name = 'index.html'

    @staticmethod
    def get_context() -> SessionListContext:
        """
        Build context with all sessions and their statistics.

        Returns:
            Dictionary containing sessions organized by cube size,
            with statistics calculated for each session.

        """
        sessions: dict[int, dict[str, SessionInfo]] = {}
        for cube in CUBE_SIZES:
            solves = load_all_solves(cube, [], [], [])
            sessions[cube] = {}
            for solve in solves:
                if solve.session not in sessions[cube]:
                    sessions[cube][solve.session] = {
                        'solves': [],
                        'stats': Statistics([]),
                    }
                sessions[cube][solve.session]['solves'].append(solve)

        for cube in CUBE_SIZES:
            values = sessions[cube].values()
            for info in values:
                info['stats'] = Statistics(
                    [s.final_time for s in info['solves']],
                )

            if len(values) > 1:
                all_solves = []
                for info in values:
                    all_solves.extend(info['solves'])
                sessions[cube]['all'] = {
                    'solves': all_solves,
                    'stats': Statistics(
                        [s.final_time for s in all_solves],
                    ),
                }

            session_sorted = sorted(
                sessions[cube].items(),
                key=lambda item: len(item[1]['solves']),
                reverse=True,
            )
            sessions[cube] = dict(session_sorted)

        return {
            'sessions': sessions,
        }


class SessionDetailView(View):
    """View for displaying detailed statistics for a solve session."""

    template_name = 'session.html'

    def __init__(self, cube: int, session: str,
                 method_name: str, step: str, case_uid: str) -> None:
        """
        Initialize session detail view with optional filtering.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            method_name: Solving method name (e.g., 'cfop').
            step: Optional step filter (e.g., 'f2l', 'oll').
            case_uid: Optional case identifier for filtering.

        """
        self.cube = cube
        self.session = session

        solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
        )
        if not method_name:
            method_name = CUBE_METHOD

        self.step = step.strip().lower()
        self.case_uid = case_uid.strip().lower()
        self.method_name = method_name.strip().lower()

        self.method_aggregation = SolvesMethodAggregator(
            self.method_name, solves, full=True,
        )

        solves_analyzed = self.method_aggregation.results['stack']

        if self.step and self.case_uid:  # noqa: PLR1702
            filtered_solves = []

            for solve in solves_analyzed:
                solve = cast('Solve', solve)

                if not solve.advanced:
                    continue

                method_applied = cast('Analyser', solve.method_applied)

                for s_step in reversed(method_applied.summary):
                    if s_step['name'].lower() == self.step:
                        if s_step['case']:
                            step_case = s_step['case'].split(' ')[0].lower()
                            if step_case == self.case_uid:
                                filtered_solves.append(solve)
                        break

            solves = filtered_solves

        if not solves:
            abort(404, 'No solve to display')

        self.stats = SolveStatisticsReporter(
            cube, solves,
        )

    def get_context(self) -> SessionDetailContext:
        """
        Build context with session statistics and visualizations.

        Returns:
            Dictionary containing session data, statistics, trends,
            distribution, and punchcard data.

        """
        return {
            'cube': self.cube,
            'session': self.session,
            'stats': self.stats,
            'sessions': self.compute_sessions(),
            'trend': self.compute_trend(),
            'distribution': self.compute_distribution(),
            'punchcard': self.compute_punchcard(),
            'step': self.step,
            'case_uid': self.case_uid,
            'method_aggregation': self.method_aggregation,
        }

    def compute_sessions(self) -> dict[str, int]:
        """
        Calculate solve counts per session.

        Returns:
            Dictionary mapping session names to solve counts.

        """
        sessions: dict[str, int] = {}
        for solve in self.stats.stack:
            sessions.setdefault(solve.session, 0)
            sessions[solve.session] += 1

        return sessions

    def compute_trend(self) -> TrendData:
        """
        Calculate rolling averages and time trends.

        Returns:
            Dictionary with solve indices, times, and rolling averages
            (ao5, ao12, ao100, ao1000) for trend visualization.

        """
        ao5s: list[float | None] = []
        ao12s: list[float | None] = []
        ao100s: list[float | None] = []
        ao1000s: list[float | None] = []
        times: list[float] = []
        indices: list[str] = []

        stack_time = list(self.stats.stack_time)
        for i, time in enumerate(stack_time):
            seconds = time / SECOND
            times.append(seconds)
            indices.append(str(i + 1))

            ao5 = self.stats.ao(5, stack_time[:i + 1])
            ao12 = self.stats.ao(12, stack_time[:i + 1])
            ao100 = self.stats.ao(100, stack_time[:i + 1])
            ao1000 = self.stats.ao(1000, stack_time[:i + 1])

            ao5s.append(ao5 / SECOND if ao5 > 0 else None)
            ao12s.append(ao12 / SECOND if ao12 > 0 else None)
            ao100s.append(ao100 / SECOND if ao100 > 0 else None)
            ao1000s.append(ao1000 / SECOND if ao1000 > 0 else None)

        return {
            'indices': indices,
            'times': times,
            'ao5s': ao5s,
            'ao12s': ao12s,
            'ao100s': ao100s,
            'ao1000s': ao1000s,
        }

    def compute_distribution(self) -> DistributionData:
        """
        Calculate solve time distribution histogram.

        Returns:
            Dictionary with time bucket labels and solve counts.

        """
        dist_labels: list[str] = []
        dist_counts: list[int] = []
        for count, edge in self.stats.repartition:
            dist_labels.append(f'{ edge }s')
            dist_counts.append(int(count))

        return {
            'labels': dist_labels,
            'counts': dist_counts,
        }

    def compute_punchcard(self) -> dict[str, dict[str, int]]:
        """
        Calculate daily solve frequency by year for calendar heatmap.

        Returns:
            Nested dictionary mapping year to date to solve count.

        """
        punchcard: dict[str, dict[str, int]] = {}

        for solve in self.stats.stack:
            dt = solve.datetime.astimezone()
            year = dt.strftime('%Y')
            date = dt.strftime('%Y-%m-%d')

            punchcard.setdefault(year, {}).setdefault(date, 0)
            punchcard[year][date] += 1

        return punchcard


class SolveDetailView(View):
    """View for displaying detailed analysis of a single solve."""

    template_name = 'solve.html'

    def __init__(self, cube: int, session: str, solve_id: int,
                 method_name: str, orientation: str) -> None:
        """
        Initialize solve detail view.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.
            method_name: Solving method to apply for analysis.
            orientation: Cube orientation for display.

        """
        self.cube = cube
        self.session = session

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
        )

        self.solve_id = solve_id
        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        method_name = method_name.strip().lower()
        if method_name:
            self.solve.method_name = method_name
        self.solve.orientation = orientation

    def get_context(self) -> SolveDetailContext:
        """
        Build context with solve details and analysis data.

        Returns:
            Dictionary containing solve data, reconstruction, timing charts,
            TPS metrics, and step analysis.

        """
        tps: list[TPSData] = []
        steps: list[StepMarker] = []
        scatter: list[ScatterPoint] = []
        fluencies: list[FluencyData] = []
        recognitions: list[RecognitionData] = []

        ranks = sorted([s.final_time for s in self.solves])
        rank = ranks.index(self.solve.final_time) + 1

        if self.solve.advanced:
            scatter = [
                {
                    'y': self.solve.move_times[i][1] / 1000,
                    'x': i + 1,
                }
                for i in range(len(self.solve.move_times))
            ]

            method_applied = cast('Analyser', self.solve.method_applied)

            for s in method_applied.summary:
                if s['type'] not in {'skipped', 'virtual'}:
                    index = s['index'][-1] + 1
                    steps.append(
                        {
                            'x': index,
                            'y': self.solve.move_times[index - 1][1] / 1000,
                            'label': s['name'],
                        },
                    )
                    tps.append(
                        {
                            'tps': Solve.compute_tps(s['qtm'], s['total']),
                            'etps': Solve.compute_tps(s['qtm'], s['execution']),
                            'label': s['name'],
                        },
                    )
                    fluencies.append(
                        {
                            'fluency': Solve.compute_fluency(s['moves']),
                            'label': s['name'],
                        },
                    )
                    recognitions.append(
                        {
                            'recognition': s['recognition'] / SECOND,
                            'execution': s['execution'] / SECOND,
                            'label': s['name'],
                        },
                    )

        reconstruction_text = self.solve.method_text_builder(
            multiple=False,
        )
        step_index: dict[str, int] = {}
        index = 0
        for line in reconstruction_text.split('\n'):
            if not line:
                continue
            moves, comment = line.split('//')
            name = comment
            if 'Reco' in name:
                name = name.split('Reco')[0]
            if '(' in name:
                name = name.split('(')[0]
            name = name.strip()
            step_index[name] = index
            if ' ' in name:
                name = name.split(' ')[0]
                if name not in step_index:
                    step_index[name] = index

            index += len(moves.strip().split(' '))

        return {
            'cube': self.cube,
            'session': self.session,
            'solve': self.solve,
            'solve_id': self.solve_id,
            'solves': self.solves,
            'scatter': scatter,
            'steps': steps,
            'cheers': generate_solve_cheers(self.solve),
            'tps': tps,
            'fluencies': fluencies,
            'recognitions': recognitions,
            'reconstruction_text': reconstruction_text,
            'reconstruction_timing': self.solve.reconstruction_steps_timing,
            'reconstruction_index': step_index,
            'rank': rank,
            'available_orientations': ORIENTATION_MOVES,
            'available_methods': list(METHOD_ANALYSERS.keys()),
        }


class SolveUpdateFlagView:
    """View for updating solve flag."""

    def __init__(self, cube: int, session: str, solve_id: int,
                 flag: SolveFlagInput) -> None:
        """
        Update solve flag and redirect to solve detail.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.
            flag: New flag value to set (DNF, +2, or OK).

        """
        self.cube = cube
        self.session = session
        self.solve_id = solve_id
        self.flag = flag

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        normalized_flag: SolveFlag = '' if flag == 'OK' else flag
        self.solves[self.solve_index].flag = normalized_flag
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/{ solve_id }/')


class SolveUpdateCommentView:
    """View for updating solve comment."""

    def __init__(self, cube: int, session: str, solve_id: int,
                 comment: str) -> None:
        """
        Update solve comment and redirect to solve detail.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.
            comment: New comment value to set.

        """
        self.cube = cube
        self.session = session
        self.solve_id = solve_id
        self.comment = comment

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves[self.solve_index].comment = comment.strip()
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/{ solve_id }/')


class SolveDeleteView:
    """View for deleting a solve from the database."""

    def __init__(self, cube: int, session: str, solve_id: int) -> None:
        """
        Delete solve and redirect to session overview.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.

        """
        self.cube = cube
        self.session = session
        self.solve_id = solve_id

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves.pop(self.solve_index)
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/')


class AlgorithmDetailView(View):
    """View for displaying algorithm with transformations and variations."""

    template_name = 'algorithm.html'

    def __init__(self, algorithm: str, orientation: str) -> None:
        """
        Initialize algorithm detail view.

        Args:
            algorithm: Algorithm string in standard cube notation.
            orientation: Cube orientation for display.

        """
        self.algorithm = Algorithm.parse_moves(algorithm)
        self.orientation = orientation

    def get_context(self) -> AlgorithmDetailContext:
        """
        Build context with algorithm variations and transformations.

        Returns:
            Dictionary containing original algorithm, Y-axis rotations,
            symmetry transformations, and invert variation.

        """
        # Generate Y-axis variations
        y_variations: list[AlgorithmVariation] = [
            {
                'label': 'Y',
                'algorithm': offset_y_moves(self.algorithm),
            },
            {
                'label': 'Y2',
                'algorithm': offset_y2_moves(self.algorithm),
            },
            {
                'label': "Y'",
                'algorithm': offset_yprime_moves(self.algorithm),
            },
        ]

        symmetry_variations: list[AlgorithmVariation] = [
            {
                'label': 'Symmetry M',
                'algorithm': symmetry_m_moves(self.algorithm),
            },
            {
                'label': 'Symmetry S',
                'algorithm': symmetry_s_moves(self.algorithm),
            },
            {
                'label': 'Symmetry C',
                'algorithm': symmetry_c_moves(self.algorithm),
            },
        ]

        selected_orientation = self.orientation or CUBE_ORIENTATION

        return {
            'algorithm': self.algorithm,
            'y_variations': y_variations,
            'symmetry_variations': symmetry_variations,
            'inverse_variation': invert_moves(self.algorithm),
            'orientation_faces': selected_orientation,
            'orientation_moves': get_orientation_moves(selected_orientation),
            'available_orientations': ORIENTATION_MOVES,
        }


class CubeImageView(View):
    """View for displaying a cube in SVG."""

    def __init__(self, algorithm: str, case: str,  # noqa: PLR0913, PLR0917
                 size: str, cube_size: str,
                 view: str, mask: str,
                 rotation: str, orientation: str) -> None:
        """
        Initialize algorithm image view.

        Args:
            algorithm: Algorithm to represent.
            case: Algorithm to represent to solve the case.
            size: Image size to render.
            cube_size: Cube size to use.
            rotation: Rotation to apply to the 3D cube.
            orientation: Orientation of the initial cube.

        """
        self.algorithm = (
            algorithm and Algorithm.parse_moves(algorithm)
        ) or Algorithm.parse_moves(case).transform(invert_moves)

        self.size = (size and int(size)) or 200
        self.cube_size = (cube_size and int(cube_size)) or 3
        self.view = view or '3d'
        self.mask = mask
        self.rotation = rotation or 'y45x-34'
        self.orientation = orientation or CUBE_ORIENTATION

        if self.orientation:
            orientation_moves = get_orientation_moves(self.orientation)
            self.algorithm = orientation_moves + self.algorithm

    def as_view(self, _debug: bool) -> str:  # noqa: FBT001
        """
        Render the cube in SVG.

        Returns:
            The rendered cube.

        """
        response.content_type = 'image/svg+xml'

        return render_cube(
            self.algorithm,
            size=self.size,
            cube_size=self.cube_size,
            view=self.view,
            mask=self.mask,
            rotation=self.rotation,
            palette_name=CUBE_PALETTE,
        )


class AcademyView(View):
    """View for displaying academy overview with solving methods."""

    template_name = 'academy/overview.html'
    methods: ClassVar[dict[str, MethodInfo]] = {
        'CFOP': {
            'cube_size': 3,
            'description': (
                'Cross, F2L, OLL, PLL - The most popular speedcubing method'
            ),
            'steps': {
                'F2L': {
                    'description': (
                        'First Two Layers - '
                        'Solve cross and first two layers simultaneously'
                    ),
                    'view': '3d',
                    'mask': 'f2l',
                },
                'OLL': {
                    'description': (
                        'Orientation of Last Layer - '
                        'Orient all pieces on the last layer'
                    ),
                    'view': 'top',
                    'mask': 'oll',
                },
                'PLL': {
                    'description': (
                        'Permutation of Last Layer - '
                        'Permute all pieces on the last layer'
                    ),
                    'view': 'top',
                    'mask': 'pll',
                },
                'AF2L': {
                    'description': (
                        'Advanced First Two Layers - '
                        'Solve first two layers with advanced techniques.'
                    ),
                    'view': '3d',
                    'mask': 'af2l',
                },
            },
        },
        'Roux': {
            'cube_size': 3,
            'description': (
                'First Two Block, CMLL, LSE - '
                'The blockbuilding speedcubing method'
            ),
            'steps': {
                'CMLL': {
                    'description': (
                        'Corners of last layer - '
                        'Solve of corner orientations and permutations'
                    ),
                    'view': '3d',
                    'mask': '',
                },
                'LSE': {
                    'description': (
                        'Last Six Edges - '
                        'Solve M-slice centers and edges together'
                    ),
                    'view': '3d',
                    'mask': '',
                },
            },
        },
        'Ortega': {
            'cube_size': 2,
            'description': (
                'Solve D, OLL, PBL - The most popular 2x2x2 method'
            ),
            'steps': {
                'OLL': {
                    'description': (
                        'Orientation of Last Layer - '
                        'Orient all pieces on the last layer'
                    ),
                    'view': 'top',
                    'mask': 'oll',
                },
                'PBL': {
                    'description': (
                        'Permutation of Both Layers - '
                        'Orient all pieces on all layers'
                    ),
                    'view': '3d',
                    'mask': '',
                },
            },
        },
    }

    def get_context(
        self,
    ) -> AcademyOverviewContext | AcademyStepContext | AcademyCaseContext:
        """
        Build context with available solving methods.

        Returns:
            Dictionary containing methods and their descriptions.

        """
        return {
            'methods': self.methods,
        }


class AcademyStepView(AcademyView):
    """View for displaying all cases for a specific method step."""

    template_name = 'academy/step.html'

    def __init__(self, method: str, step: str,
                 group: str, family: str, orientation: str) -> None:
        """
        Initialize academy step view.

        Args:
            method: Method name (CFOP, Ortega).
            step: Method step name (F2L, OLL, or PLL).
            group: Step group filter.
            family: Step family filter.
            orientation: Cube orientation for display.

        """
        self.method = method
        self.step = step
        self.group = group
        self.family = family
        self.orientation = orientation

        try:
            self.cases = get_collection(f'{ method }/{ step }').cases
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = self.methods[method]['cube_size']
        except KeyError:
            abort(404, f'{ method }/{ step } does not exist')

        if group:
            self.cases = {
                c: case
                for c, case in self.cases.items()
                if group in case.groups
            }
        if family:
            self.cases = {
                c: case
                for c, case in self.cases.items()
                if family == case.family
            }

    def get_context(self) -> AcademyStepContext:
        """
        Build context with all cases for the step.

        Returns:
            Dictionary containing step information, case list.

        """
        selected_orientation = self.orientation or CUBE_ORIENTATION

        return {
            'method': self.method,
            'step': self.step,
            'step_info': self.step_info,
            'cube_size': self.cube_size,
            'cases': self.cases,
            'group': self.group,
            'family': self.family,
            'orientation_faces': selected_orientation,
            'orientation_moves': get_orientation_moves(selected_orientation),
            'available_orientations': ORIENTATION_MOVES,
        }


class AcademyCaseView(AcademyView):
    """View for displaying detailed information about a specific case."""

    template_name = 'academy/case.html'

    def __init__(self, method: str, step: str, case_id: str,
                 orientation: str) -> None:
        """
        Initialize academy case view.

        Args:
            method: Method name (CFOP).
            step: CFOP step name (F2L, OLL, or PLL).
            case_id: Case identifier within the step.
            orientation: Cube orientation for display.

        """
        self.method = method
        self.step = step
        self.case_id = case_id
        self.orientation = orientation

        try:
            self.case = get_case(f'{ method }/{ step }', case_id)
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = self.methods[method]['cube_size']
        except KeyError:
            abort(404, f'{ method }/{ step } { case_id } does not exist')

    def get_context(self) -> AcademyCaseContext:
        """
        Build context with case details, algorithms, and orientations.

        Returns:
            Dictionary containing case information.

        """
        selected_orientation = self.orientation or CUBE_ORIENTATION

        return {
            'method': self.method,
            'step': self.step,
            'step_info': self.step_info,
            'cube_size': self.cube_size,
            'case': self.case,
            'orientation_faces': selected_orientation,
            'orientation_moves': get_orientation_moves(selected_orientation),
            'available_orientations': ORIENTATION_MOVES,
        }


class Server:
    """Flask/Bottle web server for solve statistics and visualization."""

    def run_server(self, host: str, port: int, *, debug: bool) -> None:
        """
        Start the web server and open browser.

        Args:
            host: Host address to bind to (e.g., 'localhost', '0.0.0.0').
            port: Port number to listen on.
            debug: Enable debug mode with auto-reload on code changes.

        """
        TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)

        app = self.create_app(debug=debug)

        if not os.getenv('BOTTLE_CHILD'):
            url = f'http://{ host }:{ port }/'
            console.print(
                '[server]Term Timer server is listening on [/server]'
                f'[localhost][link={ url }]{ url }[/link][/localhost]',
            )
            console.print('Hit Ctrl-C to quit.', style='comment')

            # Open browser in a separate thread
            def open_browser() -> None:
                webbrowser.open(url)

            if not debug:
                threading.Thread(target=open_browser, daemon=True).start()

        app.run(
            host=host,
            port=port,
            quiet=True,
            reloader=debug,
            debug=debug,
            server='wsgiref',
            handler_class=RichHandler,
        )

    @staticmethod
    def create_app(*, debug: bool) -> Bottle:  # noqa: C901
        """
        Create and configure Bottle application with all routes.

        Args:
            debug: Enable debug mode for detailed error pages.

        Returns:
            Configured Bottle application instance with all routes,
            hooks, and error handlers registered.

        """
        app = Bottle()

        @app.hook('before_request')  # type: ignore[untyped-decorator]
        def add_trailing_slash() -> None:
            """Redirect URLs without trailing slash to version with slash."""
            path = request.environ.get('PATH_INFO', '')

            if (
                    path != '/'
                    and not path.endswith('/')
                    and '.' not in path.split('/')[-1]
            ):
                new_url = request.url + '/'
                redirect(new_url, code=301)

        @app.route('/')  # type: ignore[untyped-decorator]
        def session_list() -> str:
            """
            Render session list overview page.

            Returns:
                Rendered HTML template.

            """
            return SessionListView().as_view(debug)

        @app.route('/academy/')  # type: ignore[untyped-decorator]
        def academy_overview() -> str:
            """
            Render academy overview page.

            Returns:
                Rendered HTML template.

            """
            return AcademyView().as_view(debug)

        @app.route('/academy/<method>/<step>/')  # type: ignore[untyped-decorator]
        def academy_step(method: str, step: str) -> str:
            """
            Render academy step page with all cases.

            Returns:
                Rendered HTML template.

            """
            return AcademyStepView(
                method, step,
                request.GET.group,
                request.GET.family,
                request.GET.o,
            ).as_view(debug)

        @app.route('/academy/<method>/<step>/<case_id>/')  # type: ignore[untyped-decorator]
        def academy_case(method: str, step: str, case_id: str) -> str:
            """
            Render academy case detail page.

            Returns:
                Rendered HTML template.

            """
            return AcademyCaseView(
                method, step, case_id,
                request.GET.o,
            ).as_view(debug)

        @app.route('/algorithm/<algorithm>/')  # type: ignore[untyped-decorator]
        def algorithm_detail(algorithm: str) -> str:
            """
            Render algorithm detail page with variations.

            Returns:
                Rendered HTML template.

            """
            return AlgorithmDetailView(
                algorithm,
                request.GET.o,
            ).as_view(debug)

        @app.route('/cube/')  # type: ignore[untyped-decorator]
        def cube_image() -> str:
            """
            Render cube SVG image.

            Returns:
                Rendered SVG image.

            """
            return CubeImageView(
                request.GET.algo,
                request.GET.case,
                request.GET.size,
                request.GET.cube_size,
                request.GET.view,
                request.GET.mask,
                request.GET.rotation,
                request.GET.o,
            ).as_view(debug)

        @app.route('/<cube:int>/<session:path>/<solve:int>/flag/',
                   method='POST')  # type: ignore[untyped-decorator]
        def solve_update_flag(cube: int, session: str, solve: int) -> None:
            """Handle solve update flag POST request."""
            SolveUpdateFlagView(
                cube, session, solve,
                request.POST.flag,
            )

        @app.route('/<cube:int>/<session:path>/<solve:int>/comment/',
                   method='POST')  # type: ignore[untyped-decorator]
        def solve_update_comment(cube: int, session: str, solve: int) -> None:
            """Handle solve update comment POST request."""
            SolveUpdateCommentView(
                cube, session, solve,
                request.POST.comment,
            )

        @app.route('/<cube:int>/<session:path>/<solve:int>/delete/',
                   method='POST')  # type: ignore[untyped-decorator]
        def solve_delete(cube: int, session: str, solve: int) -> None:
            """Handle solve delete POST request."""
            SolveDeleteView(
                cube, session, solve,
            )

        @app.route('/<cube:int>/<session:path>/<solve:int>/')  # type: ignore[untyped-decorator]
        def solve_detail(cube: int, session: str, solve: int) -> str:
            """
            Render solve detail page with analysis.

            Returns:
                Rendered HTML template.

            """
            return SolveDetailView(
                cube, session, solve,
                request.GET.m,
                request.GET.o or 'auto',
            ).as_view(debug)

        @app.route('/<cube:int>/<session:path>/')  # type: ignore[untyped-decorator]
        def session_detail(cube: int, session: str) -> str:
            """
            Render session detail page with statistics.

            Returns:
                Rendered HTML template.

            """
            return SessionDetailView(
                cube, session,
                request.GET.m,
                request.GET.step,
                request.GET.case_uid,
            ).as_view(debug)

        @app.route('/static/<filepath:path>')  # type: ignore[untyped-decorator]
        def static_serve(filepath: str) -> HTTPResponse:
            """
            Serve static files.

            Returns:
                Static file response.

            """
            return static_file(filepath, root=STATIC_DIRECTORY)

        @app.error(404)  # type: ignore[untyped-decorator]
        def error_404(error: HTTPError) -> str:
            """
            Handle 404 Not Found errors.

            Returns:
                Rendered error page HTML.

            """
            return Error404View(error).as_view(debug)

        @app.error(500)  # type: ignore[untyped-decorator]
        def error_500(error: HTTPError) -> str:
            """
            Handle 500 Internal Server errors.

            Returns:
                Rendered error page HTML.

            """
            return Error500View(error).as_view(debug)

        return app
