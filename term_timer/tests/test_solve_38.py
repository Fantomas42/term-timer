import datetime
import unittest

from cubing_algs.parsing import parse_moves

from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.solve import Solve


class TestSolve38(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.date = 1748280849
        self.time = 29818126171
        self.scramble = "D2 R2 D2 U' R2 U R2 F2 R' B2 F' L F' R F U2 B L'"
        self.solution = """
        B@0 R'@389 D@1561 F'@1800 F'@1890 D'@4230 D'@4440 B@4830 D@4951 B'@5040 D'@5131 D@5730 L'@6061 D'@6390 L@6721 D@7050 D@7290 R@7650 D@8010 R'@8430 D@9391 D@10050 L'@10290 D@10440 L@10800 D'@11010 L'@11310 D'@11610 L@11850 L@12510 D@12570 L'@12660 D'@12750 D@13920 D'@14100 F@14820 D@14971 D@15210 F'@15270 D@15630 D@15840 F@15960 D'@15990 F'@16170 D@18330 D@18571 F'@19110 D@19260 F@19621 D'@19831 F'@20099 D'@20371 F@20610 D'@21810 D'@22590 R'@23160 L@23161 R'@23490 B@23670 B@23910 R@24091 B@24212 R'@24331 B@24450 R@24571 B@24750 L'@25199 R@25200 D@25920 L'@26342 D'@26461 F'@26790 L@27180 D@27301 L'@27360 D'@27481 L'@27660 F@27750 L@27930 L@28020 D'@28110 L'@28260 D'@28410 L@28620 D@28771 L'@28800 D@29161 L@29280 D'@29641 D'@29820
        """  # noqa: E501

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
                2025, 5, 26, 17, 34, 9,
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
                ['B', 0],
                ["R'", 389],
                ['D', 1561],
                ["F'", 1800],
                ["F'", 1890],
                ["D'", 4230],
                ["D'", 4440],
                ['B', 4830],
                ['D', 4951],
                ["B'", 5040],
                ["D'", 5131],
                ['D', 5730],
                ["L'", 6061],
                ["D'", 6390],
                ['L', 6721],
                ['D', 7050],
                ['D', 7290],
                ['R', 7650],
                ['D', 8010],
                ["R'", 8430],
                ['D', 9391],
                ['D', 10050],
                ["L'", 10290],
                ['D', 10440],
                ['L', 10800],
                ["D'", 11010],
                ["L'", 11310],
                ["D'", 11610],
                ['L', 11850],
                ['L', 12510],
                ['D', 12570],
                ["L'", 12660],
                ["D'", 12750],
                ['D', 13920],
                ["D'", 14100],
                ['F', 14820],
                ['D', 14971],
                ['D', 15210],
                ["F'", 15270],
                ['D', 15630],
                ['D', 15840],
                ['F', 15960],
                ["D'", 15990],
                ["F'", 16170],
                ['D', 18330],
                ['D', 18571],
                ["F'", 19110],
                ['D', 19260],
                ['F', 19621],
                ["D'", 19831],
                ["F'", 20099],
                ["D'", 20371],
                ['F', 20610],
                ["D'", 21810],
                ["D'", 22590],
                ["R'", 23160],
                ['L', 23161],
                ["R'", 23490],
                ['B', 23670],
                ['B', 23910],
                ['R', 24091],
                ['B', 24212],
                ["R'", 24331],
                ['B', 24450],
                ['R', 24571],
                ['B', 24750],
                ["L'", 25199],
                ['R', 25200],
                ['D', 25920],
                ["L'", 26342],
                ["D'", 26461],
                ["F'", 26790],
                ['L', 27180],
                ['D', 27301],
                ["L'", 27360],
                ["D'", 27481],
                ["L'", 27660],
                ['F', 27750],
                ['L', 27930],
                ['L', 28020],
                ["D'", 28110],
                ["L'", 28260],
                ["D'", 28410],
                ['L', 28620],
                ['D', 28771],
                ["L'", 28800],
                ['D', 29161],
                ['L', 29280],
                ["D'", 29641],
                ["D'", 29820],
            ],
        )

    def test_advanced(self):
        self.assertTrue(
            self.solve.advanced,
        )

    def test_solution(self):
        self.assertEqual(
            self.solve.solution.metrics['htm'],
            90,
        )

    def test_reconstruction(self):
        self.assertEqual(
            str(self.solve.reconstruction),
            "B@0 L'@389 U@1561 F2@1890 U2@4440 B@4830 U@4951 B'@5040 U'@5131 U@5730 R'@6061 U'@6390 R@6721 U2@7290 L@7650 U@8010 L'@8430 U2@10050 R'@10290 U@10440 R@10800 U'@11010 R'@11310 U'@11610 R2@12510 U@12570 R'@12660 U'@12750 U@13920 U'@14100 F@14820 U2@15210 F'@15270 U2@15840 F@15960 U'@15990 F'@16170 U2@18571 F'@19110 U@19260 F@19621 U'@19831 F'@20099 U'@20371 F@20610 U2@22590 L'@23160 R@23161 L'@23490 B2@23910 L@24091 B@24212 L'@24331 B@24450 L@24571 B@24750 R'@25199 L@25200 U@25920 R'@26342 U'@26461 F'@26790 R@27180 U@27301 R'@27360 U'@27481 R'@27660 F@27750 R2@28020 U'@28110 R'@28260 U'@28410 R@28620 U@28771 R'@28800 U@29161 R@29280 U2@29820",  # noqa: E501
        )

    def test_tps(self):
        self.assertEqual(
            self.solve.tps,
            3.0182983157248375,
        )

    def test_all_missed_moves(self):
        self.assertEqual(
            self.solve.all_missed_moves,
            4,
        )

    def test_step_missed_moves(self):
        self.assertEqual(
            self.solve.step_missed_moves,
            4,
        )

    def test_step_pauses(self):
        self.assertEqual(
            self.solve.step_pauses,
            8,
        )

    def test_execution_pauses(self):
        self.assertEqual(
            self.solve.execution_pauses,
            8,
        )

    def test_execution_missed_moves(self):
        self.assertEqual(
            self.solve.execution_missed_moves,
            4,
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
            8041000000,
        )

    def test_execution_time(self):
        self.assertEqual(
            self.solve.execution_time,
            21779000000,
        )

    def test_move_speed(self):
        self.assertEqual(
            self.solve.move_speed,
            241988888.8888889,
        )

    def test_pause_threshold(self):
        self.assertEqual(
            self.solve.pause_threshold,
            483977777.7777778,
        )

    def test_score(self):
        self.assertEqual(
            self.solve.score,
            13.6863747658,
        )

    def test_reconstruction_step_line(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "B L' [pause].[/pause] U F2 [pause].[/pause]",

            "U2 B U B' [red]U'[/red] [pause].[/pause] [red]U[/red] R' U' R "
            "U2 L U L' [pause].[/pause]",

            "U [pause].[/pause] U R' U R U' R' U' R [pause].[/pause]",

            "R U R' [red]U'[/red] [pause].[/pause] [red]U[/red] U' "
            "[pause].[/pause] F U2 F' U2 F U' F' [pause].[/pause]",

            "U2 [pause].[/pause] F' U F U' F' U' F [pause].[/pause]",

            "U' [pause].[/pause] U' [pause].[/pause] "
            "L' R L' B2 L B L' B L B R' L [pause].[/pause]",

            "U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",
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
            "B L' [pause].[/pause] [pause].[/pause] U F2 "
            "[pause].[/pause] [pause].[/pause] "
            "[pause].[/pause] [pause].[/pause]",

            "U2 B U B' [red]U'[/red] [pause].[/pause] [red]U[/red] "
            "[green][pause].[/pause][/green] R' U' R "
            "U2 L U L' [pause].[/pause]",

            "U [pause].[/pause] U R' U R U' R' U' R [pause].[/pause]",

            "R U R' [red]U'[/red] [pause].[/pause] [pause].[/pause] "
            "[red]U[/red] U' [pause].[/pause] F U2 F' U2 F U' F' "
            "[pause].[/pause] [pause].[/pause] "
            "[pause].[/pause] [pause].[/pause]",

            "U2 [pause].[/pause] F' U F U' F' U' F [pause].[/pause] "
            "[pause].[/pause]",

            "U' [pause].[/pause] U' [pause].[/pause] "
            "L' R L' B2 L B L' B L B R' L [pause].[/pause]",

            "U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",
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
            "B L' . U F2 .",

            "U2 B U B' U' . U R' U' R U2 L U L' .",

            "U . U R' U R U' R' U' R .",

            "R U R' U' . U U' . F U2 F' U2 F U' F' .",

            "U2 . F' U F U' F' U' F .",

            "U' . U' . L' R L' B2 L B L' B L B R' L .",

            "U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",
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
            "B L' . . U F2 . . . .",

            "U2 B U B' U' . U R' U' R U2 L U L' .",

            "U . U R' U R U' R' U' R .",

            "R U R' U' . . U U' . F U2 F' U2 F U' F' . . . .",

            "U2 . F' U F U' F' U' F . .",

            "U' . U' . L' R L' B2 L B L' B L B R' L .",

            "U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=True),
                expected,
            )
