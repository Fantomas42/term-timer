"""Tests for solve short."""
import unittest

from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolveShort(unittest.TestCase):
    """Test Solve short for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1766883476
        self.time = 2608404439
        self.scramble = "L2 D' L' F' L'"
        self.solution = """
        L@0 F@507 L@1019 D@1768 L@2518 L@2608
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'


class TestSolveShortAutoOrientation(TestSolveShort):
    """Test Solve short for checking output with auto orientation."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.orientation = 'auto'

    def test_reconstruction(self) -> None:
        """Test reconstruction."""
        self.assertEqual(
            str(self.solve.reconstruction),
            'U R U F U2',
        )

    def test_score(self) -> None:
        """Test score."""
        self.assertEqual(
            self.solve.score,
            20,
        )

    def test_method_score(self) -> None:
        """Test method score."""
        method_applied = get_method_applied(self.solve)
        self.assertEqual(
            method_applied.score,
            38.75,
        )

    def test_recognition_percent(self) -> None:
        """Test recognition percent."""
        self.assertEqual(
            self.solve.recognition_percent,
            28.757668711656436,
        )

    def test_execution_percent(self) -> None:
        """Test execution percent."""
        self.assertEqual(
            self.solve.execution_percent,
            71.24233128834356,
        )

    def test_recognition_execution_percent(self) -> None:
        """Test recognition + execution percent."""
        self.assertEqual(
            self.solve.recognition_percent
            + self.solve.execution_percent,
            100.0,
        )

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('XXXXCross', 'step'),
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

    def test_reconstruction_step_line(self) -> None:
        """Test reconstruction step line."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            (
                '[pre-auf]U[/pre-auf] R U [pause].[/pause] F '
                '[reco-pause].[/reco-pause]'
            ),
            '',
            '',
            '[post-auf]U2[/post-auf]',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_line(source, multiple=False),
                    expected,
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
            'U R U . F .',
            '',
            '',
            'U2',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_text(source, multiple=False),
                    expected,
                )

    def test_orientation_faces(self) -> None:
        """Test orientation faces."""
        self.solve.orientation = 'auto'

        self.assertEqual(
            self.solve.orientation_faces,
            'LD',
        )


class TestSolveShortDFOrientation(TestSolveShort):
    """Test Solve short for checking output with DF orientation."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.orientation = 'DF'

    def test_reconstruction(self) -> None:
        """Test reconstruction."""
        self.assertEqual(
            str(self.solve.reconstruction),
            'R F R U R2',
        )

    def test_score(self) -> None:
        """Test score."""
        self.assertEqual(
            self.solve.score,
            20,
        )

    def test_method_score(self) -> None:
        """Test method score."""
        method_applied = get_method_applied(self.solve)
        self.assertEqual(
            method_applied.score,
            41.5,
        )

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('Cross', 'step'),
            ('F2L', 'skipped'),
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

    def test_reconstruction_step_line(self) -> None:
        """Test reconstruction step line."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            'R F R U R2',
            '',
            '',
            '',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_line(source, multiple=False),
                    expected,
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
            'R F R U R2',
            '',
            '',
            '',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_text(source, multiple=False),
                    expected,
                )

    def test_recognition_percent(self) -> None:
        """Test recognition percent."""
        self.assertEqual(
            self.solve.recognition_percent,
            0,
        )

    def test_execution_percent(self) -> None:
        """Test execution percent."""
        self.assertEqual(
            self.solve.execution_percent,
            100.0,
        )

    def test_recognition_execution_percent(self) -> None:
        """Test recognition + execution percent."""
        self.assertEqual(
            self.solve.recognition_percent
            + self.solve.execution_percent,
            100.0,
        )


class TestSolveShortLBLAutoOrientation(TestSolveShort):
    """Test Short solve in LBL in auto orientation."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'lbl'
        self.solve.orientation = 'auto'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)

        inputs = method_applied.summary
        outputs = [
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


class TestSolveShortLBLDFOrientation(TestSolveShort):
    """Test Short solve in LBL in DF orientation."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'lbl'
        self.solve.orientation = 'DF'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)

        inputs = method_applied.summary
        outputs = [
            ('F1L', 'step'),
            ('F2L', 'skipped'),
            ('LL', 'skipped'),
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


class TestSolveShortCFOPAutoOrientation(TestSolveShort):
    """Test Short solve in CFOP in auto orientation."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'cfop'
        self.solve.orientation = 'auto'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)

        inputs = method_applied.summary
        outputs = [
            ('Cross', 'step'),
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


class TestSolveShortCFOPUFOrientation(TestSolveShort):
    """Test Short solve in CFOP in UF orientation."""

    def setUp(self) -> None:
        """Test setup."""
        super().setUp()
        self.solve.method_name = 'cfop'
        self.solve.orientation = 'UF'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)

        inputs = method_applied.summary
        outputs = [
            ('Cross', 'step'),
            ('F2L', 'skipped'),
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
