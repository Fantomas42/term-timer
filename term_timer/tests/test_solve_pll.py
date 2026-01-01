"""Tests for solve with PLL skip."""
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


class TestSolvePLLSkipAUF(unittest.TestCase):
    """Test Solve with PLL skip with AUF for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1738409202
        self.time = 34962000000
        self.scramble = """
        D' L U R B' U R U' F B2 U L2 B2 U L2 U2 F2 L2 D' R2 L2 U2
        """
        self.solution = """
        D'@0 F@485 R@1035 U'@2052 L'@2448 D@7595 L'@7995 D'@8130 D@8388 D@8679
        L@8803 D@9450 B'@10114 D@10229 B@10397 D'@12090 F'@12460 D@12691
        F@12819 D'@13116 D'@13328 D'@13605 L'@13991 D@14310 L@14688 L@18093
        D@18157 L'@18240 D'@18354 D@23053 F'@23469 D'@23618 D'@23856 F@23903
        D'@24253 F@24704 D@24894 D@25177 F'@25255 D@25592 D@25832 F@25899
        D'@26019 F'@26160 D@28182 F'@28505 D@28737 F@29070 D'@29288 D'@29493
        F'@29979 D@30158 F@30484 F@31565 L@31763 D@31882 L'@31948 D'@32057
        F'@32401 B@32724 D@33046 R@33189 D'@33273 R'@33344 B'@33598 D@34325
        D'@34749 D'@34962
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

    def test_reconstruction_step_text(self) -> None:
        """Test reconstruction step text."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "U' F L . D' R' .",
            "U R' U' U2 R . U . B' U B .",
            "U' F' U F U2 U' R' U R .",
            "R U R' U' . U F' U2 F U' F U2 F' U2 F U' F' .",
            "U F' U F U2 F' U F .",
            "F R U R' U' F' B U L U' L' B' .",
            'U U2',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )


class TestSolvePLLSkipPure(unittest.TestCase):
    """Test Solve with PLL skip for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1713970887
        self.time = 39453000000
        self.scramble = """
        R' L' D R' B' U2 B L U D2 F2 R F2 L U2 R' F2 R' F2 R2 F2
        """
        self.solution = """
        L@0 U'@400 R@978 F@1841 L'@2310 F'@2459 B'@3927 U@4517 R'@5358 U'@5368
        U'@5668 D'@8349 L'@10965 D@11191 L@11375 F'@12654 D@13038 F@13407
        D@14647 B@15763 D@15841 B'@15944 D@16791 D@17716 D@18030 F@18719
        D'@19053 D'@19343 D@19766 F'@20111 D'@20629 F@20964 F@22542 D@22651
        F'@22712 R@23866 U'@24924 R@25399 U@25776 R@26412 R@26706 D'@27528
        R'@27895 D@27979 R@28123 L@29088 D@29192 L'@29259 D'@29400 D@30496
        F'@30946 D'@31255 F@31570 D@32783 R@33873 D@33960 R'@34055 L@35970
        D@36102 D@36394 L'@36448 D@36824 D@37082 L@37204 D'@37256 L'@37382
        L@38382 D'@38523 D'@38761 L'@38925 D'@39073 L@39168 D'@39320 L'@39453
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
            ('OLL', 'step'),
            ('PLL', 'skipped'),
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
            "R D' L F R' F' . B' D L' D2 .",
            "U' . R' U R . F' U F . U . B U B'",
            "U . U2 F U2 U F' U' F . F U F' . L . D' L D L2 U' L' U L .",
            "R U R' U' . U F' U' F . U . L U L' .",
            "R U2 R' U2 R U' R' .",
            "R U2 R' U' R U' R'",
            '',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )
