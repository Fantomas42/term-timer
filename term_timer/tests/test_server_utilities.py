"""Tests for the utility pages: errors and the cube renderer."""
import html
import unittest
from http import HTTPStatus
from traceback import FrameSummary
from unittest.mock import patch

from bottle import TEMPLATE_PATH
from bottle import Bottle
from bottle import HTTPError

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.server.app import Server
from term_timer.server.modes import get_mode_groups
from term_timer.server.views import Error404View
from term_timer.server.views import Error500View
from term_timer.tests.test_server_scramble import WSGIClient


def failing_app(*, debug: bool) -> Bottle:
    """
    Build the application with a route that always fails.

    Returns:
        The application, /boom/ raising a ZeroDivisionError.

    """
    app = Server.create_app(debug=debug)

    @app.route('/boom/')  # type: ignore[untyped-decorator]
    def boom() -> str:
        return str(1 // 0)

    return app


class UtilitiesTestCase(unittest.TestCase):
    """Register the templates once."""

    @classmethod
    def setUpClass(cls) -> None:
        """Register the templates."""
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)


class TestError404(UtilitiesTestCase):
    """Tests for the 404 page."""

    def test_page(self) -> None:
        """The page scrambles a cube with the lost path."""
        client = WSGIClient(Server.create_app(debug=False))
        status, _headers, body = client.get('/nowhere/')
        scramble = Error404View(HTTPError(404), '/nowhere/').get_scramble()

        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        self.assertIn('This page is scrambled', body)
        self.assertIn(f'href="/algorithm/{ scramble }/"', html.unescape(body))
        self.assertIn('class="error-way"', body)
        self.assertIn('data-lookup', body)

    def test_scramble_follows_the_path(self) -> None:
        """The same path gives the same cube, another path another."""
        first = Error404View(HTTPError(404), '/a/').get_scramble()
        again = Error404View(HTTPError(404), '/a/').get_scramble()
        other = Error404View(HTTPError(404), '/b/').get_scramble()

        self.assertEqual(first, again)
        self.assertNotEqual(first, other)

    def test_path_is_escaped(self) -> None:
        """A path carrying markup is shown as text."""
        client = WSGIClient(Server.create_app(debug=False))
        body = client.get('/<script>x</script>/')[2]

        self.assertNotIn('<script>x</script>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_v1(self) -> None:
        """?v1 renders the V1 page."""
        client = WSGIClient(Server.create_app(debug=False))
        status, _headers, body = client.get('/nowhere/', 'v1')

        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        self.assertIn('Error 404', body)

    def test_fallback_when_the_page_fails(self) -> None:
        """A broken skeleton still answers a bare page with the status."""
        client = WSGIClient(Server.create_app(debug=False))
        with (
            patch(
                'term_timer.server.views.base.Navigation.items',
                side_effect=RuntimeError('broken'),
            ),
            self.assertLogs('term_timer.server.views.errors', 'ERROR'),
        ):
            status, _headers, body = client.get('/nowhere/')

        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        self.assertIn('<h1>404 Not Found</h1>', body)
        self.assertIn('href="/"', body)


class TestError500(UtilitiesTestCase):
    """Tests for the 500 page."""

    def test_traceback_hidden_without_debug(self) -> None:
        """Without debug mode, the page tells where the error went."""
        client = WSGIClient(failing_app(debug=False))
        with self.assertLogs('term_timer.server.views.errors', 'ERROR') as logs:
            status, _headers, body = client.get('/boom/')

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIn('Something broke', body)
        self.assertIn('TERM_TIMER_DEBUG=1', body)
        self.assertNotIn('ZeroDivisionError', body)
        self.assertNotIn('error-frame', body)
        self.assertIn('ZeroDivisionError', logs.output[0])

    def test_traceback_shown_in_debug(self) -> None:
        """In debug mode, the frames are listed, ours put forward."""
        client = WSGIClient(failing_app(debug=True))
        with self.assertLogs('term_timer.server.views.errors', 'ERROR'):
            status, _headers, body = client.get('/boom/')

        self.assertEqual(status, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertIn('ZeroDivisionError', body)
        self.assertIn('data-own', body)
        self.assertIn('term_timer/tests/test_server_utilities.py', body)
        self.assertIn('data-copy-label="traceback"', body)
        self.assertNotIn('TERM_TIMER_DEBUG=1', body)

    def test_frame_of_own_file(self) -> None:
        """A frame of term-timer is named from its package."""
        frame = Error500View.frame_of(FrameSummary(
            '/home/u/term_timer/term_timer/server/app.py', 12, 'route',
            line='return view()',
        ))

        self.assertEqual(frame, {
            'file': 'term_timer/server/app.py',
            'line': 12,
            'function': 'route',
            'code': 'return view()',
            'own': True,
        })

    def test_frame_of_library_file(self) -> None:
        """A library frame is named from site-packages, never own."""
        frame = Error500View.frame_of(FrameSummary(
            '/v/lib/python3.12/site-packages/term_timer/x.py', 3, 'f',
            line='',
        ))

        self.assertEqual(frame['file'], 'term_timer/x.py')
        self.assertFalse(frame['own'])

        stdlib = Error500View.frame_of(FrameSummary(
            '/usr/lib/python3.12/json/decoder.py', 3, 'decode', line='',
        ))
        self.assertEqual(stdlib['file'], 'decoder.py')
        self.assertFalse(stdlib['own'])


class TestCubeRender(UtilitiesTestCase):
    """Tests for the cube renderer page."""

    def test_page_sheet_holds_every_mode(self) -> None:
        """The contact sheet shows the algorithm in every mode."""
        client = WSGIClient(Server.create_app(debug=False))
        status, _headers, body = client.get(
            '/cube/render/', "algorithm=R+U+R'+U'&m=oll",
        )
        modes = [mode for _group, keys in get_mode_groups() for mode in keys]

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(body.count('class="cube-render-mode"'), len(modes))
        self.assertEqual(body.count('aria-current="true"'), 1)
        self.assertIn('data-cube-render', body)
        self.assertIn('value="R U R&#39; U&#39;"', body)

    def test_v1(self) -> None:
        """?v1 renders the V1 page."""
        client = WSGIClient(Server.create_app(debug=False))
        body = client.get('/cube/render/', 'v1')[2]

        self.assertIn('cube-debug', body)
