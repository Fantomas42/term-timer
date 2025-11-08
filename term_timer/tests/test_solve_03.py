"""Tests for solve 03."""

import datetime
import unittest
from typing import cast

from term_timer.methods.base import Analyser
from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.solve import Solve


def get_method_applied(solve: Solve) -> Analyser:
    """Get method_applied, asserting it's not None in tests."""
    return cast('Analyser', solve.method_applied)


class TestSolve03(unittest.TestCase):  # noqa: PLR0904
    maxDiff = None

    def setUp(self) -> None:
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
        self.assertEqual(
            self.solve.datetime,
            datetime.datetime(
                2025, 7, 8, 18, 21, 58,
                tzinfo=datetime.timezone.utc,  # noqa: UP017
            ),
        )

    def test_final_time(self) -> None:
        self.assertEqual(
            self.solve.final_time,
            self.time,
        )

    def test_move_times(self) -> None:
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
        self.assertTrue(
            self.solve.advanced,
        )

    def test_solution(self) -> None:
        self.assertEqual(
            self.solve.solution.metrics.htm,
            7,
        )

    def test_reconstruction(self) -> None:
        self.assertEqual(
            str(self.solve.reconstruction),
            "U R2 U L2 B'",
        )

    def test_reconstruction_orientation_auto(self) -> None:
        self.solve.orientation = 'auto'
        self.assertEqual(
            str(self.solve.reconstruction),
            "B L2 B R2 U'",
        )
        self.assertEqual(str(self.solve.orientation_moves), "x'")

    def test_tps(self) -> None:
        self.assertEqual(
            self.solve.tps,
            2.7451303725453884,
        )

    def test_all_missed_moves(self) -> None:
        self.assertEqual(
            self.solve.all_missed_moves,
            0,
        )

    def test_step_missed_moves(self) -> None:
        self.assertEqual(
            self.solve.step_missed_moves,
            0,
        )

    def test_step_pauses(self) -> None:
        self.assertEqual(
            self.solve.step_pauses,
            1,
        )

    def test_execution_pauses(self) -> None:
        self.assertEqual(
            self.solve.execution_pauses,
            1,
        )

    def test_execution_missed_moves(self) -> None:
        self.assertEqual(
            self.solve.execution_missed_moves,
            0,
        )

    def test_transition_missed_moves(self) -> None:
        self.assertEqual(
            self.solve.transition_missed_moves,
            0,
        )

    def test_method_analyser(self) -> None:
        self.assertEqual(
            self.solve.method_analyser,
            CF4OPAnalyser,
        )

    def test_recognition_time(self) -> None:
        self.assertEqual(
            self.solve.recognition_time,
            0,
        )

    def test_execution_time(self) -> None:
        self.assertEqual(
            self.solve.execution_time,
            2551000000,
        )

    def test_move_speed(self) -> None:
        self.assertEqual(
            self.solve.move_speed,
            364428571.4285714,
        )

    def test_pause_threshold(self) -> None:
        self.assertEqual(
            self.solve.pause_threshold,
            728857142.8571428,
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
            50,
        )

    def test_summary(self) -> None:
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('Full Cube', 'step'),
            ('F2L', 'skipped'),
            ('OLL', 'skipped'),
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

    def test_reconstruction_steps_timing(self) -> None:
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
            self.assertEqual(
                self.solve.reconstruction_step_line(source, multiple=False),
                expected,
            )

    def test_reconstruction_step_line_multiple(self) -> None:
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
            self.assertEqual(
                self.solve.reconstruction_step_line(source, multiple=True),
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
            "U R2 U L2 . B'",
            '',
            '',
            '',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )

    def test_reconstruction_step_text_multiple(self) -> None:
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
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=True),
                expected,
            )
