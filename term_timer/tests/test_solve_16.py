"""Tests for solve 16."""
import unittest

from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolve16(unittest.TestCase):
    """Test Solve with broken result for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1713907375
        self.time = 44693000000
        self.scramble = """
        R2 U D R' U2 B' R' U' L2 F2 U' R2 F2 R2 D B2 R2 D F U'
        """
        self.solution = """
        B@0 B@594 R'@1088 B'@1249 D@1893 F@2343 F@2714 U@3232 D@7079
        R'@7794 D@8007 R@8189 D'@8262 R'@9464 D@9632 R@9748 D@10346
        D@10605 F'@11189 D'@11957 F@12059 B'@13223 D'@13353 B@13447
        D'@13629 D@14207 D'@14629 L'@14802 D@15004 L@15158 D'@15822
        D@16787 B'@17121 D@17298 D@17897 B@17907 D'@18154 D'@18402
        F@19275 D@19859 F'@20824 D'@21680 D'@21912 R@22267 D@22417
        R'@22508 D@22827 R@22971 D'@23053 R'@23176 L@27717 D@27727
        L'@27836 F@28516 F@28577 U'@29039 R@29546 D'@30161 R@30258
        D@30731 R'@30891 U@31454 F@31854 F@31929 D@33756 D@34209
        L@34340 D'@34479 L'@34597 D'@35573 D@37045 L@37247 D'@37384
        D'@37622 L@37842 L@37905 D'@37998 L@38337 L@38379 D'@38479
        L@38808 L@38853 D'@38942 D'@39211 L@39410 F'@41387 R@41887
        F'@42048 L'@42197 L'@42774 F@43059 R'@43129 F'@43247 L'@43418
        L'@43641 F@43775 F@43812 D@44407 D@44693
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'


class TestSolve16CF4OP(TestSolve16):
    """Test Solve with OLL skip in CF4OP."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'cf4op'

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
            with self.subTest(name=source['name']):
                self.assertEqual(
                    source['name'],
                    expected[0],
                )
                self.assertEqual(
                    source['type'],
                    expected[1],
                )


class TestSolve16CFOP(TestSolve16):
    """Test Solve with OLL skip in CFOP."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'cfop'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('Cross', 'step'),
            ('F2L', 'step'),
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
