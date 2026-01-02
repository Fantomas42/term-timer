"""Tests for solve with broken result."""
import unittest

from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolve32(unittest.TestCase):
    """Test Solve with broken result for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1713971700
        self.time = 56773000000
        self.scramble = """
        L2 B' R2 B2 L2 U2 F U2 B R2 U2 D' R2 D' R' D' U' B' L U'
        """
        self.solution = """
        L@0 D'@340 B@862 B@1137 F@1498 F@1841 U'@2612 U'@2978 B@4728 D@4784
        B'@4902 D'@5009 D@7092 F@8722 D'@8821 D'@9081 F'@9207 D@9558 F'@10276
        D'@10386 D'@10612 F@10670 D'@12400 U'@12410 U'@12748 R'@13951 D@14043
        R@14134 D@14882 D'@15099 F'@16154 D@16374 F@16718 D@17091 L'@17904
        D'@18011 L@18178 D'@18311 L'@18467 L@19264 D@21561 L'@22733 D'@22863
        L@23013 D'@23155 L'@23317 D@23448 L@23542 D@24037 D@25306 F'@26190
        D'@26600 F@26762 D@27371 R@27744 D@27990 R'@28234 D'@28642 F'@29729
        D'@30026 D'@30289 D'@30723 F@30893 D'@31726 F'@31735 D@31952 F@32094
        D'@32205 D'@32468 L@33351 D@33461 L'@33522 B@34523 B'@34922 D@35472
        B'@36216 D'@36766 L'@36866 D@37001 L@37187 B@37431 L@38327 D'@38529
        D'@38750 L'@38855 D'@39007 L@39088 L@39228 L'@39332 D'@39978 L'@40195
        L@43010 R'@43014 L@43318 R'@43333 U@44021 U@44307 R'@44667 L@44667
        L@44941 R'@44944 F'@48289 D@48496 F'@48682 D'@49211 L'@49576 F'@49873
        L@50235 L@50365 D'@50495 L'@50738 D@50982 L'@51222 F@51501 L@51712
        F@52143 D'@52771 D@54129 L@54600 D@54699 L'@54762 F'@55038 L@55356
        D@55448 L'@55534 D'@55664 L'@55942 F@56084 L@56247 L@56361 D'@56449
        L'@56620 D'@56773
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'auto'


class TestSolve32CF4OP(TestSolve32):
    """Test Solve with broken result for checking output in CF4OP."""

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('F2L', 'virtual'),
            ('F2L 4', 'substep'),
            ('F2L', 'skipped'),
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

    def test_reconstruction_step_text(self) -> None:
        """Test reconstruction step text."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "R U' B2 F2 D2 . B U B' U' . U . F U2 F' U F' U2 F . "
            "U' D2 . L' U L U U' . F' U F U . R' U' R U' R' R . U "
            ". R' U' R U' R' U R U . U . F' U' F U L U L' U' . F' "
            "U2 U' F . U' F' U F U2 . R U R' . B B' U B' U' R' U R "
            "B . R U2 R' U' R2 R' U' r' . M U2 M2 .",
            '',
            '',
            "F' U F' U' R' F' R2 U' R' U R' F R F U' . U R U R' F' "
            "R U R' U' R' F R2 U' R' U'",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_text(source, multiple=False),
                    expected,
                )


class TestSolve32LBL(TestSolve32):
    """Test Solve with broken result for checking output in LBL."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'lbl'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('Cross', 'skipped'),
            ('F1L', 'skipped'),
            ('F2L', 'step'),
            ('LL', 'step'),
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


class TestSolve32CFOP(TestSolve32):
    """Test Solve with broken result for checking output in CFOP."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'cfop'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('Cross', 'skipped'),
            ('F2L', 'skipped'),
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


class TestSolve32UROrientationCFOP(TestSolve32):
    """Test Solve with broken result for checking output in CFOP."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'cfop'
        self.solve.orientation = 'UR'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('Cross', 'step'),
            ('F2L', 'step'),
            ('OLL', 'skipped'),
            ('PLL', 'skipped'),
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
