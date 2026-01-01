"""Tests for solve with OLL skip."""
import unittest
from typing import cast

from term_timer.methods.base import Analyser
from term_timer.solve import Solve


def get_method_applied(solve: Solve) -> Analyser:
    """
    Get method_applied, asserting it's not None in tests.

    Returns:
        The method_applied Analyser instance.

    """
    return cast('Analyser', solve.method_applied)


class TestSolveOLLSkip(unittest.TestCase):
    """Test Solve with OLL skip for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1729886473
        self.time = 25926000000
        self.scramble = """
        F' R F B U' R2 L' U' F R D' L2 B2 U F2 D F2 B2 U B2 D2
        """
        self.solution = """
        R@0 F'@314 L'@2415 D@2995 D@3292 B@3718 B@4043 D'@4415 F@4738 F@4988
        U@5475 D@7625 L'@8020 D'@8144 L@8239 D@8661 B'@9528 D@9650 B@9803
        F@10659 D@10762 F'@10842 D'@10963 D@12747 D@13026 B@13326 D@13467
        B'@13561 F@16188 D@16376 F'@16473 D@16817 L@17196 D'@17516 L'@17729
        D'@18563 D@18978 D@19256 F@20041 D@20127 F'@20226 D'@20320 F@20491
        D@20573 F'@20666 D'@20762 F@20941 D@21029 F'@21106 D@22050 F'@22971
        D'@23099 R'@23434 F@23796 D@23869 F'@23957 D'@24066 F'@24260 R@24357
        F@24517 F@24588 D'@24674 F'@24835 D'@24997 F@25240 D@25356 F'@25407
        D@25789 F@25926
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'auto'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('Cross', 'step'),
            ('F2L', 'virtual'),
            ('F2L 1', 'substep'),
            ('F2L 2', 'substep'),
            ('F2L 3', 'substep'),
            ('F2L 4', 'substep'),
            ('OLL', 'skipped'),
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

    def test_reconstruction_step_text(self) -> None:
        """Test reconstruction step text."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "L F' . R' . U2 B2 U' F2 D .",
            "U R' U' R U . B' U B .",
            "F U F' U' . U2 B U B' .",
            "F U F' U R U' R' .",
            "U' U2 . F U F' U' F U F' U' F U F' .",
            '',
            "U . F' U' L' F U F' U' F' L F2 U' F' U' F U F' U F",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )
