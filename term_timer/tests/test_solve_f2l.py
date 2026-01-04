"""Tests for solve with F2L special cases."""
import unittest

from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolveF2LDouble(unittest.TestCase):
    """Test Solve with F2L double for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1728144170
        self.time = 47158000000
        self.scramble = """
        L' B2 R' D2 L2 D2 U2 F2 R' B2 L D U' B' R F U2 B R U' F'
        """
        self.solution = """
        R'@0 D@255 L@691 L'@1243 U'@1690 L@1960 R@2673 R@2748 F@3175 F@3477
        D@5732 D@5986 D@7329 R'@7859 D'@8284 R@8633 D'@8740 D'@8972 R'@9060
        D@9616 D'@10037 D'@10279 F'@10670 D'@10853 F@11190 D@12405 D@13759
        B@14401 D'@14536 B'@15234 D@15439 B@15556 D'@16676 D'@17099 B@17367
        D'@17458 B'@17637 D'@17762 D@18796 D@19658 B@20007 B@20077 B@21044
        D'@21139 B'@21489 D@21655 B@21778 B'@22469 D'@23929 B'@24657 D@24846
        B@25241 D'@26359 D'@26567 F@26869 D'@26956 F'@27056 D'@27209 B@29579
        R'@29774 B'@29936 R'@31050 D@31285 R@31640 D'@31934 D'@32138 R'@32436
        D@32617 D@32875 R@33191 D'@33403 R'@33703 D@33850 R@34189 L'@37124
        D@37263 L@37372 D@37529 B@38033 D'@38152 B'@38303 D'@40143 D'@42083
        D'@42290 B'@43187 L@43380 B@43552 L'@43846 D'@44273 L'@44636 D@45200
        L@45589 D@46525 D'@46938 D'@47158
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
            ('F2L 1+2', 'substep'),
            ('F2L 3', 'substep'),
            ('F2L 4', 'substep'),
            ('OLL', 'step'),
            ('PLL', 'step'),
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
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
            "R' U L L' D' L R2 B2 .",
            (
                "U2 . U R' U' R U2 R' U U2 B' U' B . U . U F U' F' U F . "
                "U2 F U' F' U' . U . U F2 . F U' F' U F F' . U' F' U F . "
                "U2 B U' B' U' . F R' F' ."
            ),
            "R' U R U2 R' U2 R U' R' U R .",
            "L' U L U F U' F' .",
            "U' . U2 . F' L F L' U' L' U L .",
            'U U2',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_text(source, multiple=False),
                    expected,
                )
