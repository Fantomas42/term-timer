import datetime
import unittest

from cubing_algs.parsing import parse_moves

from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.solve import Solve


class TestSolve03(unittest.TestCase):
    maxDiff = None

    def setUp(self):
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
        self.solve.orientation = parse_moves('z2')

    def test_datetime(self):
        self.assertEqual(
            self.solve.datetime,
            datetime.datetime(
                2025, 7, 8, 18, 21, 58,
                tzinfo=datetime.timezone.utc,  # noqa: UP017
            ),
        )

    def test_final_time(self):
        self.assertEqual(
            self.solve.final_time,
            self.time,
        )

    def test_move_times(self):
        self.assertEqual(
            self.solve.move_times,
            [
                ['D', 0],
                ['L', 419],
                ['L', 510],
                ['D', 1019],
                ["R'", 1681],
                ["R'", 1769],
                ["B'", 2551],
            ],
        )

    def test_advanced(self):
        self.assertTrue(
            self.solve.advanced,
        )

    def test_solution(self):
        self.assertEqual(
            self.solve.solution.metrics['htm'],
            7,
        )

    def test_reconstruction(self):
        self.assertEqual(
            str(self.solve.reconstruction),
            "U@0 R2@510 U@1019 L2@1769 B'@2551",
        )

    def test_tps(self):
        self.assertEqual(
            self.solve.tps,
            2.7451303725453884,
        )

    def test_all_missed_moves(self):
        self.assertEqual(
            self.solve.all_missed_moves,
            0,
        )

    def test_step_missed_moves(self):
        self.assertEqual(
            self.solve.step_missed_moves,
            0,
        )

    def test_step_pauses(self):
        self.assertEqual(
            self.solve.step_pauses,
            1,
        )

    def test_execution_pauses(self):
        self.assertEqual(
            self.solve.execution_pauses,
            1,
        )

    def test_execution_missed_moves(self):
        self.assertEqual(
            self.solve.execution_missed_moves,
            0,
        )

    def test_transition_missed_moves(self):
        self.assertEqual(
            self.solve.transition_missed_moves,
            0,
        )

    def test_method(self):
        self.assertEqual(
            self.solve.method,
            CF4OPAnalyser,
        )

    def test_recognition_time(self):
        self.assertEqual(
            self.solve.recognition_time,
            0,
        )

    def test_execution_time(self):
        self.assertEqual(
            self.solve.execution_time,
            2551000000,
        )

    def test_move_speed(self):
        self.assertEqual(
            self.solve.move_speed,
            364428571.4285714,
        )

    def test_pause_threshold(self):
        self.assertEqual(
            self.solve.pause_threshold,
            728857142.8571428,
        )

    def test_score(self):
        self.assertEqual(
            self.solve.score,
            20,
        )

    def test_method_score(self):
        self.assertEqual(
            self.solve.method_applied.score,
            50,
        )

    def test_summary(self):
        inputs = self.solve.method_applied.summary
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

    def test_timeline_inputs(self):
        self.assertEqual(
            self.solve.timeline_inputs,
            [0, 728, 1092, 1602, 2111, 2497, 2861, 3279, 3643],
        )

    def test_reconstruction_step_line(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
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

    def test_reconstruction_step_line_multiple(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
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

    def test_reconstruction_step_text(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
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

    def test_reconstruction_step_text_multiple(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
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
