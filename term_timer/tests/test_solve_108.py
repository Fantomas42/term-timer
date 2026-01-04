"""Tests for solve with broken result."""
import unittest

from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolve108(unittest.TestCase):
    """Test Solve with broken result for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1715018355
        self.time = 26996000000
        self.scramble = """
        U B' U B2 D' R2 D' L2 R2 U F2 U B2 F' D2 U' R' F L' F
        """
        self.solution = """
        L'@0 R'@592 B'@842 F'@2293 U@3296 L'@3453 U'@3940 R'@4987 D@5182 R@5512
        D'@5826 R@6402 D@6710 R'@6885 D@7928 D@9204 D@9466 L'@10165 D'@10527
        L@10646 D'@11992 F'@13047 D'@13160 F@13301 D'@13484 R'@14014 D@14106
        R@14263 D@15942 F@17037 L@17216 D@17331 L'@17398 D'@17490 F'@17810
        D@18454 D@18857 L@19121 D'@19227 D'@19447 L'@19584 D'@19737 L@19829
        D'@19956 L'@20081 L@22766 R'@22768 R'@23038 L@23040 U@23413 R'@24270
        L@24278 R'@24538 L@24544 D@24848 D@25128 L@25858 R'@25860 L@26116
        R'@26118 U@26370 L@26756 R'@26758 L@26996 R'@26996
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'RU'


class TestSolve108CF4OPRU(TestSolve108):
    """
    Test Solve with broken result for checking output
    in CF4OP oriented in RU.
    """

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('XXCross', 'step'),
            ('F2L', 'virtual'),
            ('F2L 3+4', 'substep'),
            ('OLL', 'skipped'),
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
