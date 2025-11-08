"""Tests for solve wr."""

import unittest
from typing import cast

from term_timer.methods.base import Analyser
from term_timer.solve import Solve


def get_method_applied(solve: Solve) -> Analyser:
    """Get method_applied, asserting it's not None in tests."""
    return cast('Analyser', solve.method_applied)


class TestSolveWR(unittest.TestCase):
    """
    Test Solve WR for color neutral analyse.

    http://cubesolv.es/solve/5757
    """

    maxDiff = None

    def setUp(self) -> None:
        self.date = 1751998918
        self.time = 2549969965
        self.scramble = "F U2 L2 B2 F' U L2 U R2 D2 L' B L2 B' R2 U2"
        self.solution = """
        L@10 B2@20 L'@30 U'@40 F@50 U'@60 L'@70 F'@80
        L'@90 B@100 L@110 B'@120
        B'@130 L@140 B@150 L'@160 L'@170 B'@180 L@190 B@200
        L@210 B'@220 L'@230 B@240 L'@250 B'@260 L2@270 B@280
        L@290
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'auto'

    def test_reconstruction(self) -> None:
        self.assertEqual(
            str(self.solve.reconstruction),
            "U R2 U' F' L F' U' L' U' R U R2 U R U2 R' U R "
            "U R' U' R U' R' U2 R U",
        )

    def test_score(self) -> None:
        self.assertEqual(
            self.solve.score,
            20,
        )

    def test_method_score(self) -> None:
        method_applied = get_method_applied(self.solve)
        self.assertEqual(
            method_applied.score,
            26.5,
        )

    def test_summary(self) -> None:
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('XXCross', 'step'),
            ('F2L', 'virtual'),
            ('F2L 3', 'substep'),
            ('F2L 4', 'substep'),
            ('OLL', 'step'),
            ('PLL', 'step'),
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                source['name'],
                expected[0],
            )
            self.assertEqual(
                source['type'],
                expected[1],
            )

    def test_reconstruction_step_line(self) -> None:
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "U R2 U' F' L F' U' L'",
            "U' [pair-ie]R U R'[/pair-ie]",
            "R' U [ne]R U2 R'[/ne] U R",
            "[pre-auf]U[/pre-auf] [su]R' U' R U'[/su] [ne]R' U2 R[/ne]",
            '[post-auf]U[/post-auf]',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_line(source, multiple=False),
                expected,
            )

    def test_reconstruction_step_text(self) -> None:
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "U R2 U' F' L F' U' L'",
            "U' R U R'",
            "R' U R U2 R' U R",
            "U R' U' R U' R' U2 R",
            'U',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )
