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
            "R2 U F L U F2 U' B2 U' R U R' U B U' B' U F' U F U' F U F' U2 R U' R' U U' R U2 R' U F' U' F U L U' L' U' B' U B U' R L' U B U' B' U' L U R' R U R' U' R' F R2 U' R' U' R U R' R R' F' U2",  # noqa: E501
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

    def test_method_analyser(self):
        self.assertEqual(
            self.solve.method_analyser,
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

    def test_method_score(self):
        self.assertEqual(
            self.solve.method_applied.score,
            16.0,
        )

    def test_reconstruction_step_line(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "R2 [pause].[/pause] U [pause].[/pause] F L [pause].[/pause] "
            "U F2 U' B2 [reco-pause].[/reco-pause]",

            "[pre-auf]U'[/pre-auf] "
            "[su]R U R' U[/su] "
            "[pair-ie]B U' B'[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] "
            "[pair-ie]F' U F[/pair-ie] "
            "U' "
            "[pair-ie]F U F'[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U2[/pre-auf] [pause].[/pause] "
            "R [deletion]U'[/deletion] [deletion]R'[/deletion] "
            "[addition].[/addition] U [deletion].[/deletion] "
            "[deletion]U'[/deletion] [deletion]R[/deletion] "
            "[deletion]U2[/deletion] R' U [pair-ie]F' U' F[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] "
            "[sa]L U' L' U'[/sa] "
            "[pair-ie]B' U B[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U'[/pre-auf] [pause].[/pause] "
            "[slice]M[/slice] [pair-ie]F U F'[/pair-ie] "
            "[pause].[/pause] U' F' L F [wide]l'[/wide] "
            "[reco-pause].[/reco-pause]",

            "[sexy-move]R U R' U'[/sexy-move] R' F R2 U' "
            "[sexy-move]R' U' R U[/sexy-move] "
            "[deletion]R'[/deletion] [pause].[/pause] "
            "[deletion]R[/deletion] R' F' [post-auf]U2[/post-auf]",
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
            "[pause].[/pause] U F2 U' B2 "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "[pre-auf]U'[/pre-auf] "
            "[su]R U R' U[/su] "
            "[pair-ie]B U' B'[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] "
            "[pair-ie]F' U F[/pair-ie] "
            "U' "
            "[pair-ie]F U F'[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "[pre-auf]U2[/pre-auf] [pause].[/pause] "
            "R [deletion]U'[/deletion] [deletion]R'[/deletion] "
            "[addition].[/addition] [addition].[/addition] "
            "[addition].[/addition] U [deletion].[/deletion] "
            "[deletion]U'[/deletion] [deletion]R[/deletion] "
            "[deletion]U2[/deletion] R' U [pair-ie]F' U' F[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] "
            "[sa]L U' L' U'[/sa] "
            "[pair-ie]B' U B[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U'[/pre-auf] [pause].[/pause] "
            "[slice]M[/slice] [pair-ie]F U F'[/pair-ie] "
            "[pause].[/pause] U' F' L F [wide]l'[/wide] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "[sexy-move]R U R' U'[/sexy-move] R' F R2 U' "
            "[sexy-move]R' U' R U[/sexy-move] "
            "[deletion]R'[/deletion] [pause].[/pause] "
            "[deletion]R[/deletion] R' F' [post-auf]U2[/post-auf]",
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

            "U' . M F U F' . U' F' L F l' .",

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

            "U' . M F U F' . U' F' L F l' . . . .",

            "R U R' U' R' F R2 U' R' U' R U R' . R R' F' U2",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=True),
                expected,
            )

    def test_link_alg_cubing(self):
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation%0AR2_._U_._F_L_._._U_F2_U-_B2_._._%2F%2F_Cross_Reco:_0.00s_Exec:_3.75s_HTM:_8_%0AU-_R_U_R-_U_B_U-_B-_._._._._._%2F%2F_F2L_1_(BR)_Reco:_1.32s_Exec:_1.89s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B1%0AU_F-_U_F_U-_F_U_F-_._._%2F%2F_F2L_2_(FL)_Reco:_2.43s_Exec:_1.89s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B1%0AU2_._R_U-_R-_U_._U-_R_U2_R-_U_F-_U-_F_._._._._%2F%2F_F2L_3_(FR)_Reco:_1.05s_Exec:_3.60s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_L_U-_L-_U-_B-_U_B_._%2F%2F_F2L_4_(BL)_Reco:_1.98s_Exec:_1.17s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B1%0AU-_._M_F_U_F-_._U-_F-_L_F_l-_._._._._%2F%2F_OLL_(32_Anti-Couch)_Reco:_0.45s_Exec:_2.49s_HTM:_11_Pre%26%2345%3BAUF:_%26%232b%3B1%0AR_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_._R_R-_F-_U2_%2F%2F_PLL_(T)_Reco:_2.22s_Exec:_3.12s_HTM:_17_Post%26%2345%3BAUF:_%26%232b%3B2%0A&setup=F2_D2_F2_D-_U-_L2_B2_L2_B2_U_L_U-_B_D_R2_U_L_F2_U_R2_U2',
            self.solve.link_alg_cubing,
        )

    def test_link_cube_db(self):
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation%0AR2_._U_._F_L_._._U_F2_U-_B2_._._%2F%2F_Cross_Reco:_0.00s_Exec:_3.75s_HTM:_8_%0AU-_R_U_R-_U_B_U-_B-_._._._._._%2F%2F_F2L_1_(BR)_Reco:_1.32s_Exec:_1.89s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B1%0AU_F-_U_F_U-_F_U_F-_._._%2F%2F_F2L_2_(FL)_Reco:_2.43s_Exec:_1.89s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B1%0AU2_._R_U-_R-_U_._U-_R_U2_R-_U_F-_U-_F_._._._._%2F%2F_F2L_3_(FR)_Reco:_1.05s_Exec:_3.60s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_L_U-_L-_U-_B-_U_B_._%2F%2F_F2L_4_(BL)_Reco:_1.98s_Exec:_1.17s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B1%0AU-_._M_F_U_F-_._U-_F-_L_F_l-_._._._._%2F%2F_OLL_(32_Anti-Couch)_Reco:_0.45s_Exec:_2.49s_HTM:_11_Pre%26%2345%3BAUF:_%26%232b%3B1%0AR_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_._R_R-_F-_U2_%2F%2F_PLL_(T)_Reco:_2.22s_Exec:_3.12s_HTM:_17_Post%26%2345%3BAUF:_%26%232b%3B2%0A&scramble=F2_D2_F2_D-_U-_L2_B2_L2_B2_U_L_U-_B_D_R2_U_L_F2_U_R2_U2',
            self.solve.link_cube_db,
        )

    def test_reconstruction_steps_timing(self):
        self.assertEqual(
            self.solve.reconstruction_steps_timing,
            [
                [0, 447, 'z2'],
                [447, 758, 'R2'],
                [759, 983, '.'],
                [984, 1208, 'U'],
                [1269, 1493, '.'],
                [1554, 1778, 'F'],
                [1796, 2020, 'L'],
                [2246, 2470, '.'],
                [2695, 2919, 'U'],
                [3129, 3488, 'F2'],
                [3565, 3789, "U'"],
                [4059, 4418, 'B2'],
                [4855, 5079, '.'],
                [5515, 5739, "U'"],
                [5874, 6098, 'R'],
                [6098, 6219, 'U'],
                [6219, 6309, "R'"],
                [6414, 6638, 'U'],
                [6775, 6999, 'B'],
                [7135, 7359, "U'"],
                [7405, 7629, "B'"],
                [8620, 8844, '.'],
                [9834, 10058, 'U'],
                [10164, 10388, "F'"],
                [10388, 10568, 'U'],
                [10675, 10899, 'F'],
                [10915, 11139, "U'"],
                [11244, 11468, 'F'],
                [11545, 11769, 'U'],
                [11769, 11949, "F'"],
                [12250, 12474, '.'],
                [12909, 13268, 'U2'],
                [13344, 13568, '.'],
                [13644, 13868, 'R'],
                [13868, 13958, "U'"],
                [13958, 14078, "R'"],
                [14184, 14408, 'U'],
                [14409, 14633, '.'],
                [14634, 14858, "U'"],
                [14995, 15219, 'R'],
                [15219, 15519, 'U2'],
                [15519, 15578, "R'"],
                [15654, 15878, 'U'],
                [15878, 16089, "F'"],
                [16105, 16329, "U'"],
                [16376, 16600, 'F'],
                [17365, 17589, '.'],
                [18354, 18578, 'U'],
                [18578, 18729, 'L'],
                [18729, 18819, "U'"],
                [18819, 19028, "L'"],
                [19028, 19089, "U'"],
                [19255, 19479, "B'"],
                [19479, 19628, 'U'],
                [19628, 19748, 'B'],
                [19750, 19974, '.'],
                [19975, 20199, "U'"],
                [20261, 20485, '.'],
                [20547, 20771, 'M'],
                [20965, 21189, 'F'],
                [21189, 21279, 'U'],
                [21279, 21369, "F'"],
                [21370, 21594, '.'],
                [21595, 21819, "U'"],
                [21819, 22028, "F'"],
                [22028, 22178, 'L'],
                [22178, 22328, 'F'],
                [22465, 22689, "l'"],
                [23575, 23799, '.'],
                [24684, 24908, 'R'],
                [24908, 24999, 'U'],
                [24999, 25089, "R'"],
                [25089, 25209, "U'"],
                [25209, 25388, "R'"],
                [25388, 25508, 'F'],
                [25508, 25721, 'R2'],
                [25721, 25809, "U'"],
                [25809, 25959, "R'"],
                [25959, 26079, "U'"],
                [26214, 26438, 'R'],
                [26438, 26589, 'U'],
                [26589, 26678, "R'"],
                [26679, 26903, '.'],
                [26904, 27128, 'R'],
                [27128, 27162, "R'"],
                [27264, 27488, "F'"],
                [27670, 28029, 'U2'],
            ],
        )
