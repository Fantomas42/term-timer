"""Tests for the QR codes of the shared pages."""
import re
import unittest

import segno

from term_timer.server.share import QUIET_ZONE
from term_timer.server.share import ShareCode

# A run of dark modules: its start, its length, closed back to its start.
RUN_RE = re.compile(r'M(\d+) (\d+)h(\d+)v1h-\3z')

URL = 'http://192.168.1.20:8333/scramble/3/SALON/7/'


def drawn_matrix(code: ShareCode) -> list[list[bool]]:
    """
    Rebuild the modules a path fills, run by run.

    Returns:
        The dark modules, row by row.

    """
    matrix = [[False] * code.size for _ in range(code.size)]
    for x, y, length in RUN_RE.findall(code.path):
        for column in range(int(x), int(x) + int(length)):
            matrix[int(y)][column] = True

    return matrix


class TestShareCode(unittest.TestCase):
    """Tests for ShareCode."""

    def test_path_draws_the_segno_matrix(self) -> None:
        """The path fills exactly the dark modules segno encodes."""
        for url in (URL, 'http://localhost/', 'http://x.local:1/' + 'a' * 80):
            with self.subTest(url=url):
                code = ShareCode.encode(url)
                expected = [
                    [bool(module) for module in row]
                    for row in segno.make(url, error='m', micro=False).matrix
                ]
                self.assertEqual(drawn_matrix(code), expected)

    def test_path_is_only_runs(self) -> None:
        """Nothing but runs in the path, nothing to escape."""
        code = ShareCode.encode(URL)
        self.assertEqual(RUN_RE.sub('', code.path), '')

    def test_view_box_keeps_the_quiet_zone(self) -> None:
        """The view box adds the quiet zone on every side."""
        code = ShareCode.encode(URL)
        side = code.size + 2 * QUIET_ZONE
        self.assertEqual(
            code.view_box,
            f'-{ QUIET_ZONE } -{ QUIET_ZONE } { side } { side }',
        )

    def test_local_addresses(self) -> None:
        """Loopback addresses are local, network ones are not."""
        cases = {
            'http://localhost:8333/': True,
            'http://127.0.0.1:8333/': True,
            'http://127.4.5.6/': True,
            'http://[::1]:8333/': True,
            'http://192.168.1.20:8333/': False,
            'http://cube.local/': False,
            'http://[fe80::1]/': False,
        }
        for url, local in cases.items():
            with self.subTest(url=url):
                self.assertEqual(ShareCode.encode(url).local, local)
