"""Tests for the seeded scramble series views."""
import unittest
from http import HTTPStatus
from io import BytesIO
from random import Random
from typing import Any
from urllib.parse import unquote
from wsgiref.util import setup_testing_defaults

from bottle import TEMPLATE_PATH
from bottle import Bottle
from bottle import HTTPError

from term_timer.constants import MAX_SCRAMBLE_INDEX
from term_timer.constants import SCRAMBLE_SEED_ALPHABET
from term_timer.constants import SCRAMBLE_SEED_LENGTH
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.scrambler import scrambler
from term_timer.server.app import Server
from term_timer.server.views import ScrambleDetailView
from term_timer.server.views import ScrambleHomeView


def cli_scrambles(cube_size: int, seed: str, count: int) -> list[str]:
    """
    Generate a series the way `term-timer scramble -r SEED` does.

    Returns:
        The scrambles of the series, as strings.

    """
    rng = Random(seed)  # noqa: S311

    return [
        str(scrambler(cube_size=cube_size, iterations=0, rng=rng)[0])
        for _ in range(count)
    ]


class WSGIClient:
    """Minimal WSGI client calling a Bottle application in process."""

    def __init__(self, app: Bottle) -> None:
        """Keep the application to call."""
        self.app = app

    def get(
            self, path: str, query: str = '',
    ) -> tuple[int, dict[str, str], str]:
        """
        Issue a GET request.

        Returns:
            Status code, headers and decoded body.

        """
        environ: dict[str, Any] = {
            'PATH_INFO': path,
            'QUERY_STRING': query,
            'REQUEST_METHOD': 'GET',
            'wsgi.input': BytesIO(),
        }
        setup_testing_defaults(environ)

        result: dict[str, Any] = {}

        def start_response(
                status: str, headers: list[tuple[str, str]],
                _exc_info: object = None,
        ) -> None:
            result['status'] = int(status.split(maxsplit=1)[0])
            result['headers'] = dict(headers)

        body = b''.join(self.app(environ, start_response))

        return result['status'], result['headers'], body.decode('utf-8')


class TestScrambleServer(unittest.TestCase):
    """Tests for the scramble routes through the whole application."""

    client: WSGIClient

    @classmethod
    def setUpClass(cls) -> None:
        """Register the templates and build the application once."""
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)
        cls.client = WSGIClient(Server.create_app(debug=False))

    def test_detail_parity_with_cli(self) -> None:
        """The n-th page shows the n-th scramble of the CLI series."""
        for cube_size in (2, 3, 4):
            expected = cli_scrambles(cube_size, 'SALON', 3)
            for index, scramble in enumerate(expected, start=1):
                with self.subTest(cube_size=cube_size, index=index):
                    status, _headers, body = self.client.get(
                        f'/scramble/{ cube_size }/SALON/{ index }/',
                    )
                    self.assertEqual(status, HTTPStatus.OK)
                    self.assertIn(scramble, body)

    def test_detail_image_carries_scramble(self) -> None:
        """The cube image is rendered from the same scramble."""
        scramble = cli_scrambles(3, 'SALON', 1)[0]
        _status, _headers, body = self.client.get('/scramble/3/SALON/1/')

        self.assertIn(
            f'algo={ scramble }&o=UF',
            unquote(body),
        )

    def test_detail_is_deterministic(self) -> None:
        """Two renders of the same URL are identical."""
        first = self.client.get('/scramble/3/SALON/5/')[2]
        second = self.client.get('/scramble/3/SALON/5/')[2]

        self.assertEqual(first, second)

    def test_detail_navigation_links(self) -> None:
        """First page links only forward, last page only backward."""
        body = self.client.get('/scramble/2/SALON/1/')[2]
        self.assertIn('href="/scramble/2/SALON/2/"', body)
        self.assertNotIn('href="/scramble/2/SALON/0/"', body)

        last = MAX_SCRAMBLE_INDEX
        body = self.client.get(f'/scramble/2/SALON/{ last }/')[2]
        self.assertIn(f'href="/scramble/2/SALON/{ last - 1 }/"', body)
        self.assertNotIn(f'href="/scramble/2/SALON/{ last + 1 }/"', body)

    def test_detail_out_of_bounds(self) -> None:
        """Out of range size, index or seed answer 404."""
        paths = [
            '/scramble/1/SALON/1/',
            '/scramble/8/SALON/1/',
            '/scramble/3/SALON/0/',
            f'/scramble/3/SALON/{ MAX_SCRAMBLE_INDEX + 1 }/',
            '/scramble/3/SA.LON/1/',
            '/scramble/3/SA/LON/1/',
            f'/scramble/3/{ "A" * 33 }/1/',
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(
                    self.client.get(path)[0], HTTPStatus.NOT_FOUND,
                )

    def test_home_redirects_to_first_scramble(self) -> None:
        """A submitted size and seed redirect to the first scramble."""
        status, headers, _body = self.client.get(
            '/scramble/', 'c=4&seed=Salon-2',
        )

        self.assertEqual(status, HTTPStatus.FOUND)
        self.assertTrue(
            headers['Location'].endswith('/scramble/4/Salon-2/1/'),
        )

    def test_home_proposes_a_seed(self) -> None:
        """Without a form, the page proposes a short seed code."""
        status, _headers, body = self.client.get('/scramble/')

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn('name="seed"', body)
        self.assertRegex(body, r'value="3"\s+checked')

    def test_home_invalid_seed_shows_error(self) -> None:
        """An invalid seed stays on the form with an error."""
        status, _headers, body = self.client.get(
            '/scramble/', 'c=3&seed=a.b',
        )

        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn('scramble-error', body)


class TestScrambleHomeView(unittest.TestCase):
    """Tests for ScrambleHomeView context."""

    def test_generate_seed(self) -> None:
        """The proposed seed is a code of the unambiguous alphabet."""
        for _ in range(50):
            seed = ScrambleHomeView.generate_seed()
            self.assertEqual(len(seed), SCRAMBLE_SEED_LENGTH)
            self.assertTrue(set(seed) <= set(SCRAMBLE_SEED_ALPHABET))

    def test_context_without_form(self) -> None:
        """The empty form defaults to 3x3 and a generated seed."""
        context = ScrambleHomeView('', '').get_context()

        self.assertEqual(context['cube_size'], 3)
        self.assertEqual(len(context['seed']), SCRAMBLE_SEED_LENGTH)
        self.assertEqual(context['error'], '')

    def test_context_invalid_size(self) -> None:
        """An unknown size keeps the form with an error."""
        context = ScrambleHomeView('9', 'SALON').get_context()

        self.assertEqual(context['cube_size'], 3)
        self.assertEqual(context['seed'], 'SALON')
        self.assertNotEqual(context['error'], '')


class TestScrambleDetailView(unittest.TestCase):
    """Tests for ScrambleDetailView generation."""

    def test_different_seeds_differ(self) -> None:
        """Two seeds give two different scrambles."""
        first = ScrambleDetailView(3, 'SALON', 1).get_scramble()
        second = ScrambleDetailView(3, 'DUEL', 1).get_scramble()

        self.assertNotEqual(str(first), str(second))

    def test_seed_is_case_sensitive(self) -> None:
        """The seed keeps its case, as the CLI does."""
        upper = ScrambleDetailView(3, 'SALON', 1).get_scramble()
        lower = ScrambleDetailView(3, 'salon', 1).get_scramble()

        self.assertNotEqual(str(upper), str(lower))

    def test_context(self) -> None:
        """The context carries the scramble and its HTM count."""
        context = ScrambleDetailView(2, 'SALON', 2).get_context()

        self.assertEqual(context['index'], 2)
        self.assertEqual(context['max_index'], MAX_SCRAMBLE_INDEX)
        self.assertEqual(
            str(context['scramble']), cli_scrambles(2, 'SALON', 2)[1],
        )
        self.assertEqual(context['htm'], context['scramble'].metrics.htm)

    def test_invalid_arguments_abort(self) -> None:
        """Invalid arguments abort with a 404 before any generation."""
        for args in ((1, 'SALON', 1), (3, 'SA.LON', 1), (3, 'SALON', 101)):
            with self.subTest(args=args), self.assertRaises(HTTPError) as ctx:
                ScrambleDetailView(*args)
            self.assertEqual(ctx.exception.status_code, HTTPStatus.NOT_FOUND)
