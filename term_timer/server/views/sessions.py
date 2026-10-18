"""Session list and detail views."""
import json
from datetime import date
from datetime import datetime
from datetime import timedelta
from operator import itemgetter
from typing import TYPE_CHECKING
from typing import Final
from typing import cast

from bottle import abort

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.config import CUBE_METHOD
from term_timer.config import STATS_GRAPH_SERIES
from term_timer.config import STATS_SESSION_SERIES
from term_timer.constants import CUBE_SIZES
from term_timer.constants import SECOND
from term_timer.formatter import format_grade
from term_timer.formatter import format_session_name
from term_timer.in_out import load_all_daily_solves
from term_timer.in_out import load_all_solves
from term_timer.interface.series import SeriesReporter
from term_timer.methods import METHOD_ANALYSERS
from term_timer.server.activity import ActivityCalendar
from term_timer.server.annotations import ActivityCalendarData
from term_timer.server.annotations import BoardRow
from term_timer.server.annotations import CareerChart
from term_timer.server.annotations import CareerKind
from term_timer.server.annotations import CareerLinePoint
from term_timer.server.annotations import CareerPoint
from term_timer.server.annotations import CaseRow
from term_timer.server.annotations import CaseTable
from term_timer.server.annotations import DashboardContext
from term_timer.server.annotations import DashboardForm
from term_timer.server.annotations import DistributionChart
from term_timer.server.annotations import DistributionData
from term_timer.server.annotations import ForecastDay
from term_timer.server.annotations import ForecastSummary
from term_timer.server.annotations import RecentSolve
from term_timer.server.annotations import SessionDetailContext
from term_timer.server.annotations import SessionInfo
from term_timer.server.annotations import SessionListContext
from term_timer.server.annotations import SessionRow
from term_timer.server.annotations import SessionSeriesEntry
from term_timer.server.annotations import SessionSwitchItem
from term_timer.server.annotations import SessionTable
from term_timer.server.annotations import TrainingBannerInfo
from term_timer.server.annotations import TrendChart
from term_timer.server.annotations import TrendData
from term_timer.server.annotations import TrendSeries
from term_timer.server.filters import short_date
from term_timer.server.views.base import View
from term_timer.server.views.daily import DailyListView
from term_timer.server.views.daily import DailyLocation
from term_timer.server.views.scramble import DEFAULT_CUBE_SIZE
from term_timer.server.views.solves import SolveLocation
from term_timer.server.views.training import TrainingForecastView
from term_timer.stats import SolveStatisticsReporter
from term_timer.stats import Statistics

if TYPE_CHECKING:
    from term_timer.methods.base import Analyser
    from term_timer.solve import Solve

# Dashboard: solves drawn by the form chart, by a sparkline, listed as
# the last ones; days counted as the last month; forecast days shown.
FORM_SOLVES: Final = 60
SPARK_SOLVES: Final = 30
RECENT_SOLVES: Final = 10
MONTH_DAYS: Final = 30
FORECAST_DAYS: Final = 9

# Series of the career chart, the most recently played first, and the
# colour roles they take in turn; its line, the rolling average of
# CAREER_AVERAGE solves, keeps one point out of CAREER_LINE_STEP; its
# scale stops at the CAREER_CEILING quantile of the times.
CAREER_ROLES: Final = (
    'chart-1', 'chart-3', 'chart-6', 'chart-4', 'chart-5', 'chart-2',
)
CAREER_AVERAGE: Final = 100
CAREER_LINE_STEP: Final = 5
CAREER_CEILING: Final = 0.99
CAREER_FLOOR_STEP: Final = 5
LOGBOOK: Final = 'logbook'

# Session page: solves listed unless all are asked for; the scale of the
# progress chart stops at the TREND_CEILING quantile; legend key of each
# rolling average, in the colour order of the trend chart.
SOLVES_SHOWN: Final = 50
TREND_CEILING: Final = 0.98
TREND_KEYS: Final = ('3', '1', '4', '5')
# A case is overrepresented when met this much above its probability.
OVERREPRESENTED: Final = 1.5


def seconds(elapsed_ns: int) -> float | None:
    """
    Convert a time to seconds for a chart, a DNF being no point.

    Returns:
        The time in seconds, None for a DNF.

    """
    return round(elapsed_ns / SECOND, 3) if elapsed_ns > 0 else None


def quantile(values: list[float], share: float) -> float:
    """
    Value under which a share of the values lie.

    Returns:
        The value at that rank of the sorted values, 0 without value.

    """
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * share))]


def rolling_average(times: list[int], size: int) -> list[float | None]:
    """
    Compute the average of the last solves at every solve.

    Returns:
        One value per solve in seconds, None before enough solves.

    """
    return [
        seconds(Statistics.ao(size, times[index + 1 - size:index + 1]))
        if index + 1 >= size else None
        for index in range(len(times))
    ]


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
            solves = load_all_solves(
                cube, [], [], [], directory=SolveLocation.directory,
            )
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

        training = TrainingForecastView.banner()

        return {
            'daily': DailyListView.banner(DEFAULT_CUBE_SIZE),
            'training': training,
            **SessionListView.dashboard(sessions, training),
        }

    @staticmethod
    def dashboard(
            sessions: dict[int, dict[str, SessionInfo]],
            training: TrainingBannerInfo | None,
    ) -> DashboardContext:
        """
        Build what the dashboard shows beyond the sessions and banners.

        The form, the last solves and the career cover the main puzzle,
        every session and the daily together; the activity covers every
        puzzle.

        Args:
            sessions: Sessions of every puzzle, the whole of them as all.
            training: Training banner, None when nothing is trained.

        Returns:
            The form, the session tables, the last solves, the career,
            the activity, the forecast and the commands to run.

        """
        today = datetime.now().astimezone().date()
        daily = load_all_daily_solves(DEFAULT_CUBE_SIZE)
        timeline = sorted(
            [
                solve
                for name, info in sessions[DEFAULT_CUBE_SIZE].items()
                if name != 'all'
                for solve in info['solves']
            ] + daily,
            key=lambda solve: solve.datetime,
        )
        logbook = {id(solve) for solve in daily}
        everything = [
            solve
            for cube_sessions in sessions.values()
            for name, info in cube_sessions.items()
            if name != 'all'
            for solve in info['solves']
        ] + daily

        return {
            'today': today,
            'form': SessionListView.form(timeline, today),
            'session_tables': SessionListView.session_tables(sessions),
            'recent': SessionListView.recent(timeline, logbook),
            'career': SessionListView.career(timeline, logbook, today),
            'activity': ActivityCalendar.from_moments(
                solve.datetime for solve in everything
            ).layout(today),
            'forecast': (
                SessionListView.forecast(today) if training else None
            ),
            'daily_command': 'term-timer daily',
            'training_command': (
                'term-timer train -s '
                + max(training['steps'], key=itemgetter('due'))[
                    'step'].lower()
                if training and training['steps'] else ''
            ),
        }

    @staticmethod
    def form(timeline: list['Solve'], today: date) -> DashboardForm | None:
        """
        Measure the current form, every session and the daily together.

        Args:
            timeline: Solves of the main puzzle, oldest first.
            today: Day the last month ends on.

        Returns:
            Current and best averages, the solves of the last month, and
            the last solves with their Ao12; None without any solve.

        """
        if not timeline:
            return None

        times = [solve.final_time for solve in timeline]
        stats = Statistics(times)
        month = today - timedelta(days=MONTH_DAYS)
        best_ao12 = stats.best_ao12 if len(times) >= 12 else 0

        return {
            'ao5': stats.ao5 if len(times) >= 5 else 0,
            'ao12': stats.ao12 if len(times) >= 12 else 0,
            'ao100': stats.ao100 if len(times) >= 100 else 0,
            'best_ao5': stats.best_ao5 if len(times) >= 5 else 0,
            'best_ao12': best_ao12,
            'best_ao100': stats.best_ao100 if len(times) >= 100 else 0,
            'best': stats.best,
            'total': len(times),
            'month': sum(
                solve.datetime.astimezone().date() > month
                for solve in timeline
            ),
            'chart': {
                'points': [seconds(time) for time in times[-FORM_SOLVES:]],
                'ao12': rolling_average(times, 12)[-FORM_SOLVES:],
                'best': (seconds(best_ao12) or 0),
            },
        }

    @staticmethod
    def session_tables(
            sessions: dict[int, dict[str, SessionInfo]],
    ) -> list[SessionTable]:
        """
        Lay the sessions of every puzzle, the last played first.

        Returns:
            One table per puzzle with sessions, the whole of them last.

        """
        tables: list[SessionTable] = []
        for cube, cube_sessions in sessions.items():
            rows = sorted(
                (
                    SessionListView.session_row(cube, name, info['solves'])
                    for name, info in cube_sessions.items()
                    if name != 'all'
                ),
                key=itemgetter('last'),
                reverse=True,
            )
            if not rows:
                continue
            if 'all' in cube_sessions:
                rows.append(SessionListView.session_row(
                    cube, 'all', cube_sessions['all']['solves'],
                ))
            tables.append({
                'cube': cube,
                'name': f'{ cube }x{ cube }x{ cube }',
                'count': sum(
                    len(info['solves'])
                    for name, info in cube_sessions.items()
                    if name != 'all'
                ),
                'rows': rows,
            })
        return tables

    @staticmethod
    def session_row(cube: int, name: str,
                    solves: list['Solve']) -> SessionRow:
        """
        Measure a session for the table of the dashboard.

        Returns:
            Its counts, best single, current and best Ao12, last solve
            and last times.

        """
        ordered = sorted(solves, key=lambda solve: solve.datetime)
        times = [solve.final_time for solve in ordered]
        stats = Statistics(times)
        enough = len(times) >= 12
        session = name or 'default'

        return {
            'label': (
                'All sessions' if name == 'all'
                else format_session_name(session)
            ),
            'url': SolveLocation.session_url(cube, session),
            'count': len(times),
            'best': stats.best,
            'ao12': stats.ao12 if enough else 0,
            'best_ao12': stats.best_ao12 if enough else 0,
            'last': ordered[-1].datetime,
            'spark': [seconds(time) for time in times[-SPARK_SOLVES:]],
            'total': name == 'all',
        }

    @staticmethod
    def recent(timeline: list['Solve'], logbook: set[int]) -> list[RecentSolve]:
        """
        List the last solves, the daily ones named by their day.

        Args:
            timeline: Solves of the main puzzle, oldest first.
            logbook: Identities of the daily solves among them.

        Returns:
            The last solves, the most recent first.

        """
        recent: list[RecentSolve] = []
        for solve in reversed(timeline[-RECENT_SOLVES:]):
            if id(solve) in logbook:
                label = 'Daily'
                detail = (
                    f'{ short_date(date.fromisoformat(solve.session)) }'
                    f' #{ solve.solve_id }'
                )
                url = DailyLocation.session_url(solve.cube_size, solve.session)
            else:
                session = solve.session or 'default'
                label = format_session_name(session)
                detail = f'#{ solve.solve_id }'
                url = SolveLocation.session_url(solve.cube_size, session)
            recent.append({
                'label': label,
                'detail': detail,
                'url': f'{ url }{ solve.solve_id }/',
                'time': solve.final_time,
                'moment': solve.datetime,
                'grade': (
                    format_grade(solve.score)
                    if solve.advanced and solve.score is not None else ''
                ),
                'fluency': solve.fluency if solve.advanced else 0,
            })
        return recent

    @staticmethod
    def career(timeline: list['Solve'], logbook: set[int],
               today: date) -> CareerChart | None:
        """
        Lay every solve on the calendar, with the rolling Ao100.

        Args:
            timeline: Solves of the main puzzle, oldest first.
            logbook: Identities of the daily solves among them.
            today: Last day of the chart.

        Returns:
            The data of the career chart, None without a timed solve.

        """
        timed = [solve for solve in timeline if solve.final_time > 0]
        if not timed:
            return None

        start = timed[0].datetime.astimezone().date()
        points: list[CareerPoint] = []
        last_played: dict[str, datetime] = {}
        for solve in timed:
            key = (
                LOGBOOK if id(solve) in logbook
                else solve.session or 'default'
            )
            last_played[key] = solve.datetime
            points.append({
                'x': (solve.datetime.astimezone().date() - start).days,
                'y': round(solve.final_time / SECOND, 3),
                'k': key,
            })

        average = rolling_average(
            [solve.final_time for solve in timed], CAREER_AVERAGE,
        )
        line: list[CareerLinePoint] = [
            {'x': point['x'], 'y': value}
            for point, value in zip(points, average, strict=True)
            if value is not None
        ]
        line = line[::CAREER_LINE_STEP]

        labels = {
            key: 'Daily logbook' if key == LOGBOOK
            else format_session_name(key)
            for key in last_played
        }
        kinds: list[CareerKind] = [
            {
                'key': key,
                'label': labels[key],
                'role': CAREER_ROLES[index % len(CAREER_ROLES)],
            }
            for index, key in enumerate(
                sorted(last_played, key=last_played.__getitem__,
                       reverse=True),
            )
        ]
        times = [point['y'] for point in points]

        return {
            'start': start.isoformat(),
            'days': max(1, (today - start).days),
            'points': points,
            'line': line,
            'floor': CAREER_FLOOR_STEP * int(min(times) // CAREER_FLOOR_STEP),
            'ceiling': quantile(times, CAREER_CEILING),
            'kinds': kinds,
            'labels': labels,
        }

    @staticmethod
    def forecast(today: date) -> ForecastSummary:
        """
        Add up the reviews of every step, day by day.

        Returns:
            The overdue reviews then the next days, and the busiest day.

        """
        forecast = TrainingForecastView.build_forecast(
            TrainingForecastView.read_steps(),
            datetime.now().astimezone(),
        )
        days: list[ForecastDay] = [
            {
                'label': label,
                'short': 'Due' if not index else (
                    f'{ today + timedelta(days=index - 1):%a}'[:2]
                ),
                'total': sum(
                    series['data'][index] for series in forecast['series']
                ),
            }
            for index, label in enumerate(forecast['labels'][:FORECAST_DAYS])
        ]
        return {
            'days': days,
            'peak': max((day['total'] for day in days), default=0) or 1,
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
        self.all_solves = False

        solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
            directory=SolveLocation.directory,
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
        case_tables = self.compute_case_tables()
        session_series = self.compute_session_series()
        trend = self.compute_trend()

        return {
            'cube': self.cube,
            'session': self.session,
            'stats': self.stats,
            'punchcard': self.compute_punchcard(),
            'step': self.step,
            'case_uid': self.case_uid,
            'method_aggregation': self.method_aggregation,
            'today': datetime.now().astimezone().date(),
            'label': (
                'All sessions' if self.session == 'all'
                else format_session_name(self.session)
            ),
            'breadcrumb': [
                {'label': 'Home', 'href': '/'},
                {'label': f'{ self.cube }x{ self.cube }x{ self.cube }',
                 'href': '/#sessions'},
                {'label': format_session_name(self.session), 'href': ''},
            ],
            'board': self.compute_board(session_series),
            'switch': self.compute_switch(),
            'activity': self.compute_activity(),
            'trend_chart': self.compute_trend_chart(trend),
            'distribution_chart': self.compute_distribution_chart(),
            'solve_rows': self.compute_solve_rows(),
            'case_tables': case_tables,
            'solve_tabs': [('solves', f'Solves · { self.stats.total }')] + [
                (table['step'],
                 f'{ table["step"].upper() } · { len(table["rows"]) }')
                for table in case_tables
            ],
            'available_methods': list(METHOD_ANALYSERS.keys()),
            'method_name': self.method_name,
        }

    def listing(self, *, all_solves: bool) -> 'SessionDetailView':
        """
        List every solve instead of the last ones.

        Args:
            all_solves: Whether every solve is asked for, by
                ?solves=all in the URL.

        Returns:
            The view itself.

        """
        self.all_solves = all_solves
        return self

    def compute_board(
            self, session_series: list[SessionSeriesEntry],
    ) -> list[BoardRow]:
        """
        Set the last single and every current average against its best.

        Args:
            session_series: The configured session averages.

        Returns:
            The single first, then the configured session averages.

        """
        board: list[BoardRow] = [{
            'label': 'Single',
            'value': self.stats.stack[-1].final_time,
            'best': self.stats.best,
        }]
        board.extend(
            {'label': entry['label'], 'value': entry['value'],
             'best': entry['best']}
            for entry in session_series
        )
        return board

    def compute_switch(self) -> list[SessionSwitchItem]:
        """
        List the sessions of the puzzle, from their files.

        The solves are counted without being loaded: a file holds the
        list of its solves.

        Returns:
            Every session with solves, the whole of them last.

        """
        prefix = f'{ self.cube }x{ self.cube }x{ self.cube }'
        counts: dict[str, int] = {}
        for path in sorted(SolveLocation.directory.glob(f'{ prefix }*.json')):
            name = path.stem.removeprefix(prefix).removeprefix('-')
            if path.stem != prefix and not path.stem.startswith(f'{ prefix }-'):
                continue
            with path.open(encoding='utf-8') as fd:
                count = len(json.load(fd))
            if count:
                counts[name or 'default'] = count

        switch: list[SessionSwitchItem] = [
            {
                'label': format_session_name(name),
                'url': SolveLocation.session_url(self.cube, name),
                'count': count,
                'current': name == self.session,
            }
            for name, count in sorted(counts.items())
        ]
        if len(counts) > 1:
            switch.append({
                'label': 'All',
                'url': SolveLocation.session_url(self.cube, 'all'),
                'count': sum(counts.values()),
                'current': self.session == 'all',
            })
        return switch

    def compute_activity(self) -> ActivityCalendarData:
        """
        Lay the solves of the session on the weeks it spans.

        Returns:
            The calendar, ending with the day of the last solve.

        """
        first = self.stats.stack[0].datetime.astimezone().date()
        last = self.stats.stack[-1].datetime.astimezone().date()
        return ActivityCalendar.from_moments(
            solve.datetime for solve in self.stats.stack
        ).layout(last, ActivityCalendar.span_weeks(first, last))

    @staticmethod
    def compute_trend_chart(trend: TrendData) -> TrendChart:
        """
        Prepare the progress chart: a DNF is no point, and the scale stops
        above most solves.

        Args:
            trend: Times and rolling averages of the session.

        Returns:
            The chart data and its legend.

        """
        times: list[float | None] = [time or None for time in trend['times']]
        return {
            'indices': trend['indices'],
            'times': times,
            'series': [
                {'label': series['label'], 'data': series['data']}
                for series in trend['series']
            ],
            'ceiling': quantile(
                [time for time in times if time], TREND_CEILING,
            ),
            'legend': [('dot', 'Solve')] + [
                (TREND_KEYS[index % len(TREND_KEYS)], series['label'])
                for index, series in enumerate(trend['series'])
            ],
        }

    def compute_distribution_chart(self) -> DistributionChart:
        """
        Name the most frequent bucket of the distribution.

        Returns:
            The buckets, their counts and the mode.

        """
        distribution = self.compute_distribution()
        counts = distribution['counts']
        mode = (
            distribution['labels'][counts.index(max(counts))]
            if counts else ''
        )
        return {
            'labels': distribution['labels'],
            'counts': counts,
            'mode': mode,
        }

    def compute_solve_rows(self) -> list['Solve']:
        """
        List the solves, the most recent first.

        Returns:
            The last solves, or all of them when asked.

        """
        solves = list(reversed(self.stats.stack))
        return solves if self.all_solves else solves[:SOLVES_SHOWN]

    def compute_case_tables(self) -> list[CaseTable]:
        """
        Measure the cases met in each step, the most met first.

        The frequency bar is scaled on the most frequent case, its tick
        on the probability of the case.

        Returns:
            One table per step of the method with cases.

        """
        method = self.method_aggregation.analyser.name.lower()
        tables: list[CaseTable] = []
        for step, cases in self.method_aggregation.results['cases'].items():
            peak = max(
                (max(case['frequency'], case['case'].probability)
                 for case in cases.values()),
                default=0,
            ) or 1
            rows: list[CaseRow] = []
            for case in sorted(
                    cases.values(), key=itemgetter('count'), reverse=True):
                info = case['case']
                rows.append({
                    'case': info,
                    'name': info.pretty_name,
                    'setup': (
                        '' if info.code == 'SKIP'
                        else str(info.main_algorithm)
                    ),
                    'count': case['count'],
                    'frequency': case['frequency'],
                    'probability': info.probability,
                    'seen': round(100 * case['frequency'] / peak, 1),
                    'expected': round(100 * info.probability / peak, 1),
                    'overrepresented': (
                        case['frequency'] > OVERREPRESENTED * info.probability
                    ),
                    'recognition': case['recognition'],
                    'execution': case['execution'],
                    'time': case['time'],
                    'recognition_share': (
                        round(100 * case['recognition'] / case['time'], 1)
                        if case['time'] else 0
                    ),
                    'qtm': case['qtm'],
                    'tps': case['tps'],
                    'etps': case['etps'],
                    'filter_url': (
                        f'?m={ method }&step={ step }'
                        f'&case_uid={ info.code.lower() }'
                    ),
                })
            tables.append({'step': step, 'rows': rows})
        return tables

    def compute_session_series(self) -> list[SessionSeriesEntry]:
        """
        Build the configurable session rolling averages.

        Returns:
            One entry per ``STATS_SESSION_SERIES`` average with enough
            solves (``total >= size``), each carrying its current value
            and the session best for that average.

        """
        total = self.stats.total
        stack_time = list(self.stats.stack_time)

        series: list[SessionSeriesEntry] = []
        for kind, size in STATS_SESSION_SERIES:
            if total < size:
                continue

            value = getattr(self.stats, kind)(size, stack_time)
            best = getattr(self.stats, f'best_{ kind }')(size)
            series.append({
                'token': f'{ kind }{ size }',
                'label': SeriesReporter.series_label(kind, size),
                'size': size,
                'value': value,
                'best': best,
            })

        return series

    def compute_trend(self) -> TrendData:
        """
        Calculate rolling averages and time trends.

        Returns:
            Dictionary with solve indices, times, and the rolling-average
            series configured in ``STATS_GRAPH_SERIES``. Only series with
            enough solves (``total >= size``) are included.

        """
        total = self.stats.total
        active = [
            (kind, size)
            for kind, size in STATS_GRAPH_SERIES
            if total >= size
        ]
        series_values: list[list[float | None]] = [[] for _ in active]
        times: list[float] = []
        indices: list[str] = []

        stack_time = list(self.stats.stack_time)
        for i, time in enumerate(stack_time):
            times.append(time / SECOND)
            indices.append(str(i + 1))

            window = stack_time[:i + 1]
            for index, (kind, size) in enumerate(active):
                value = getattr(self.stats, kind)(size, window)
                series_values[index].append(
                    value / SECOND if value > 0 else None,
                )

        series: list[TrendSeries] = []
        for (kind, size), values in zip(active, series_values, strict=True):
            token = f'{kind}{size}'
            series.append({
                'token': token,
                'label': token.upper(),
                'size': size,
                'data': values,
            })

        return {
            'indices': indices,
            'times': times,
            'series': series,
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
            dist_labels.append(f'{edge:g}s')
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
