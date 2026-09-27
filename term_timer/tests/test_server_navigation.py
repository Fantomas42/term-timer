"""Tests for the V2 navigation and its first page, the design styleguide."""
import unittest
from datetime import UTC
from datetime import datetime

from bottle import TEMPLATE_PATH
from bottle import jinja2_template

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.server.app import Server
from term_timer.server.views.navigation import Navigation
from term_timer.tests.test_server_daily import WSGIClient


class NavigationTestCase(unittest.TestCase):
    """Visible entries and the active one, per request path."""

    @staticmethod
    def active(path: str, *, debug: bool = False) -> list[str]:
        """
        Labels of the active entries for a path.

        Returns:
            The active labels, at most one.

        """
        return [
            item['label']
            for item in Navigation.items(path, debug=debug)
            if item['active']
        ]

    def test_sessions_own_the_home_and_the_cube_paths(self) -> None:
        """Home, sessions and solves all belong to Sessions."""
        for path in ('/', '/3/', '/3/all/', '/3/all/1181/'):
            with self.subTest(path=path):
                self.assertEqual(self.active(path), ['Sessions'])

    def test_sections_own_their_prefix(self) -> None:
        """Each section is active on its whole subtree."""
        cases = {
            '/daily/3/2026-09-25/2/': 'Daily',
            '/training/cfop/oll/review/': 'Training',
            '/academy/cfop/pll/Ua/': 'Academy',
            '/scramble/3/abc/1/': 'Scramble',
        }
        for path, label in cases.items():
            with self.subTest(path=path):
                self.assertEqual(self.active(path), [label])

    def test_unlisted_pages_have_no_active_entry(self) -> None:
        """A page outside the menu leaves every entry inactive."""
        self.assertEqual(self.active('/algorithm/R U/'), [])
        self.assertEqual(self.active('/cube/render/'), [])

    def test_styleguide_only_in_debug(self) -> None:
        """The styleguide entry is hidden unless debugging."""
        labels = [
            item['label'] for item in Navigation.items('/', debug=False)
        ]
        self.assertNotIn('Design', labels)
        self.assertEqual(
            self.active('/styleguide/v2/', debug=True), ['Design'],
        )
        self.assertEqual(self.active('/styleguide/v2/'), [])


class DesignStyleguideServerTestCase(unittest.TestCase):
    """The V2 styleguide page rendered through the application."""

    client: WSGIClient
    debug_client: WSGIClient

    @classmethod
    def setUpClass(cls) -> None:
        """Register the templates and build both applications once."""
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)
        cls.client = WSGIClient(Server.create_app(debug=False))
        cls.debug_client = WSGIClient(Server.create_app(debug=True))

    def test_page_renders_the_theme(self) -> None:
        """Every theme family and the contrast pairs are listed."""
        status, _headers, body = self.client.get('/styleguide/v2/')

        self.assertEqual(status, 200)
        self.assertIn('/static/v2/css/theme.css', body)
        self.assertIn('style="--swatch: var(--acid)"', body)
        self.assertIn('--pair-text: var(--text-faint)', body)
        for section in ('palette', 'roles', 'type', 'space', 'contrast'):
            self.assertIn(f'id="{ section }"', body)

    def test_page_renders_the_navigation(self) -> None:
        """The rail lists the sections; debug adds the active styleguide."""
        _status, _headers, body = self.client.get('/styleguide/v2/')
        self.assertIn('<nav class="nav"', body)
        self.assertIn('href="/daily/3/"', body)
        self.assertNotRegex(body, r'class="nav-item"[^>]*aria-current')

        _status, _headers, body = self.debug_client.get('/styleguide/v2/')
        self.assertIn(
            '<a class="nav-item" href="/styleguide/v2/" aria-current="page">',
            body,
        )

    def test_v1_pages_ignore_the_navigation(self) -> None:
        """The injected navigation leaves the V1 styleguide working."""
        status, _headers, body = self.client.get('/styleguide/')
        self.assertEqual(status, 200)
        self.assertNotIn('<nav class="nav"', body)

    def test_template_outside_a_request_defaults_to_home(self) -> None:
        """Rendered outside a request, the path is the home page."""
        body = jinja2_template(
            'v2/skeleton.html',
            navigation=Navigation.items('/', debug=False),
            now=datetime(2026, 9, 27, tzinfo=UTC),
        )
        self.assertIn(
            '<a class="nav-item" href="/" aria-current="page">', body,
        )
