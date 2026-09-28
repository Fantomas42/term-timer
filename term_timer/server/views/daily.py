"""Daily sessions views: one scramble per day, attempted several times."""
from datetime import date
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Final
from typing import cast

from bottle import abort

from term_timer.aggregator import SolvesDoctorAggregator
from term_timer.config import CUBE_METHOD
from term_timer.constants import CUBE_SIZES
from term_timer.constants import DAILY_DAYS_LISTED
from term_timer.constants import DAILY_DIRECTORY
from term_timer.constants import DAILY_TIMES_CEILING
from term_timer.constants import DAILY_ZONE_EDGES
from term_timer.constants import SECOND
from term_timer.constants import WEEK_DAYS
from term_timer.doctor import group_doctor_findings
from term_timer.in_out import load_all_daily_solves
from term_timer.in_out import load_solves
from term_timer.interface.doctor import DoctorReporter
from term_timer.server.activity import ActivityCalendar
from term_timer.server.activity import DailyActivityCalendar
from term_timer.server.annotations import ActivityCalendarData
from term_timer.server.annotations import BreadcrumbItem
from term_timer.server.annotations import DailyAttemptsChart
from term_timer.server.annotations import DailyBannerInfo
from term_timer.server.annotations import DailyDayContext
from term_timer.server.annotations import DailyDayRow
from term_timer.server.annotations import DailyDoctorGroup
from term_timer.server.annotations import DailyListContext
from term_timer.server.annotations import DailyRecord
from term_timer.server.annotations import DailySeries
from term_timer.server.annotations import DailyStepSeries
from term_timer.server.annotations import DailyTimesChart
from term_timer.server.annotations import DailyToday
from term_timer.server.views.base import View
from term_timer.server.views.scramble import ScrambleDetailView
from term_timer.server.views.solves import SolveDeleteView
from term_timer.server.views.solves import SolveDetailView
from term_timer.server.views.solves import SolveLocation
from term_timer.server.views.solves import SolveUpdateCommentView
from term_timer.server.views.solves import SolveUpdateFlagView
from term_timer.stats import DailySummaryReporter
from term_timer.stats import Statistics

if TYPE_CHECKING:
    from term_timer.methods.base import Analyser


# Legend keys of the step series, in the colour order of daily-steps.
STEP_LEGEND_KEYS: Final = ('3', '4', '5', '1')


class DailyLocation(SolveLocation):
    """Daily sessions, stored and served apart from the regular ones."""

    directory = DAILY_DIRECTORY
    url_prefix = '/daily'

    @classmethod
    def day_url(cls, cube: int, day: date) -> str:
        """
        Build the URL of the daily session of a day.

        Returns:
            Absolute path of the day page.

        """
        return cls.session_url(cube, day.isoformat())

    @classmethod
    def breadcrumb(cls, cube: int, session: str,
                   solve_id: int) -> list[BreadcrumbItem]:
        """
        Build the breadcrumb of a daily attempt, its session being a day.

        Returns:
            Home, the daily hub, the day, then the attempt itself.

        """
        return [
            {'label': 'Home', 'href': '/'},
            {
                'label': f'Daily { cube }x{ cube }x{ cube }',
                'href': f'{ cls.url_prefix }/{ cube }/',
            },
            {'label': session, 'href': cls.session_url(cube, session)},
            {'label': f'#{ solve_id }', 'href': ''},
        ]

    @classmethod
    def logbook_breadcrumb(cls, cube: int) -> list[BreadcrumbItem]:
        """
        Build the breadcrumb of the logbook of a cube.

        Returns:
            Home, then the logbook itself.

        """
        return [
            {'label': 'Home', 'href': '/'},
            {'label': f'Daily { cube }x{ cube }x{ cube }', 'href': ''},
        ]

    @classmethod
    def day_breadcrumb(cls, cube: int, day: str) -> list[BreadcrumbItem]:
        """
        Build the breadcrumb of the page of a day.

        Returns:
            Home, the logbook, then the day itself.

        """
        logbook = cls.logbook_breadcrumb(cube)
        logbook[-1]['href'] = f'{ cls.url_prefix }/{ cube }/'
        return [*logbook, {'label': day, 'href': ''}]


class DailyListView(DailyLocation, View):
    """View of the logbook of every daily session of a cube."""

    template_name = 'daily.html'

    def __init__(self, cube: int, today: date | None = None) -> None:
        """
        Initialize the daily hub view.

        Args:
            cube: Cube size (2-7).
            today: Reference day of the streaks, defaulting to today.

        """
        if cube not in CUBE_SIZES:
            abort(404, 'Invalid cube size')

        self.cube = cube
        self.summary = DailySummaryReporter(
            cube, load_all_daily_solves(cube), today,
        )

    @staticmethod
    def series(
            summary: DailySummaryReporter, days: list[date],
    ) -> DailySeries:
        """
        Build the values drawn for each day of a graph.

        Each day is represented by its best and its first attempt, never
        by a mean: no value pools the solves of several days.

        Returns:
            Best and first attempt in seconds, None when the day holds
            none, and the number of attempts of each day.

        """
        best: list[float | None] = []
        first: list[float | None] = []

        for day in days:
            stats = summary.days.get(day)
            best.append(stats.best / SECOND if stats else None)
            cold = summary.first_attempts.get(day, 0)
            first.append(cold / SECOND if cold else None)

        return {
            'labels': [day.isoformat() for day in days],
            'best': best,
            'first': first,
            'attempts': [len(summary.sessions.get(day, [])) for day in days],
        }

    @classmethod
    def banner(
            cls, cube: int, today: date | None = None,
    ) -> DailyBannerInfo:
        """
        Build the teaser of the daily of the day, shown on the dashboard.

        Returns:
            Streaks, state and best of the day, its scramble, and the
            best of the last days.

        """
        summary = DailySummaryReporter(
            cube, load_all_daily_solves(cube), today,
        )
        day = summary.today
        stats = summary.days.get(day)

        window = [
            day - timedelta(days=offset)
            for offset in reversed(range(DAILY_DAYS_LISTED))
        ]
        url = (
            cls.day_url(cube, day)
            if day in summary.sessions
            else f'{ cls.url_prefix }/{ cube }/'
        )

        return {
            'cube': cube,
            'day': day.isoformat(),
            'number': summary.day_number(day),
            'done': summary.daily_done,
            'streak': len(summary.current_streak),
            'record': len(summary.longest_streak),
            'best': stats.best if stats else 0,
            'attempts': len(summary.sessions.get(day, [])),
            'scramble': ScrambleDetailView(
                cube, day.isoformat(), 1,
            ).get_scramble(),
            'url': url,
            'series': cls.series(summary, window),
            'zone_edges': DAILY_ZONE_EDGES,
        }

    def get_context(self) -> DailyListContext:
        """
        Build context with the participation and the days of the daily.

        Returns:
            Dictionary containing the summary, the rows, the records,
            the activity and the times chart of the daily.

        """
        series = self.series(self.summary, self.summary.played_days)

        return {
            'cube': self.cube,
            'summary': self.summary,
            'rows': self.compute_rows(),
            'records': self.compute_records(),
            'zone_edges': DAILY_ZONE_EDGES,
            'breadcrumb': self.logbook_breadcrumb(self.cube),
            'today': self.compute_today(),
            'activity': self.compute_activity(),
            'times_chart': self.compute_times_chart(series),
            'record_days': [
                day.isoformat() for day, _best in self.summary.records
            ],
        }

    def compute_today(self) -> DailyToday:
        """
        Present the daily of the day, played or still to play.

        Returns:
            The day, its number, its scramble and its page, empty until
            it has a session.

        """
        summary = self.summary
        day = summary.today
        number = summary.day_number(day) or len(summary.played_days) + 1

        return {
            'day': day,
            'number': number,
            'scramble': ScrambleDetailView(
                self.cube, day.isoformat(), 1,
            ).get_scramble(),
            'url': (
                self.day_url(self.cube, day)
                if day in summary.sessions else ''
            ),
        }

    def compute_activity(self) -> ActivityCalendarData | None:
        """
        Lay the attempts of each daily on the punchcard, over the span
        of the daily.

        Returns:
            The calendar, None without daily session.

        """
        sessions = self.summary.sessions
        if not sessions:
            return None

        first = next(iter(sessions))
        today = self.summary.today

        return DailyActivityCalendar(
            {day: len(times) for day, times in sessions.items()},
            first,
            f'{ self.url_prefix }/{ self.cube }/',
        ).layout(today, ActivityCalendar.span_weeks(first, today))

    @staticmethod
    def compute_times_chart(series: DailySeries) -> DailyTimesChart | None:
        """
        Frame the best and first attempt of each played day on the zones.

        The axis stops at a high percentile of the times: a rare slow
        first attempt would squash every other day.

        Returns:
            The chart data, None without played day.

        """
        values = sorted(
            value
            for value in series['best'] + series['first']
            if value is not None
        )
        if not values:
            return None

        index = int(len(values) * DAILY_TIMES_CEILING)
        top = values[min(len(values) - 1, index)]
        ceiling = 5 * (int(top) // 5 + 1)

        return {
            'labels': series['labels'],
            'best': series['best'],
            'first': series['first'],
            'edges': DAILY_ZONE_EDGES,
            'floor': 5 * (int(values[0]) // 5),
            'ceiling': ceiling,
            'clipped': sum(value > ceiling for value in values),
        }

    def compute_rows(self) -> list[DailyDayRow]:
        """
        Sum up every daily session on a row, newest day first.

        Days never solved are listed too: their session exists, their
        attempts can be read and flagged.

        Returns:
            One row per daily session.

        """
        summary = self.summary
        rows: list[DailyDayRow] = []

        for day, times in reversed(summary.sessions.items()):
            stats = summary.days.get(day)
            rows.append({
                'day': day.isoformat(),
                'weekday': WEEK_DAYS[day.weekday()],
                'number': summary.day_number(day),
                'attempts': len(times),
                'first': times[0],
                'best': stats.best if stats else 0,
                'gain': summary.warmup_gains.get(day),
                'times': times,
                'zones': [summary.zone_index(time) for time in times],
            })

        return rows

    def compute_records(self) -> list[DailyRecord]:
        """
        List the staircase of the daily personal best, newest first.

        Returns:
            Each record with the time it took off the previous one, 0
            for the very first.

        """
        records: list[DailyRecord] = []
        previous = 0

        for day, best in self.summary.records:
            records.append({
                'day': day.isoformat(),
                'best': best,
                'gain': previous - best if previous else 0,
            })
            previous = best

        return list(reversed(records))


class DailyDayView(DailyLocation, View):
    """View of the card of a single daily session."""

    template_name = 'daily_day.html'

    def __init__(self, cube: int, day: str) -> None:
        """
        Initialize the daily session view.

        Args:
            cube: Cube size (2-7).
            day: Day of the daily session, as YYYY-MM-DD.

        """
        try:
            self.date = date.fromisoformat(day)
        except ValueError:
            abort(404, 'Invalid day')

        self.cube = cube
        self.day = day

        self.solves = load_solves(cube, day, directory=self.directory)
        if not self.solves:
            abort(404, 'No daily solve on this day')

        self.summary = DailySummaryReporter(
            cube, load_all_daily_solves(cube),
        )

    def get_context(self) -> DailyDayContext:
        """
        Build context with the attempts of the day and their analysis.

        Returns:
            Dictionary containing the day, its attempts, their zones and
            steps, the doctor of the scramble and the share card.

        """
        days = list(self.summary.sessions)
        index = days.index(self.date)
        previous_day = days[index - 1].isoformat() if index else None
        next_day = (
            days[index + 1].isoformat() if index + 1 < len(days) else None
        )

        times = [solve.final_time for solve in self.solves]
        zones = [self.summary.zone_index(time) for time in times]
        doctor_total, doctor = self.compute_doctor()
        steps = self.compute_steps()

        return {
            'cube': self.cube,
            'day': self.day,
            'number': self.summary.day_number(self.date),
            'previous_day': previous_day,
            'next_day': next_day,
            'scramble': self.solves[0].scramble,
            'solves': self.solves,
            'stats': Statistics(times),
            'zones': zones,
            'times': [time / SECOND if time else None for time in times],
            'steps': steps,
            'doctor_total': doctor_total,
            'doctor': doctor,
            'share': self.summary.share_card(self.date),
            'zone_edges': DAILY_ZONE_EDGES,
            'breadcrumb': self.day_breadcrumb(self.cube, self.day),
            'previous_url': (
                self.session_url(self.cube, previous_day)
                if previous_day else ''
            ),
            'next_url': (
                self.session_url(self.cube, next_day) if next_day else ''
            ),
            'record': any(
                day == self.date for day, _best in self.summary.records
            ),
            'attempt_urls': [
                f'{ self.session_url(self.cube, self.day) }{ solve.solve_id }/'
                for solve in self.solves
            ],
            'attempts_chart': self.compute_attempts_chart(times, zones),
            'steps_chart': {
                'labels': [f'#{ solve.solve_id }' for solve in self.solves],
                'steps': steps,
            },
            'steps_legend': [
                (STEP_LEGEND_KEYS[index % len(STEP_LEGEND_KEYS)],
                 step['label'])
                for index, step in enumerate(steps)
            ],
        }

    def compute_attempts_chart(
            self, times: list[int], zones: list[int | None],
    ) -> DailyAttemptsChart:
        """
        Lay the attempts of the day in order, each on its zone.

        Returns:
            The chart data, the best attempt outlined, None for a DNF.

        """
        seconds = [time / SECOND if time else None for time in times]
        valid = [value for value in seconds if value is not None]
        best = seconds.index(min(valid)) if valid else None
        ceiling = 5 * (int(max(valid)) // 5 + 1) if valid else 0

        return {
            'labels': [f'#{ solve.solve_id }' for solve in self.solves],
            'times': seconds,
            'zones': zones,
            'best': best,
            'edges': DAILY_ZONE_EDGES,
            'ceiling': max(ceiling, DAILY_ZONE_EDGES[-1] + 5),
        }

    def compute_steps(self) -> list[DailyStepSeries]:
        """
        Split each attempt into the time spent on each step.

        Steps are gathered on their family, the F2L pairs making one F2L,
        so that what melted between the first attempt and the best one
        reads at a glance.

        Returns:
            One series per step, None for an attempt without analysis,
            empty when no attempt of the day can be analysed.

        """
        names: list[str] = []
        attempts: list[dict[str, float] | None] = []

        for solve in self.solves:
            if not solve.analysable:
                attempts.append(None)
                continue

            totals: dict[str, float] = {}
            analyser = cast('Analyser', solve.method_applied)
            for step in analyser.summary:
                if step['type'] == 'virtual':
                    continue

                name = step['name'].split(' ')[0]
                if name not in names:
                    names.append(name)
                totals[name] = totals.get(name, 0.0) + step['total'] / SECOND

            attempts.append(totals)

        return [
            {
                'label': name,
                'data': [
                    totals.get(name, 0.0) if totals is not None else None
                    for totals in attempts
                ],
            }
            for name in names
        ]

    def compute_doctor(self) -> tuple[int, list[DailyDoctorGroup]]:
        """
        Diagnose the attempts of the day together, as the CLI does.

        Every attempt solves the same scramble: a finding recurring at a
        location names a weakness on that very case.

        Returns:
            The number of diagnosed attempts and the findings grouped by
            location, 0 and empty without analysable attempt.

        """
        analysable = [solve for solve in self.solves if solve.analysable]
        if not analysable:
            return 0, []

        results = SolvesDoctorAggregator(CUBE_METHOD, analysable).results

        groups: list[DailyDoctorGroup] = []
        for group in group_doctor_findings(results['findings']):
            location = group['location']
            groups.append({
                'location': 'Global' if location == 'global' else location,
                'command': group['command'],
                'impact': group['impact_per_solve'],
                'findings': [
                    {
                        'title': DoctorReporter.finding_title(finding),
                        'severity': finding['severity'],
                        'impact': finding['impact_per_solve'],
                        'frequency': finding['frequency'],
                        'recommendation': finding['recommendation'],
                    }
                    for finding in group['findings']
                ],
            })

        return results['total'], groups


class DailySolveDetailView(DailyLocation, SolveDetailView):
    """View for displaying the detailed analysis of a daily attempt."""


class DailySolveUpdateFlagView(DailyLocation, SolveUpdateFlagView):
    """View for updating the flag of a daily attempt."""


class DailySolveUpdateCommentView(DailyLocation, SolveUpdateCommentView):
    """View for updating the comment of a daily attempt."""


class DailySolveDeleteView(DailyLocation, SolveDeleteView):
    """View for deleting a daily attempt."""
