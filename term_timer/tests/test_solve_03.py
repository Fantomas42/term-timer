"""Tests for solve 03."""
import datetime
import unittest

from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolve03(unittest.TestCase):  # noqa: PLR0904
    """Tests for solve 03 reconstruction and analysis."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1751998918
        self.time = 2549969965
        self.scramble = "B R2 D' L2 D'"
        self.solution = """
        D@0 L@419 L@510 D@1019 R'@1681 R'@1769 B'@2551
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'DF'

    def test_datetime(self) -> None:
        """Test datetime."""
        self.assertEqual(
            self.solve.datetime,
            datetime.datetime(
                2025, 7, 8, 18, 21, 58,
                tzinfo=datetime.timezone.utc,  # noqa: UP017
            ),
        )

    def test_final_time(self) -> None:
        """Test final time."""
        self.assertEqual(
            self.solve.final_time,
            self.time,
        )

    def test_move_times(self) -> None:
        """Test move times."""
        self.assertEqual(
            self.solve.move_times,
            [
                ('D', 0),
                ('L', 419),
                ('L', 510),
                ('D', 1019),
                ("R'", 1681),
                ("R'", 1769),
                ("B'", 2551),
            ],
        )

    def test_advanced(self) -> None:
        """Test advanced."""
        self.assertTrue(
            self.solve.advanced,
        )

    def test_solution(self) -> None:
        """Test solution."""
        self.assertEqual(
            self.solve.solution.metrics.htm,
            7,
        )

    def test_reconstruction(self) -> None:
        """Test reconstruction."""
        self.assertEqual(
            str(self.solve.reconstruction),
            "U R2 U L2 B'",
        )

    def test_reconstruction_orientation_auto(self) -> None:
        """Test reconstruction orientation auto."""
        self.solve.orientation = 'auto'
        self.assertEqual(
            str(self.solve.reconstruction),
            "B L2 B R2 U'",
        )
        self.assertEqual(str(self.solve.orientation_moves), "x'")

    def test_tps(self) -> None:
        """Test tps."""
        self.assertEqual(
            self.solve.tps,
            2.7451303725453884,
        )

    def test_all_missed_moves(self) -> None:
        """Test all missed moves."""
        self.assertEqual(
            self.solve.all_missed_moves,
            0,
        )

    def test_step_missed_moves(self) -> None:
        """Test step missed moves."""
        self.assertEqual(
            self.solve.step_missed_moves,
            0,
        )

    def test_step_pauses(self) -> None:
        """Test step pauses."""
        self.assertEqual(
            self.solve.step_pauses,
            1,
        )

    def test_execution_pauses(self) -> None:
        """Test execution pauses."""
        self.assertEqual(
            self.solve.execution_pauses,
            1,
        )

    def test_execution_missed_moves(self) -> None:
        """Test execution missed moves."""
        self.assertEqual(
            self.solve.execution_missed_moves,
            0,
        )

    def test_transition_missed_moves(self) -> None:
        """Test transition missed moves."""
        self.assertEqual(
            self.solve.transition_missed_moves,
            0,
        )

    def test_method_analyser(self) -> None:
        """Test method analyser."""
        self.assertEqual(
            self.solve.method_analyser,
            CF4OPAnalyser,
        )

    def test_recognition_time(self) -> None:
        """Test recognition time."""
        self.assertEqual(
            self.solve.recognition_time,
            0,
        )

    def test_execution_time(self) -> None:
        """Test execution time."""
        self.assertEqual(
            self.solve.execution_time,
            2551000000,
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

    def test_move_speed(self) -> None:
        """Test move speed."""
        self.assertEqual(
            self.solve.move_speed,
            364428571.4285714,
        )

    def test_pause_threshold(self) -> None:
        """Test pause threshold."""
        self.assertEqual(
            self.solve.pause_threshold,
            728857142.8571428,
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

    def test_reconstruction_steps_timing(self) -> None:
        """Test reconstruction steps timing."""
        self.assertEqual(
            self.solve.reconstruction_steps_timing,
            [
                (0, 583, 'z2'),
                (583, 947, 'U'),
                (947, 1457, 'R2'),
                (1601, 1966, 'U'),
                (2132, 2716, 'L2'),
                (2742, 3107, '.'),
                (3133, 3498, "B'"),
            ],
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
            "U R2 U L2 [pause].[/pause] B'",
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

    def test_reconstruction_step_line_multiple(self) -> None:
        """Test reconstruction step line multiple."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "U R2 U L2 [pause].[/pause] B'",
            '',
            '',
            '',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_line(source, multiple=True),
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
            "U R2 U L2 . B'",
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

    def test_reconstruction_step_text_multiple(self) -> None:
        """Test reconstruction step text multiple."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "U R2 U L2 . B'",
            '',
            '',
            '',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_text(source, multiple=True),
                    expected,
                )
