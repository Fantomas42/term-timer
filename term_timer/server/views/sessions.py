"""Session list and detail views."""
from typing import TYPE_CHECKING
from typing import cast

from bottle import abort

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.config import CUBE_METHOD
from term_timer.constants import CUBE_SIZES
from term_timer.constants import SECOND
from term_timer.in_out import load_all_solves
from term_timer.server.annotations import DistributionData
from term_timer.server.annotations import SessionDetailContext
from term_timer.server.annotations import SessionInfo
from term_timer.server.annotations import SessionListContext
from term_timer.server.annotations import TrendData
from term_timer.server.views.base import View
from term_timer.stats import SolveStatisticsReporter
from term_timer.stats import Statistics

if TYPE_CHECKING:
    from term_timer.methods.base import Analyser
    from term_timer.solve import Solve


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
