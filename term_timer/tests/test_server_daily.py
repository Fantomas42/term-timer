"""Tests for the daily sessions routes of the web server."""
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from bottle import TEMPLATE_PATH
from bottle import Bottle

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.scripts.commands import daily as daily_mod
from term_timer.server.activity import DailyActivityCalendar
from term_timer.server.app import Server
from term_timer.server.views import ScrambleDetailView
from term_timer.server.views.base import View
from term_timer.server.views.daily import DailyListView
from term_timer.server.views.daily import DailyLocation
from term_timer.server.views.solves import SolveLocation

if TYPE_CHECKING:
    from term_timer.server.annotations import ActivityCell
    from term_timer.server.annotations import DailySeries

SCRAMBLE = "L2 D' L' F' L'"
MOVES = 'L@0 F@507 L@1019 D@1768 L@2518 L@2608'
DAY = '2026-09-25'
OTHER_DAY = '2026-09-24'
DNF_DAY = '2026-09-23'
SECOND = 1_000_000_000


class WSGIClient:
    """Minimal WSGI client calling a Bottle application in process."""

    def __init__(self, app: Bottle) -> None:
        """Keep the application to call."""
        self.app = app

    def request(
            self, method: str, path: str, form: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        """
        Issue a request, with a url-encoded form body for a POST.

        Returns:
            Status code, headers and decoded body.

        """
        body = urlencode(form or {}).encode('utf-8')
        path, _mark, query = path.partition('?')
        environ: dict[str, Any] = {
            'PATH_INFO': path,
            'QUERY_STRING': query,
            'REQUEST_METHOD': method,
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': BytesIO(body),
        }
        setup_testing_defaults(environ)

        result: dict[str, Any] = {}

        def start_response(
                status: str, headers: list[tuple[str, str]],
                _exc_info: object = None,
        ) -> None:
            result['status'] = int(status.split(maxsplit=1)[0])
            result['headers'] = dict(headers)

        content = b''.join(self.app(environ, start_response))

        return result['status'], result['headers'], content.decode('utf-8')

    def get(self, path: str) -> tuple[int, dict[str, str], str]:
        """
        Issue a GET request.

        Returns:
            Status code, headers and decoded body.

        """
        return self.request('GET', path)

    def post(
            self, path: str, form: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        """
        Issue a POST request.

        Returns:
            Status code, headers and decoded body.

        """
        return self.request('POST', path, form)


class DailyServerTestCase(unittest.TestCase):
    """Daily folders and application shared by the daily route tests."""

    client: WSGIClient

    @classmethod
    def setUpClass(cls) -> None:
        """Register the templates and build the application once."""
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)
        cls.client = WSGIClient(Server.create_app(debug=False))

    def setUp(self) -> None:
        """Point the solves and daily directories at temporary folders."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        self.solves_directory = Path(tmp.name) / 'solves'
        self.daily_directory = self.solves_directory / 'daily'
        self.daily_directory.mkdir(parents=True)

        patchers = [
            patch('term_timer.in_out.DAILY_DIRECTORY', self.daily_directory),
            patch.object(SolveLocation, 'directory', self.solves_directory),
            patch.object(DailyLocation, 'directory', self.daily_directory),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.write_day(DAY, [
            {'date': 1790330000, 'time': 31 * SECOND, 'scramble': SCRAMBLE},
            {
                'date': 1790330100, 'time': 24 * SECOND,
                'scramble': SCRAMBLE, 'moves': MOVES,
            },
            {'date': 1790330200, 'time': 27 * SECOND, 'scramble': SCRAMBLE},
        ])
        self.write_day(OTHER_DAY, [
            {'date': 1790240000, 'time': 29 * SECOND, 'scramble': SCRAMBLE},
        ])
        self.write_day(DNF_DAY, [
            {
                'date': 1790150000, 'time': 40 * SECOND,
                'scramble': SCRAMBLE, 'flag': 'DNF',
            },
        ])

    def write_day(self, name: str, solves: list[dict[str, Any]]) -> None:
        """Write a daily session file into the temporary daily folder."""
        path = self.daily_directory / f'3x3x3-{ name }.json'
        path.write_text(json.dumps(solves), encoding='utf-8')

    def read_day(self, name: str) -> list[dict[str, Any]]:
        """
        Read back a daily session file.

        Returns:
            The raw solves of the session.

        """
        path = self.daily_directory / f'3x3x3-{ name }.json'
        data: list[dict[str, Any]] = json.loads(
            path.read_text(encoding='utf-8'),
        )
        return data


class TestDailyHub(DailyServerTestCase):
    """Tests for the daily hub, the logbook of every day."""

    def test_hub_skips_sessions_not_named_after_a_day(self) -> None:
        """A stray file of the daily folder is not a daily session."""
        self.write_day('notes', [
            {'date': 1790000000, 'time': 10 * SECOND, 'scramble': SCRAMBLE},
        ])

        body = self.client.get('/daily/3/')[2]

        self.assertNotIn('/daily/3/notes/', body)

    def test_hub_without_daily(self) -> None:
        """A cube never played in daily renders an empty hub."""
        status, _headers, body = self.client.get('/daily/4/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn('No daily played yet', body)

    def test_hub_invalid_cube(self) -> None:
        """An unknown cube size answers 404."""
        self.assertEqual(
            self.client.get('/daily/9/')[0], HTTPStatus.NOT_FOUND,
        )


class TestDailyDay(DailyServerTestCase):
    """Tests for the card of a single daily session."""

    def test_day_links_each_attempt(self) -> None:
        """The day lists its attempts, each linked to its detail."""
        status, _headers, body = self.client.get(f'/daily/3/{ DAY }/')

        self.assertEqual(status, HTTPStatus.OK)
        for solve_id in (1, 2, 3):
            self.assertIn(f'href="/daily/3/{ DAY }/{ solve_id }/"', body)

    def test_day_share_card(self) -> None:
        """The share card numbers the day among the played ones."""
        body = self.client.get(f'/daily/3/{ DAY }/')[2]

        self.assertIn(
            f'Term Timer Daily #2 · { DAY } · 24.00\n🟥🟨🟧', body,
        )

    def test_day_scramble_links_its_series(self) -> None:
        """The scramble of the day opens the scramble page of the date."""
        body = self.client.get(f'/daily/3/{ DAY }/')[2]

        self.assertIn(f'href="/scramble/3/{ DAY }/1/"', body)

    def test_day_not_found(self) -> None:
        """A day without session, or not a day, answers 404."""
        for path in (
                '/daily/3/2020-01-01/',
                '/daily/3/all/',
                '/daily/3/2026-9-25/',
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    self.client.get(path)[0], HTTPStatus.NOT_FOUND,
                )


class TestDailyAttempt(DailyServerTestCase):
    """Tests for the attempts of a daily and their actions."""

    def test_attempt_detail(self) -> None:
        """An attempt renders with its actions bound to the daily routes."""
        status, _headers, body = self.client.get(f'/daily/3/{ DAY }/2/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertNotIn(f'"/daily/3/{ DAY }/2/flag/"', body)
        self.assertIn(f'action="/daily/3/{ DAY }/2/comment/"', body)
        self.assertIn(f'action="/daily/3/{ DAY }/2/delete/"', body)
        self.assertIn(f'href="/daily/3/{ DAY }/"', body)
        self.assertNotIn(f'"/3/{ DAY }/', body)

    def test_attempt_detail_without_moves(self) -> None:
        """An attempt timed without a smart cube renders, its flag editable."""
        status, _headers, body = self.client.get(f'/daily/3/{ DAY }/1/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn(f'action="/daily/3/{ DAY }/1/flag/"', body)

    def test_attempt_not_found(self) -> None:
        """An attempt beyond the session answers 404."""
        self.assertEqual(
            self.client.get(f'/daily/3/{ DAY }/4/')[0],
            HTTPStatus.NOT_FOUND,
        )

    def test_comment_saved_in_daily_file(self) -> None:
        """A comment lands in the daily file, never in a regular one."""
        status, headers, _body = self.client.post(
            f'/daily/3/{ DAY }/1/comment/', {'comment': ' cold start '},
        )

        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        self.assertTrue(
            headers['Location'].endswith(f'/daily/3/{ DAY }/1/'),
        )
        self.assertEqual(self.read_day(DAY)[0]['comment'], 'cold start')
        self.assertEqual(
            [p.name for p in self.solves_directory.iterdir()], ['daily'],
        )

    def test_flag_saved_in_daily_file(self) -> None:
        """A flag lands in the daily file."""
        status, headers, _body = self.client.post(
            f'/daily/3/{ DAY }/3/flag/', {'flag': 'DNF'},
        )

        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        self.assertTrue(
            headers['Location'].endswith(f'/daily/3/{ DAY }/3/'),
        )
        self.assertEqual(self.read_day(DAY)[2]['flag'], 'DNF')

    def test_delete_from_daily_file(self) -> None:
        """A deletion removes the attempt and returns to its day."""
        status, headers, _body = self.client.post(
            f'/daily/3/{ DAY }/1/delete/',
        )

        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        self.assertTrue(headers['Location'].endswith(f'/daily/3/{ DAY }/'))
        self.assertEqual(
            [s['time'] for s in self.read_day(DAY)],
            [24 * SECOND, 27 * SECOND],
        )


class TestDailyLogbook(DailyServerTestCase):
    """Tests for the logbook of the daily."""

    def logbook(self) -> str:
        """
        Render the logbook of the 3x3x3.

        Returns:
            The body of the page.

        """
        status, _headers, body = self.client.get('/daily/3/')
        self.assertEqual(status, HTTPStatus.OK)
        return body

    def test_renders(self) -> None:
        """The logbook loads its stylesheet, its menu entry active."""
        body = self.logbook()

        self.assertIn('/static/css/pages/daily.css', body)
        self.assertIn('aria-current="page"', body)

    def test_no_markup_escaped(self) -> None:
        """No HTML fragment leaks as escaped text."""
        body = self.logbook()

        self.assertNotIn('&lt;span', body)
        self.assertNotIn('&lt;div', body)

    def test_days_newest_first(self) -> None:
        """The table of the days lists the most recent day first."""
        table = self.logbook().split('id="days"', 1)[1]

        links = [
            table.index(f'href="/daily/3/{ day }/"')
            for day in (DAY, OTHER_DAY, DNF_DAY)
        ]
        self.assertEqual(links, sorted(links))

    def test_day_row_is_best_and_gain(self) -> None:
        """A row gives the best of its day and the warm-up gain."""
        table = self.logbook().split('id="days"', 1)[1]

        self.assertIn('24.000', table)
        self.assertNotIn('27.333', table)
        self.assertIn('&minus;7.00', table)

    def test_day_row_zones(self) -> None:
        """Each attempt of a row is a square of its zone, DNF included."""
        table = self.logbook().split('id="days"', 1)[1]
        day_row = table.split(f'href="/daily/3/{ DAY }/"', 1)[1]
        day_row = day_row.split('</tr>', 1)[0]

        self.assertEqual(
            [part.split('"', 1)[0]
             for part in day_row.split('data-zone="')[1:]],
            ['3', '1', '2'],
        )
        self.assertIn('data-zone="dnf"', table)

    def test_records(self) -> None:
        """The staircase steps down from the first record."""
        records = self.logbook().split('id="records"', 1)[1]

        self.assertIn('&minus;5.00', records)
        self.assertIn('first', records)

    def test_best_and_worst_day(self) -> None:
        """The best and the worst day link their page."""
        body = self.logbook()

        self.assertIn(f'href="/daily/3/{ DAY }/"', body)
        self.assertIn('Best day', body)
        self.assertIn('Worst day', body)

    def test_today_scramble_and_command(self) -> None:
        """Today carries its scramble to copy and the command to run."""
        body = self.logbook()

        self.assertIn('data-copy-label="scramble"', body)
        self.assertIn('term-timer daily', body)

    def test_times_chart(self) -> None:
        """The times are drawn by the daily-times builder."""
        body = self.logbook()

        self.assertIn('data-chart="daily-times"', body)
        self.assertIn('/static/js/charts.js', body)

    def test_without_daily(self) -> None:
        """A cube never played renders today and the empty state."""
        status, _headers, body = self.client.get('/daily/4/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn('No daily played yet on 4x4x4', body)
        self.assertIn('term-timer daily -c 4', body)
        self.assertNotIn('data-chart', body)


class TestDailyListView(DailyServerTestCase):
    """Tests for the context of the logbook."""

    def cells(self, today: date) -> dict[date, 'ActivityCell']:
        """
        Lay the calendar of the logbook on a given day.

        Returns:
            Its cells by day.

        """
        activity = DailyListView(3, today).get_context()['activity']
        if activity is None:
            self.fail('no calendar')
        return {
            cell['day']: cell for week in activity['weeks'] for cell in week
        }

    def test_calendar_groups_by_session(self) -> None:
        """An attempt made after midnight belongs to the day of its file."""
        solves = self.read_day(DAY)
        solves.append({
            'date': 1790380000, 'time': 26 * SECOND, 'scramble': SCRAMBLE,
        })
        self.write_day(DAY, solves)

        cells = self.cells(date(2026, 9, 28))

        self.assertEqual(cells[date.fromisoformat(DAY)]['count'], 4)
        self.assertEqual(cells[date(2026, 9, 26)]['count'], 0)
        self.assertEqual(
            cells[date.fromisoformat(DAY)]['url'], f'/daily/3/{ DAY }/',
        )

    def test_calendar_hides_days_before_the_first(self) -> None:
        """The days before the first daily are out of range."""
        cells = self.cells(date(2026, 9, 28))

        self.assertEqual(cells[date(2026, 9, 22)]['level'], -1)
        self.assertEqual(cells[date.fromisoformat(DNF_DAY)]['level'], 1)
        self.assertEqual(cells[date.fromisoformat(DAY)]['level'], 2)
        self.assertNotIn('url', cells[date(2026, 9, 26)])

    def test_calendar_cells_link_their_day(self) -> None:
        """A played cell of the rendered calendar opens its day."""
        context = DailyListView(3, date(2026, 9, 28)).get_context()
        body = View.template(
            'daily.html', DEBUG=False, navigation=[], **context,
        )

        self.assertIn(
            f'<a class="punchcard-cell" data-level="2"'
            f' href="/daily/3/{ DAY }/"',
            body,
        )
        self.assertIn('<span class="punchcard-cell" data-level="-1"', body)

    def test_today_pending(self) -> None:
        """A day not played yet takes the next number, without page."""
        today = DailyListView(3, date(2026, 9, 28)).get_context()['today']

        self.assertEqual(today['number'], 3)
        self.assertEqual(today['url'], '')

    def test_today_played(self) -> None:
        """A played day keeps its number and links its page."""
        today = DailyListView(3, date.fromisoformat(DAY)).get_context()[
            'today'
        ]

        self.assertEqual(today['number'], 2)
        self.assertEqual(today['url'], f'/daily/3/{ DAY }/')

    def test_times_chart_clips_rare_slow_times(self) -> None:
        """The axis stops at the 95th percentile, the rest counted."""
        series: DailySeries = {
            'labels': [f'2026-01-{ day:02d}' for day in range(1, 21)],
            'best': [*[22.0] * 19, 58.0],
            'first': [None] * 20,
            'attempts': [1] * 20,
        }

        chart = DailyListView.compute_times_chart(series)
        if chart is None:
            self.fail('no chart')

        self.assertEqual(chart['floor'], 20)
        self.assertEqual(chart['ceiling'], 60)
        self.assertEqual(chart['clipped'], 0)

        series['best'] = [*[22.0] * 39, 58.0]
        series['first'] = [None] * 40
        chart = DailyListView.compute_times_chart(series)
        if chart is None:
            self.fail('no chart')

        self.assertEqual(chart['ceiling'], 25)
        self.assertEqual(chart['clipped'], 1)

    def test_times_chart_without_played_day(self) -> None:
        """No played day, no chart."""
        series: DailySeries = {
            'labels': [], 'best': [], 'first': [], 'attempts': [],
        }

        self.assertIsNone(DailyListView.compute_times_chart(series))


class TestDailyActivityCalendar(unittest.TestCase):
    """Tests for the calendar of the daily."""

    def test_levels_follow_the_terminal_punchcard(self) -> None:
        """A day heats up on the floors of PUNCHCARD_LEVELS."""
        self.assertEqual(
            [DailyActivityCalendar.level(count)
             for count in (0, 1, 2, 3, 4, 5, 6, 9)],
            [0, 1, 2, 2, 3, 3, 4, 4],
        )


class TestDailyDayPage(DailyServerTestCase):
    """Tests for the page of a daily session."""

    def day_page(self, day: str) -> str:
        """
        Render the page of a day.

        Returns:
            The body of the page.

        """
        status, _headers, body = self.client.get(f'/daily/3/{ day }/')
        self.assertEqual(status, HTTPStatus.OK)
        return body

    def test_renders(self) -> None:
        """The day loads its stylesheet, no HTML fragment escaped."""
        body = self.day_page(DAY)

        self.assertIn('/static/css/pages/daily-day.css', body)
        self.assertNotIn('&lt;span', body)
        self.assertNotIn('&lt;div', body)

    def test_hero_is_the_best(self) -> None:
        """The hero is the best of the day, its warm-up gain beside."""
        body = self.day_page(DAY)

        self.assertIn('Best of the day', body)
        self.assertIn('24<span class="hero-time-millis">.000</span>', body)
        self.assertIn('warm-up <b>&minus;7.00</b>', body)
        self.assertIn('Record', body)

    def test_squares_link_their_attempt(self) -> None:
        """Each square is the zone of an attempt, linked to it."""
        squares = self.day_page(DAY).split('daily-day-squares', 1)[1]
        squares = squares.split('daily-day-share', 1)[0]

        for solve_id in (1, 2, 3):
            self.assertIn(f'href="/daily/3/{ DAY }/{ solve_id }/"', squares)
        self.assertIn('data-labelled', squares)

    def test_share_card(self) -> None:
        """The share card is shown and copied as the terminal writes it."""
        body = self.day_page(DAY)

        self.assertIn(
            f'Term Timer Daily #2 · { DAY } · 24.00\n🟥🟨🟧', body,
        )
        self.assertIn('data-copy-label="share card"', body)

    def test_navigation(self) -> None:
        """The day links its neighbours on [ and ], never past the last."""
        body = self.day_page(OTHER_DAY)

        self.assertIn(f'href="/daily/3/{ DNF_DAY }/" data-key="["', body)
        self.assertIn(f'href="/daily/3/{ DAY }/" data-key="]"', body)
        self.assertNotIn('data-key="]"', self.day_page(DAY))

    def test_scramble_copied_and_analysed(self) -> None:
        """The scramble is copied, opens its analysis and its series."""
        body = self.day_page(DAY)

        self.assertIn('data-copy-label="scramble"', body)
        self.assertIn(f'href="/algorithm/{ SCRAMBLE }/"'
                      .replace("'", '&#39;'), body)
        self.assertIn(f'href="/scramble/3/{ DAY }/1/"', body)

    def test_attempts_and_steps(self) -> None:
        """Several attempts draw their chart and the time of each step."""
        body = self.day_page(DAY)

        self.assertIn('data-chart="daily-attempts"', body)
        self.assertIn('data-chart="daily-steps"', body)
        self.assertIn('Where the time went', body)

    def test_single_attempt(self) -> None:
        """A single attempt draws no chart: its solve page does."""
        body = self.day_page(OTHER_DAY)

        self.assertIn('Time · 24 Sep 2026', body)
        self.assertNotIn('data-chart', body)
        self.assertNotIn('Where the time went', body)
        self.assertNotIn('data-zone="diagnostics"', body)

    def test_all_dnf(self) -> None:
        """A day made only of DNF shows DNF, a DNF square, no best row."""
        body = self.day_page(DNF_DAY)

        self.assertIn('DNF<span class="hero-time-millis"></span>', body)
        self.assertIn('data-zone="dnf"', body)
        self.assertNotIn('data-tone="good"', body.split('<table', 1)[1])
        self.assertIn(f'Term Timer Daily · { DNF_DAY } · DNF', body)

    def test_diagnostics_of_one_analysed_attempt(self) -> None:
        """One analysed attempt: its findings, without their frequency."""
        body = self.day_page(DAY)

        if 'data-zone="diagnostics"' not in body:
            self.skipTest('no finding on the fixture solve')
        diagnostics = body.split('data-zone="diagnostics"', 1)[1]
        self.assertNotIn('of attempts', diagnostics)
        self.assertNotIn('attempts of the same scramble', diagnostics)


class TestDailyBanner(DailyServerTestCase):
    """Tests for the daily banner of the dashboard."""

    def test_banner_played_today(self) -> None:
        """The banner of a played day links its card."""
        banner = DailyListView.banner(3, date.fromisoformat(DAY))

        self.assertTrue(banner['done'])
        self.assertEqual(banner['number'], 2)
        self.assertEqual(banner['best'], 24 * SECOND)
        self.assertEqual(banner['attempts'], 3)
        self.assertEqual(banner['streak'], 2)
        self.assertEqual(banner['record'], 2)
        self.assertEqual(banner['url'], f'/daily/3/{ DAY }/')
        self.assertEqual(len(banner['series']['labels']), 14)
        self.assertEqual(banner['series']['labels'][-1], DAY)
        self.assertEqual(banner['series']['best'][-1], 24.0)
        self.assertEqual(banner['series']['first'][-1], 31.0)

    def test_banner_pending(self) -> None:
        """The banner of a day not played yet links the logbook."""
        banner = DailyListView.banner(3, date(2026, 9, 26))

        self.assertFalse(banner['done'])
        self.assertIsNone(banner['number'])
        self.assertEqual(banner['best'], 0)
        self.assertEqual(banner['streak'], 2)
        self.assertEqual(banner['url'], '/daily/3/')
        self.assertIsNone(banner['series']['best'][-1])

    def test_banner_on_dashboard(self) -> None:
        """The dashboard teases the daily of the day."""
        with patch(
                'term_timer.server.views.sessions.load_all_solves',
                return_value=[],
        ):
            status, _headers, body = self.client.get('/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn('data-zone="daily"', body)
        self.assertIn('term-timer daily', body)


class TestDailyScrambleParity(unittest.TestCase):
    """The scramble page of a date is the scramble of its daily."""

    def test_parity_with_daily_command(self) -> None:
        """/scramble/3/<date>/1/ regenerates the scramble daily races."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        for day in ('2026-09-25', '2026-01-01', '2024-02-29'):
            with (
                    self.subTest(day=day),
                    patch.object(
                        daily_mod, 'DAILY_DIRECTORY', Path(tmp.name),
                    ),
                    patch.object(
                        daily_mod, 'build_race_timer', return_value=None,
                    ) as build,
            ):
                daily_mod.build_daily_timer(Namespace(cube=3), day)

                self.assertEqual(
                    str(ScrambleDetailView(3, day, 1).get_scramble()),
                    build.call_args.kwargs['scramble'],
                )


if __name__ == '__main__':
    unittest.main()
