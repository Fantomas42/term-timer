"""Tests for the V2 dashboard and session pages, and their helpers."""
import json
import re
import tempfile
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest import TestCase
from unittest.mock import patch

from term_timer.server.activity import ActivityCalendar
from term_timer.server.filters import days_ago
from term_timer.server.filters import hours
from term_timer.server.filters import short_date
from term_timer.server.filters import short_time
from term_timer.server.filters import sparkline
from term_timer.server.filters import weekday
from term_timer.server.views.sessions import SessionListView
from term_timer.solve import Solve
from term_timer.tests.test_server_solve import DAY
from term_timer.tests.test_server_solve import ESCAPED_V1_RE
from term_timer.tests.test_server_solve import SCRAMBLE
from term_timer.tests.test_server_solve import SECOND
from term_timer.tests.test_server_solve import SESSION
from term_timer.tests.test_server_solve import SolveServerTestCase

if TYPE_CHECKING:
    from term_timer.server.annotations import CareerChart
    from term_timer.server.annotations import DashboardForm
    from term_timer.server.filters import SparkLine

ROW_RE = re.compile(r'<tr class="session-solve"')
SINGLE_ROW_RE = re.compile(
    r'<tr class="session-board-row"( data-record)?>\s*'
    r'<th scope="row">Single</th>',
)


class TestTimeFilters(TestCase):
    """Times and durations as the dashboard reads them."""

    def test_short_time(self) -> None:
        """Leading zeros go, milliseconds stay, a DNF is named."""
        self.assertEqual(short_time(25_108_000_000), '25.108')
        self.assertEqual(short_time(61_234_000_000), '1:01.234')
        self.assertEqual(short_time(0), 'DNF')

    def test_hours(self) -> None:
        """Minutes alone under an hour, then hours and minutes."""
        self.assertEqual(hours(25 * 60 * SECOND), '25 min')
        self.assertEqual(hours(100 * 60 * SECOND + 4 * SECOND), '1 h 40')
        self.assertEqual(hours(0), '0 min')


class TestDayFilters(TestCase):
    """Days in words, from dates, moments or ISO days."""

    today = date(2026, 9, 27)

    def test_days_ago(self) -> None:
        """Days, then weeks, then months."""
        cases = {
            0: 'today',
            1: 'yesterday',
            5: '5 days ago',
            13: '13 days ago',
            21: '3 weeks ago',
            200: '6 months ago',
        }
        for days, expected in cases.items():
            with self.subTest(days=days):
                day = self.today - timedelta(days=days)
                self.assertEqual(days_ago(day, self.today), expected)

    def test_days_ago_future(self) -> None:
        """A day ahead, from a clock drift, reads as today."""
        self.assertEqual(
            days_ago(self.today + timedelta(days=2), self.today), 'today',
        )

    def test_value_kinds(self) -> None:
        """A moment gives its local day, an ISO string its day."""
        moment = datetime(2026, 9, 26, 12, tzinfo=UTC)
        self.assertEqual(days_ago(moment, self.today), 'yesterday')
        self.assertEqual(days_ago('2026-09-26', self.today), 'yesterday')
        self.assertEqual(short_date('2026-09-05'), '5 Sep 2026')
        self.assertEqual(short_date(date(2026, 9, 26)), '26 Sep 2026')

    def test_weekday(self) -> None:
        """The initial of the day, Sunday 27 September 2026 an S."""
        self.assertEqual(weekday(self.today), 'S')
        self.assertEqual(weekday('2026-09-28'), 'M')


class TestSparkline(TestCase):
    """Times drawn in the 100 by 24 box of a sparkline."""

    def test_no_point(self) -> None:
        """Nothing to draw without a time."""
        self.assertIsNone(sparkline([]))
        self.assertIsNone(sparkline([None, None]))

    def test_fastest_at_the_bottom(self) -> None:
        """The fastest time sits on the bottom margin, the slowest on top."""
        found = sparkline([30.0, 20.0, 25.0])
        self.assertIsNotNone(found)
        line = cast('SparkLine', found)
        self.assertEqual(line.path, 'M0.0 2.0 L50.0 22.0 L100.0 12.0')
        self.assertEqual((line.x, line.y), (100.0, 12.0))

    def test_dnf_skipped(self) -> None:
        """A DNF leaves no point, its neighbours are joined."""
        found = sparkline([30.0, None, 20.0])
        self.assertIsNotNone(found)
        line = cast('SparkLine', found)
        self.assertEqual(line.path, 'M0.0 2.0 L100.0 22.0')

    def test_single_point(self) -> None:
        """A single time is drawn at the start, on the bottom margin."""
        found = sparkline([22.0])
        self.assertIsNotNone(found)
        line = cast('SparkLine', found)
        self.assertEqual(line.path, 'M0.0 22.0')


class TestActivityCalendar(TestCase):
    """Solves per day laid on weeks, Monday first."""

    end = date(2026, 9, 27)  # A Sunday.

    def test_levels(self) -> None:
        """One level per edge crossed, from 0 to 4."""
        levels = [ActivityCalendar.level(count)
                  for count in (0, 1, 3, 4, 8, 9, 15, 16, 99)]
        self.assertEqual(levels, [0, 1, 1, 2, 2, 3, 3, 4, 4])

    def test_layout(self) -> None:
        """Whole weeks from Monday, the totals over the shown days only."""
        counts = {
            self.end: 2,
            self.end - timedelta(days=6): 9,
            self.end - timedelta(weeks=60): 50,
        }
        card = ActivityCalendar(counts).layout(self.end)

        self.assertEqual(len(card['weeks']), 53)
        self.assertTrue(all(len(week) == 7 for week in card['weeks']))
        self.assertEqual(card['weeks'][-1][0]['day'], date(2026, 9, 21))
        self.assertEqual(card['weeks'][-1][0]['level'], 3)
        self.assertEqual(card['weeks'][-1][-1]['count'], 2)
        self.assertEqual(card['total'], 11)
        self.assertEqual(card['active'], 2)
        self.assertEqual(card['recent'], 27)

    def test_days_after_the_end(self) -> None:
        """The days of the last week past the end are out of range."""
        end = date(2026, 9, 23)  # A Wednesday.
        card = ActivityCalendar({end + timedelta(days=1): 5}).layout(end)

        last = card['weeks'][-1]
        self.assertEqual([cell['level'] for cell in last[3:]], [-1] * 4)
        self.assertEqual(card['total'], 0)

    def test_months(self) -> None:
        """A month is labelled on the week holding its first day."""
        card = ActivityCalendar({}).layout(self.end, weeks=6)
        self.assertEqual(card['months'], [{'week': 4, 'label': 'Sep'}])

    def test_span_weeks(self) -> None:
        """Half a year at least, a year at most."""
        first = date(2026, 1, 1)
        self.assertEqual(ActivityCalendar.span_weeks(first, first), 26)
        self.assertEqual(
            ActivityCalendar.span_weeks(first, date(2026, 8, 1)), 32,
        )
        self.assertEqual(
            ActivityCalendar.span_weeks(first, date(2028, 1, 1)), 53,
        )

    def test_from_moments(self) -> None:
        """Moments are counted on their local day."""
        moments = [
            datetime(2026, 9, 27, 10, tzinfo=UTC),
            datetime(2026, 9, 27, 11, tzinfo=UTC),
        ]
        calendar = ActivityCalendar.from_moments(moments)
        self.assertEqual(sum(calendar.counts.values()), 2)


class TestDashboardHelpers(TestCase):
    """The figures of the dashboard, from real solves."""

    @staticmethod
    def solve(seconds: float, offset: int, session: str = '',
              solve_id: int = 1) -> Solve:
        """
        Build a solve done some days after 2026-01-01.

        Returns:
            The solve.

        """
        moment = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(
            days=offset,
        )
        return Solve(
            int(moment.timestamp()), int(seconds * SECOND), SCRAMBLE,
            session=session, cube_size=3, solve_id=solve_id,
        )

    def test_form_without_solve(self) -> None:
        """No form without a solve."""
        self.assertIsNone(SessionListView.form([], date(2026, 9, 27)))

    def test_form(self) -> None:
        """Averages of the timeline, the month counted to the day."""
        timeline = [self.solve(20 + index % 5, index) for index in range(30)]
        found = SessionListView.form(timeline, date(2026, 1, 30))
        self.assertIsNotNone(found)
        form = cast('DashboardForm', found)

        self.assertEqual(form['total'], 30)
        self.assertEqual(form['best'], 20 * SECOND)
        self.assertGreater(form['ao12'], 0)
        self.assertEqual(form['ao100'], 0)
        self.assertEqual(form['month'], 30)
        self.assertEqual(len(form['chart']['points']), 30)
        self.assertIsNone(form['chart']['ao12'][10])
        self.assertIsNotNone(form['chart']['ao12'][11])

    def test_career_series(self) -> None:
        """The last played series takes the acid, the daily is named."""
        default = self.solve(30, 0)
        daily = self.solve(25, 10, session='2026-01-11')
        found = SessionListView.career(
            [default, daily], {id(daily)}, date(2026, 1, 20),
        )
        self.assertIsNotNone(found)
        chart = cast('CareerChart', found)

        self.assertEqual(
            [(kind['key'], kind['role']) for kind in chart['kinds']],
            [('logbook', 'chart-1'), ('default', 'chart-3')],
        )
        self.assertEqual(chart['labels']['logbook'], 'Daily logbook')
        self.assertEqual([point['x'] for point in chart['points']], [0, 10])
        self.assertEqual(chart['days'], 19)
        self.assertEqual(chart['floor'], 25)

    def test_career_without_timed_solve(self) -> None:
        """A DNF alone draws no career."""
        dnf = self.solve(0, 0)
        self.assertIsNone(
            SessionListView.career([dnf], set(), date(2026, 1, 2)),
        )

    def test_recent_links(self) -> None:
        """A daily solve links to its day, a regular one to its session."""
        regular = self.solve(30, 0, session='', solve_id=4)
        daily = self.solve(25, 1, session='2026-01-02', solve_id=2)
        recent = SessionListView.recent([regular, daily], {id(daily)})

        self.assertEqual(recent[0]['url'], '/daily/3/2026-01-02/2/')
        self.assertEqual(recent[0]['label'], 'Daily')
        self.assertEqual(recent[0]['detail'], '2 Jan 2026 #2')
        self.assertEqual(recent[1]['url'], '/3/default/4/')
        self.assertEqual(recent[1]['label'], 'Default')

    def test_session_row_all_in_order(self) -> None:
        """The whole of the sessions is measured in the order of time."""
        solves = [self.solve(30, 2), self.solve(20, 0), self.solve(25, 1)]
        row = SessionListView.session_row(3, 'all', solves)

        self.assertEqual(row['label'], 'All sessions')
        self.assertEqual(row['url'], '/3/all/')
        self.assertEqual(row['spark'], [20.0, 25.0, 30.0])
        self.assertTrue(row['total'])
        self.assertEqual(row['ao12'], 0)


class SessionPagesTestCase(SolveServerTestCase):
    """The fixture session and daily, with an empty trainings folder."""

    def setUp(self) -> None:
        """Isolate the trainings too."""
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch(
            'term_timer.in_out.TRAININGS_DIRECTORY', Path(tmp.name),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_many(self, session: str, count: int) -> None:
        """Write a session of plain solves, a minute apart."""
        solves: list[dict[str, Any]] = [
            {'date': 1751570000 + 60 * index,
             'time': (20 + index % 7) * SECOND, 'scramble': SCRAMBLE}
            for index in range(count)
        ]
        self.write(self.solves_directory / f'3x3x3-{ session }.json', solves)


class TestDashboardPage(SessionPagesTestCase):
    """The home page, a dashboard in V2."""

    def setUp(self) -> None:
        """Render the dashboard once per test."""
        super().setUp()
        self.body = self.page('/')

    def test_renders_v2(self) -> None:
        """The V2 page and its seven zones, no V1 markup escaped."""
        self.assertIn('/static/v2/css/pages/home.css', self.body)
        for zone in ('form', 'daily', 'training', 'recent', 'sessions',
                     'activity', 'career'):
            with self.subTest(zone=zone):
                self.assertIn(f'data-zone="{ zone }"', self.body)
        self.assertIsNone(ESCAPED_V1_RE.search(self.body))

    def test_form_hero(self) -> None:
        """The Ao12 is the hero of the form zone, flush under its title."""
        self.assertIn('<div class="hero-time" data-flush>', self.body)
        self.assertIn('Ao12 · your last 12 solves', self.body)

    def test_header(self) -> None:
        """The lookup is the only action of the header."""
        self.assertIn('data-lookup', self.body)
        self.assertIn('data-key="/"', self.body)
        self.assertNotIn('Scrambles', self.body)

    def test_sessions_table(self) -> None:
        """The fixture session is listed, the daily logbook is not."""
        self.assertIn(f'href="/3/{ SESSION }/">Test</a>', self.body)
        self.assertNotIn('Daily logbook</a>', self.body)

    def test_last_solves(self) -> None:
        """The daily solves link to their day."""
        self.assertIn(f'href="/daily/3/{ DAY }/', self.body)

    def test_commands(self) -> None:
        """Without training, the command to start one is given."""
        self.assertIn('data-copy="term-timer daily"', self.body)
        self.assertIn('data-copy="term-timer train"', self.body)
        self.assertIn('No case trained yet.', self.body)

    def test_charts(self) -> None:
        """The form and career charts carry their data, no inline code."""
        for kind in ('form', 'career'):
            with self.subTest(kind=kind):
                self.assertIn(f'data-chart="{ kind }"', self.body)
        data = re.search(
            r'id="career-chart-data">(.*?)</script>', self.body, re.DOTALL,
        )
        self.assertIsNotNone(data)
        career = json.loads(cast('re.Match[str]', data).group(1))
        self.assertEqual(
            {kind['key'] for kind in career['kinds']}, {'logbook', SESSION},
        )

    def test_v1(self) -> None:
        """The V1 dashboard stays behind ?v1."""
        body = self.page('/?v1')
        self.assertIn('academy-banner', body)
        self.assertNotIn('/static/v2/css/pages/home.css', body)


class TestEmptyDashboard(SessionPagesTestCase):
    """The dashboard of a fresh install."""

    def test_no_solve(self) -> None:
        """Every zone says what to do instead of breaking."""
        for path in self.solves_directory.glob('*.json'):
            path.unlink()
        for path in self.daily_directory.glob('*.json'):
            path.unlink()

        body = self.page('/')

        self.assertIn('No solve yet: time a first one.', body)
        self.assertIn('data-copy="term-timer solve"', body)
        self.assertIn('No session yet.', body)
        self.assertNotIn('data-zone="career"', body)


class TestSessionPage(SessionPagesTestCase):
    """The page of a session, in V2."""

    def setUp(self) -> None:
        """Render the fixture session once per test."""
        super().setUp()
        self.body = self.page(f'/3/{ SESSION }/')

    def test_renders_v2(self) -> None:
        """The V2 page and its zones, no V1 markup escaped."""
        self.assertIn('/static/v2/css/pages/session.css', self.body)
        for zone in ('board', 'figures', 'progress', 'solves'):
            with self.subTest(zone=zone):
                self.assertIn(f'data-zone="{ zone }"', self.body)
        self.assertIn('class="punchcard"', self.body)
        self.assertIsNone(ESCAPED_V1_RE.search(self.body))

    def test_board(self) -> None:
        """The last single is a DNF: no gap, no record."""
        single = SINGLE_ROW_RE.search(self.body)
        self.assertIsNotNone(single)
        row = cast('re.Match[str]', single)
        self.assertIsNone(row.group(1))
        self.assertIn('<td class="session-board-current">DNF</td>',
                      self.body)

    def test_switch(self) -> None:
        """The session is marked in the list of its puzzle."""
        self.assertIn(
            f'href="/3/{ SESSION }/" aria-current="page"', self.body,
        )

    def test_method_select(self) -> None:
        """The method is applied as soon as it changes."""
        self.assertIn('name="m" data-autosubmit', self.body)
        self.assertIn('<option value="cfop"', self.body)

    def test_solves(self) -> None:
        """Every solve of a short session, the most recent first."""
        self.assertEqual(len(ROW_RE.findall(self.body)), 3)
        self.assertNotIn('Show all', self.body)
        self.assertLess(self.body.index(f'/3/{ SESSION }/3/'),
                        self.body.index(f'/3/{ SESSION }/1/'))

    def test_comment_escaped(self) -> None:
        """A comment is escaped in the list of solves."""
        self.assertIn('&lt;b&gt;cold&lt;/b&gt; start', self.body)
        self.assertNotIn('<b>cold</b>', self.body)

    def test_v1(self) -> None:
        """The V1 session page stays behind ?v1."""
        body = self.page(f'/3/{ SESSION }/?v1')
        self.assertIn('progressChart', body)
        self.assertNotIn('/static/v2/css/pages/session.css', body)


class TestSessionSolvesShown(SessionPagesTestCase):
    """A long session lists its last solves, all of them when asked."""

    def setUp(self) -> None:
        """Write a session of 55 solves."""
        super().setUp()
        self.write_many('long', 55)

    def test_last_fifty(self) -> None:
        """The last 50, and the link to the others."""
        body = self.page('/3/long/')
        self.assertEqual(len(ROW_RE.findall(body)), 50)
        self.assertIn('Show all 55', body)
        self.assertIn('/3/long/55/', body)
        self.assertNotIn('/3/long/5/"', body)

    def test_all(self) -> None:
        """Every solve with ?solves=all."""
        body = self.page('/3/long/?solves=all')
        self.assertEqual(len(ROW_RE.findall(body)), 55)
        self.assertNotIn('Show all', body)

    def test_all_sessions_switch(self) -> None:
        """The switch counts every session and their whole."""
        body = self.page('/3/long/')
        self.assertIn('Long <span>55</span>', body)
        self.assertIn('All <span>58</span>', body)
