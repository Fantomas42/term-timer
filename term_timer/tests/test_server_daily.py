"""Tests for the daily sessions routes of the web server."""
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from bottle import TEMPLATE_PATH
from bottle import Bottle

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.scripts.commands import daily as daily_mod
from term_timer.server.app import Server
from term_timer.server.views import ScrambleDetailView
from term_timer.server.views.daily import DailyListView
from term_timer.server.views.daily import DailyLocation
from term_timer.server.views.solves import SolveLocation

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

    def test_hub_lists_days_newest_first(self) -> None:
        """Every daily session is linked, the most recent day first."""
        status, _headers, body = self.client.get('/daily/3/')

        self.assertEqual(status, HTTPStatus.OK)
        links = [
            body.index(f'href="/daily/3/{ day }/"')
            for day in (DAY, OTHER_DAY, DNF_DAY)
        ]
        self.assertEqual(links, sorted(links))

    def test_hub_day_is_its_best(self) -> None:
        """A day is represented by its best attempt, never its mean."""
        body = self.client.get('/daily/3/')[2]

        self.assertIn('00:24.000', body)
        self.assertNotIn('00:27.333', body)

    def test_hub_warmup_gain(self) -> None:
        """A row carries the gain of the retries over the first attempt."""
        body = self.client.get('/daily/3/')[2]

        self.assertIn('7.00s', body)

    def test_hub_records(self) -> None:
        """The records wall steps down from the first record."""
        body = self.client.get('/daily/3/')[2]

        self.assertIn('-5.00s', body)
        self.assertIn('First record', body)

    def test_hub_calendar_groups_by_session(self) -> None:
        """An attempt made after midnight belongs to the day of its file."""
        solves = self.read_day(DAY)
        solves.append({
            'date': 1790380000, 'time': 26 * SECOND, 'scramble': SCRAMBLE,
        })
        self.write_day(DAY, solves)

        body = self.client.get('/daily/3/')[2]

        self.assertIn(f'title="{ DAY } · 4 attempts"', body)
        self.assertIn(f'title="{ DNF_DAY } · 1 attempt"', body)

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

    def test_header_links_daily(self) -> None:
        """The header navigation carries the daily hub."""
        body = self.client.get('/daily/3/')[2]

        self.assertIn('href="/daily/3/" class="btn"', body)


class TestDailyDay(DailyServerTestCase):
    """Tests for the card of a single daily session."""

    def test_day_links_each_attempt(self) -> None:
        """The day lists its attempts, each linked to its detail."""
        status, _headers, body = self.client.get(f'/daily/3/{ DAY }/')

        self.assertEqual(status, HTTPStatus.OK)
        for solve_id in (1, 2, 3):
            self.assertIn(f'href="/daily/3/{ DAY }/{ solve_id }/"', body)

    def test_day_all_dnf_has_no_best(self) -> None:
        """A day made only of DNF highlights no attempt as the best."""
        status, _headers, body = self.client.get(f'/daily/3/{ DNF_DAY }/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertNotIn('time-best', body)
        self.assertIn(f'Term Timer Daily · { DNF_DAY } · DNF', body)

    def test_day_share_card(self) -> None:
        """The share card numbers the day among the played ones."""
        body = self.client.get(f'/daily/3/{ DAY }/')[2]

        self.assertIn(
            f'Term Timer Daily #2 · { DAY } · 24.00\n🟥🟨🟧', body,
        )

    def test_day_navigation(self) -> None:
        """A day links to its neighbours, never past the last one."""
        body = self.client.get(f'/daily/3/{ DAY }/')[2]

        self.assertIn(f'href="/daily/3/{ OTHER_DAY }/"', body)
        self.assertNotIn('fa-chevron-right', body)

        body = self.client.get(f'/daily/3/{ OTHER_DAY }/')[2]
        self.assertIn(f'href="/daily/3/{ DNF_DAY }/"', body)
        self.assertIn(f'href="/daily/3/{ DAY }/"', body)

    def test_day_scramble_can_be_copied_and_analysed(self) -> None:
        """The scramble of the day is copied and opens its analysis."""
        body = self.client.get(f'/daily/3/{ DAY }/')[2]

        self.assertIn(f'data-algorithm="{ SCRAMBLE }"', body)
        self.assertIn(f'href="/algorithm/{ SCRAMBLE }/"', body)

    def test_day_scramble_links_its_series(self) -> None:
        """The scramble of the day opens the scramble page of the date."""
        body = self.client.get(f'/daily/3/{ DAY }/')[2]

        self.assertIn(f'href="/scramble/3/{ DAY }/1/"', body)

    def test_day_without_moves_degrades(self) -> None:
        """Without smart cube data there is no step split nor doctor."""
        status, _headers, body = self.client.get(f'/daily/3/{ OTHER_DAY }/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertNotIn('Where the time went', body)
        self.assertNotIn('Diagnostics on', body)
        self.assertIn('attemptsChart', body)

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
        self.assertIn('daily-banner', body)
        self.assertIn('dailySparkline', body)


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
