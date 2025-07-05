import datetime
import unittest

from cubing_algs.parsing import parse_moves

from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.solve import Solve


class TestSolve54(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.date = 1751576007
        self.time = 27357994593
        self.scramble = "F2 D2 F2 D' U' L2 B2 L2 B2 U L U' B D R2 U L F2 U R2 U2"  # noqa: E501
        self.solution = """
        L@0 L@88 D@538 F@1108 R@1350 D@2249 F@2608 F@2818 D'@3119 B@3419 B@3748 D'@5069 L@5428 D@5549 L'@5639 D@5968 B@6329 D'@6689 B'@6959 D@9388 F'@9718 D@9898 F@10229 D'@10469 F@10798 D@11099 F'@11279 D'@12328 D'@12598 L@13198 D'@13288 L'@13408 D@13738 D'@14188 L@14549 D'@14638 D'@14849 L'@14908 D@15208 F'@15419 D'@15659 F@15930 D@17908 R@18059 D'@18149 R'@18358 D'@18419 B'@18809 D@18958 B@19078 D'@19529 L@20099 R'@20101 D@20519 B@20609 D'@20699 B'@21149 D'@21358 R@21508 D@21658 L'@22019 L@24238 D@24329 L'@24419 D'@24539 L'@24718 F@24838 L@24988 L@25051 D'@25139 L'@25289 D'@25409 L@25768 D@25919 L'@26008 L@26458 L'@26492 F'@26818 D'@27148 D'@27359
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
                2025, 7, 3, 20, 53, 27,
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
                ['L', 0],
                ['L', 88],
                ['D', 538],
                ['F', 1108],
                ['R', 1350],
                ['D', 2249],
                ['F', 2608],
                ['F', 2818],
                ["D'", 3119],
                ['B', 3419],
                ['B', 3748],
                ["D'", 5069],
                ['L', 5428],
                ['D', 5549],
                ["L'", 5639],
                ['D', 5968],
                ['B', 6329],
                ["D'", 6689],
                ["B'", 6959],
                ['D', 9388],
                ["F'", 9718],
                ['D', 9898],
                ['F', 10229],
                ["D'", 10469],
                ['F', 10798],
                ['D', 11099],
                ["F'", 11279],
                ["D'", 12328],
                ["D'", 12598],
                ['L', 13198],
                ["D'", 13288],
                ["L'", 13408],
                ['D', 13738],
                ["D'", 14188],
                ['L', 14549],
                ["D'", 14638],
                ["D'", 14849],
                ["L'", 14908],
                ['D', 15208],
                ["F'", 15419],
                ["D'", 15659],
                ['F', 15930],
                ['D', 17908],
                ['R', 18059],
                ["D'", 18149],
                ["R'", 18358],
                ["D'", 18419],
                ["B'", 18809],
                ['D', 18958],
                ['B', 19078],
                ["D'", 19529],
                ['L', 20099],
                ["R'", 20101],
                ['D', 20519],
                ['B', 20609],
                ["D'", 20699],
                ["B'", 21149],
                ["D'", 21358],
                ['R', 21508],
                ['D', 21658],
                ["L'", 22019],
                ['L', 24238],
                ['D', 24329],
                ["L'", 24419],
                ["D'", 24539],
                ["L'", 24718],
                ['F', 24838],
                ['L', 24988],
                ['L', 25051],
                ["D'", 25139],
                ["L'", 25289],
                ["D'", 25409],
                ['L', 25768],
                ['D', 25919],
                ["L'", 26008],
                ['L', 26458],
                ["L'", 26492],
                ["F'", 26818],
                ["D'", 27148],
                ["D'", 27359],
            ],
        )

    def test_advanced(self):
        self.assertTrue(
            self.solve.advanced,
        )

    def test_solution(self):
        self.assertEqual(
            self.solve.solution.metrics['htm'],
            80,
        )

    def test_reconstruction(self):
        self.assertEqual(
            str(self.solve.reconstruction),
            "R2@88 U@538 F@1108 L@1350 U@2249 F2@2818 U'@3119 B2@3748 U'@5069 R@5428 U@5549 R'@5639 U@5968 B@6329 U'@6689 B'@6959 U@9388 F'@9718 U@9898 F@10229 U'@10469 F@10798 U@11099 F'@11279 U2@12598 R@13198 U'@13288 R'@13408 U@13738 U'@14188 R@14549 U2@14849 R'@14908 U@15208 F'@15419 U'@15659 F@15930 U@17908 L@18059 U'@18149 L'@18358 U'@18419 B'@18809 U@18958 B@19078 U'@19529 R@20099 L'@20101 U@20519 B@20609 U'@20699 B'@21149 U'@21358 L@21508 U@21658 R'@22019 R@24238 U@24329 R'@24419 U'@24539 R'@24718 F@24838 R2@25051 U'@25139 R'@25289 U'@25409 R@25768 U@25919 R'@26008 R@26458 R'@26492 F'@26818 U2@27359",  # noqa: E501
        )

    def test_tps(self):
        self.assertEqual(
            self.solve.tps,
            2.924190942726092,
        )

    def test_all_missed_moves(self):
        self.assertEqual(
            self.solve.all_missed_moves,
            10,
        )

    def test_step_missed_moves(self):
        self.assertEqual(
            self.solve.step_missed_moves,
            8,
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
            8,
        )

    def test_transition_missed_moves(self):
        self.assertEqual(
            self.solve.transition_missed_moves,
            2,
        )

    def test_method(self):
        self.assertEqual(
            self.solve.method,
            CF4OPAnalyser,
        )

    def test_recognition_time(self):
        self.assertEqual(
            self.solve.recognition_time,
            9447000000,
        )

    def test_execution_time(self):
        self.assertEqual(
            self.solve.execution_time,
            17912000000,
        )

    def test_move_speed(self):
        self.assertEqual(
            self.solve.move_speed,
            223900000.0,
        )

    def test_pause_threshold(self):
        self.assertEqual(
            self.solve.pause_threshold,
            447800000.0,
        )

    def test_score(self):
        self.assertEqual(
            self.solve.score,
            5.9284010814000005,
        )

    def test_reconstruction_step_line(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "R2 [pause].[/pause] U [pause].[/pause] F L [pause].[/pause] "
            "U F2 U' B2 [pause].[/pause]",

            "U' R U R' U B U' B' [pause].[/pause]",

            "U F' U F U' F U F' [pause].[/pause]",

            "U2 [pause].[/pause] R [red]U'[/red] [red]R'[/red] "
            "[green].[/green] U [red].[/red] "
            "[red]U'[/red] [red]R[/red] [red]U2[/red] "
            "R' U F' U' F [pause].[/pause]",

            "U L U' L' U' B' U B [pause].[/pause]",

            "U' [pause].[/pause] R L' U B U' [pause].[/pause] "
            "B' U' L U R' [pause].[/pause]",

            "R U R' U' R' F R2 U' R' U' R U [red]R'[/red] "
            "[pause].[/pause] [red]R[/red] R' F' U2",
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
            "R2 [pause].[/pause] U [pause].[/pause] F L [pause].[/pause] "
            "[pause].[/pause] U F2 U' B2 [pause].[/pause] [pause].[/pause]",

            "U' R U R' U B U' B' [pause].[/pause] [pause].[/pause] "
            "[pause].[/pause] [pause].[/pause] [pause].[/pause]",

            "U F' U F U' F U F' [pause].[/pause] [pause].[/pause]",

            "U2 [pause].[/pause] R [red]U'[/red] [red]R'[/red] "
            "[green].[/green] [green].[/green] "
            "[green].[/green] U [red].[/red] "
            "[red]U'[/red] [red]R[/red] [red]U2[/red] R' U F' U' F "
            "[pause].[/pause] [pause].[/pause] [pause].[/pause] "
            "[pause].[/pause]",

            "U L U' L' U' B' U B [pause].[/pause]",

            "U' [pause].[/pause] R L' U B U' [pause].[/pause] "
            "B' U' L U R' [pause].[/pause] [pause].[/pause] "
            "[pause].[/pause] [pause].[/pause]",

            "R U R' U' R' F R2 U' R' U' R U [red]R'[/red] [pause].[/pause] "
            "[red]R[/red] R' F' U2",
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
            "R2 . U . F L . U F2 U' B2 .",

            "U' R U R' U B U' B' .",

            "U F' U F U' F U F' .",

            "U2 . R U' R' U . U' R U2 R' U F' U' F .",

            "U L U' L' U' B' U B .",

            "U' . R L' U B U' . B' U' L U R' .",

            "R U R' U' R' F R2 U' R' U' R U R' . R R' F' U2",
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
            "R2 . U . F L . . U F2 U' B2 . .",

            "U' R U R' U B U' B' . . . . .",

            "U F' U F U' F U F' . .",

            "U2 . R U' R' U . U' R U2 R' U F' U' F . . . .",

            "U L U' L' U' B' U B .",

            "U' . R L' U B U' . B' U' L U R' . . . .",

            "R U R' U' R' F R2 U' R' U' R U R' . R R' F' U2",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=True),
                expected,
            )
