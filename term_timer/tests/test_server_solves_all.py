"""Tests for the writes made on a solve shown in « All sessions »."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bottle import HTTPError

from term_timer.server.views.solves import SolveDeleteView
from term_timer.server.views.solves import SolveLocation
from term_timer.server.views.solves import SolveUpdateCommentView
from term_timer.server.views.solves import SolveUpdateFlagView


class TestSolveWriteFromAllSessions(unittest.TestCase):
    """A write on the session 'all' lands in the session of the solve."""

    def setUp(self) -> None:
        """Write two sessions in a temporary folder."""
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.default = self.directory / '3x3x3.json'
        self.foo = self.directory / '3x3x3-foo.json'
        self.parasite = self.directory / '3x3x3-all.json'
        self.default.write_text(json.dumps([
            {'date': 1000, 'time': 10000000000, 'scramble': 'R U'},
        ]))
        self.foo.write_text(json.dumps([
            {'date': 2000, 'time': 20000000000, 'scramble': 'F D'},
            {'date': 3000, 'time': 30000000000, 'scramble': 'B L'},
        ]))
        directory = patch.object(SolveLocation, 'directory', self.directory)
        directory.start()
        self.addCleanup(directory.stop)
        redirect = patch('term_timer.server.views.solves.redirect')
        self.redirect = redirect.start()
        self.addCleanup(redirect.stop)

    def tearDown(self) -> None:
        """Remove the temporary folder."""
        self.temp.cleanup()

    @staticmethod
    def read(path: Path) -> list[dict[str, object]]:
        """
        Read a session file.

        Returns:
            The raw solves of the file.

        """
        data: list[dict[str, object]] = json.loads(
            path.read_text(encoding='utf-8'),
        )
        return data

    def test_comment(self) -> None:
        """The comment is saved in the file of the solve's session."""
        SolveUpdateCommentView(3, 'all', 1, ' hello ')

        self.assertFalse(self.parasite.exists())
        self.assertEqual(self.read(self.default)[0]['comment'], 'hello')
        self.assertNotIn('comment', self.read(self.foo)[0])
        self.redirect.assert_called_once_with('/3/all/1/')

    def test_flag(self) -> None:
        """The flag is saved in the file of the solve's session."""
        SolveUpdateFlagView(3, 'all', 3, 'DNF')

        self.assertFalse(self.parasite.exists())
        foo = self.read(self.foo)
        self.assertNotIn('flag', foo[0])
        self.assertEqual(foo[1]['flag'], 'DNF')
        self.assertNotIn('flag', self.read(self.default)[0])
        self.redirect.assert_called_once_with('/3/all/3/')

    def test_delete(self) -> None:
        """The solve is deleted from the file of its own session."""
        SolveDeleteView(3, 'all', 2)

        self.assertFalse(self.parasite.exists())
        self.assertEqual(
            [solve['date'] for solve in self.read(self.foo)], [3000],
        )
        self.assertEqual(len(self.read(self.default)), 1)
        self.redirect.assert_called_once_with('/3/all/')

    def test_invalid_id(self) -> None:
        """An unknown solve of 'all' is a 404 and writes nothing."""
        with self.assertRaises(HTTPError) as error:
            SolveDeleteView(3, 'all', 4)

        self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(self.parasite.exists())

    def test_session_unchanged(self) -> None:
        """A write on a named session still saves that session."""
        SolveUpdateCommentView(3, 'foo', 2, 'x')

        self.assertEqual(self.read(self.foo)[1]['comment'], 'x')
        self.assertFalse(self.parasite.exists())
        self.redirect.assert_called_once_with('/3/foo/2/')
