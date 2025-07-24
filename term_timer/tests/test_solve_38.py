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
            "B L' U F2 U2 B U B' U' U R' U' R U2 L U L' U2 R' U R U' R' U' R2 U R' U' U U' F U2 F' U2 F U' F' U2 F' U F U' F' U' F U2 L' R L' B2 L B L' B L B R' L U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",  # noqa: E501
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
            12.6863747658,
        )

    def test_method_score(self):
        self.assertEqual(
            self.solve.method_applied.score,
            18.25,
        )

    def test_reconstruction_step_line(self):
        inputs = [
            info
            for info in self.solve.method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "B L' [pause].[/pause] U F2 [reco-pause].[/reco-pause]",

            "[pre-auf]U2[/pre-auf] [pair-ie]B U B'[/pair-ie] "
            "[deletion]U'[/deletion] "
            "[pause].[/pause] [deletion]U[/deletion] "
            "[pair-ie]R' U' R[/pair-ie] "
            "U2 [pair-ie]L U L'[/pair-ie] [reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] [pause].[/pause] "
            "[pre-auf]U[/pre-auf] R' U [sa]R U' R' U'[/sa] "
            "R [reco-pause].[/reco-pause]",

            "[pair-ie]R U R'[/pair-ie] [deletion]U'[/deletion] "
            "[pause].[/pause] [deletion]U[/deletion] U' "
            "[pause].[/pause] [ne]F U2 F'[/ne] "
            "U2 [pair-ie]F U' F'[/pair-ie] [reco-pause].[/reco-pause]",

            "[pre-auf]U2[/pre-auf] [pause].[/pause] "
            "F' U [sa]F U' F' U'[/sa] F [reco-pause].[/reco-pause]",

            "[pre-auf]U'[/pre-auf] [pause].[/pause] "
            "[pre-auf]U'[/pre-auf] [pause].[/pause] "
            "[slice]M[/slice] "
            "[chair]L' U2 L U L' U L[/chair] "
            "U "
            "[slice]M'[/slice] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] R' U' F' "
            "[sexy-move]R U R' U'[/sexy-move] R' F R2 U' "
            "[sexy-move]R' U' R U[/sexy-move] [pair-ie]R' U R[/pair-ie] "
            "[post-auf]U2[/post-auf]",
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
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "[pre-auf]U2[/pre-auf] [pair-ie]B U B'[/pair-ie] "
            "[deletion]U'[/deletion] "
            "[pause].[/pause] [deletion]U[/deletion] "
            "[addition].[/addition] [pair-ie]R' U' R[/pair-ie] "
            "U2 [pair-ie]L U L'[/pair-ie] [reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] [pause].[/pause] "
            "[pre-auf]U[/pre-auf] R' U [sa]R U' R' U'[/sa] "
            "R [reco-pause].[/reco-pause]",

            "[pair-ie]R U R'[/pair-ie] [deletion]U'[/deletion] "
            "[pause].[/pause] [pause].[/pause] [deletion]U[/deletion] "
            "U' [pause].[/pause] "
            "[ne]F U2 F'[/ne] U2 [pair-ie]F U' F'[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "[pre-auf]U2[/pre-auf] [pause].[/pause] "
            "F' U [sa]F U' F' U'[/sa] F "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "[pre-auf]U'[/pre-auf] [pause].[/pause] "
            "[pre-auf]U'[/pre-auf] [pause].[/pause] "
            "[slice]M[/slice] "
            "[chair]L' U2 L U L' U L[/chair] "
            "U "
            "[slice]M'[/slice] "
            "[reco-pause].[/reco-pause]",

            "[pre-auf]U[/pre-auf] R' U' F' "
            "[sexy-move]R U R' U'[/sexy-move] R' F R2 U' "
            "[sexy-move]R' U' R U[/sexy-move] [pair-ie]R' U R[/pair-ie] "
            "[post-auf]U2[/post-auf]",
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

            "U' . U' . M L' U2 L U L' U L U M' .",

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

            "U' . U' . M L' U2 L U L' U L U M' .",

            "U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=True),
                expected,
            )

    def test_link_alg_cubing(self):
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation%0AB_L-_._._U_F2_._._._._%2F%2F_Cross_Reco:_0.00s_Exec:_1.89s_HTM:_4_%0AU2_B_U_B-_U-_._U_R-_U-_R_U2_L_U_L-_._%2F%2F_F2L_1_(BL)_Reco:_2.34s_Exec:_4.20s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_._U_R-_U_R_U-_R-_U-_R_._%2F%2F_F2L_2_(BR)_Reco:_0.96s_Exec:_2.46s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B2%0AR_U_R-_U-_._._U_U-_._F_U2_F-_U2_F_U-_F-_._._._._%2F%2F_F2L_3_(FL)_Reco:_0.66s_Exec:_3.66s_HTM:_13_%0AU2_._F-_U_F_U-_F-_U-_F_._._%2F%2F_F2L_4_(FR)_Reco:_2.16s_Exec:_2.28s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU-_._U-_._M_L-_U2_L_U_L-_U_L_U_M-_._%2F%2F_OLL_(10_Anti-Kite)_Reco:_1.20s_Exec:_3.39s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_R-_U-_F-_R_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_U_R_U2_%2F%2F_PLL_(F)_Reco:_0.72s_Exec:_3.90s_HTM:_20_Pre%26%2345%3BAUF:_%26%232b%3B1_Post%26%2345%3BAUF:_%26%232b%3B2%0A&setup=D2_R2_D2_U-_R2_U_R2_F2_R-_B2_F-_L_F-_R_F_U2_B_L-',
            self.solve.link_alg_cubing,
        )

    def test_link_cube_db(self):
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation%0AB_L-_._._U_F2_._._._._%2F%2F_Cross_Reco:_0.00s_Exec:_1.89s_HTM:_4_%0AU2_B_U_B-_U-_._U_R-_U-_R_U2_L_U_L-_._%2F%2F_F2L_1_(BL)_Reco:_2.34s_Exec:_4.20s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_._U_R-_U_R_U-_R-_U-_R_._%2F%2F_F2L_2_(BR)_Reco:_0.96s_Exec:_2.46s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B2%0AR_U_R-_U-_._._U_U-_._F_U2_F-_U2_F_U-_F-_._._._._%2F%2F_F2L_3_(FL)_Reco:_0.66s_Exec:_3.66s_HTM:_13_%0AU2_._F-_U_F_U-_F-_U-_F_._._%2F%2F_F2L_4_(FR)_Reco:_2.16s_Exec:_2.28s_HTM:_8_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU-_._U-_._M_L-_U2_L_U_L-_U_L_U_M-_._%2F%2F_OLL_(10_Anti-Kite)_Reco:_1.20s_Exec:_3.39s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_R-_U-_F-_R_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_U_R_U2_%2F%2F_PLL_(F)_Reco:_0.72s_Exec:_3.90s_HTM:_20_Pre%26%2345%3BAUF:_%26%232b%3B1_Post%26%2345%3BAUF:_%26%232b%3B2%0A&scramble=D2_R2_D2_U-_R2_U_R2_F2_R-_B2_F-_L_F-_R_F_U2_B_L-',
            self.solve.link_cube_db,
        )

    def test_reconstruction_steps_timing(self):
        self.assertEqual(
            self.solve.reconstruction_steps_timing,
            [
                [0, 483, 'z2'],
                [483, 724, 'B'],
                [871, 1113, "L'"],
                [1457, 1699, '.'],
                [2043, 2285, 'U'],
                [2285, 2614, 'F2'],
                [3542, 3784, '.'],
                [4776, 5164, 'U2'],
                [5312, 5554, 'B'],
                [5554, 5675, 'U'],
                [5675, 5764, "B'"],
                [5764, 5855, "U'"],
                [5913, 6155, '.'],
                [6212, 6454, 'U'],
                [6543, 6785, "R'"],
                [6872, 7114, "U'"],
                [7203, 7445, 'R'],
                [7626, 8014, 'U2'],
                [8132, 8374, 'L'],
                [8492, 8734, 'U'],
                [8912, 9154, "L'"],
                [9393, 9635, '.'],
                [9873, 10115, 'U'],
                [10203, 10445, '.'],
                [10532, 10774, 'U'],
                [10774, 11014, "R'"],
                [11014, 11164, 'U'],
                [11282, 11524, 'R'],
                [11524, 11734, "U'"],
                [11792, 12034, "R'"],
                [12092, 12334, "U'"],
                [12334, 12574, 'R'],
                [12662, 12904, '.'],
                [12992, 13234, 'R'],
                [13234, 13294, 'U'],
                [13294, 13384, "R'"],
                [13384, 13474, "U'"],
                [13817, 14059, '.'],
                [14402, 14644, 'U'],
                [14644, 14824, "U'"],
                [14942, 15184, '.'],
                [15302, 15544, 'F'],
                [15546, 15934, 'U2'],
                [15934, 15994, "F'"],
                [16176, 16564, 'U2'],
                [16564, 16684, 'F'],
                [16684, 16714, "U'"],
                [16714, 16894, "F'"],
                [17732, 17974, '.'],
                [18907, 19295, 'U2'],
                [19323, 19565, '.'],
                [19592, 19834, "F'"],
                [19834, 19984, 'U'],
                [20103, 20345, 'F'],
                [20345, 20555, "U'"],
                [20581, 20823, "F'"],
                [20853, 21095, "U'"],
                [21095, 21334, 'F'],
                [21692, 21934, '.'],
                [22292, 22534, "U'"],
                [22682, 22924, '.'],
                [23072, 23314, "U'"],
                [23358, 23600, '.'],
                [23643, 23885, 'M'],
                [23972, 24214, "L'"],
                [24246, 24634, 'U2'],
                [24634, 24815, 'L'],
                [24815, 24936, 'U'],
                [24936, 25055, "L'"],
                [25055, 25174, 'U'],
                [25174, 25295, 'L'],
                [25295, 25474, 'U'],
                [25682, 25924, "M'"],
                [26042, 26284, '.'],
                [26402, 26644, 'U'],
                [26824, 27066, "R'"],
                [27066, 27185, "U'"],
                [27272, 27514, "F'"],
                [27662, 27904, 'R'],
                [27904, 28025, 'U'],
                [28025, 28084, "R'"],
                [28084, 28205, "U'"],
                [28205, 28384, "R'"],
                [28384, 28474, 'F'],
                [28474, 28744, 'R2'],
                [28744, 28834, "U'"],
                [28834, 28984, "R'"],
                [28984, 29134, "U'"],
                [29134, 29344, 'R'],
                [29344, 29495, 'U'],
                [29495, 29524, "R'"],
                [29643, 29885, 'U'],
                [29885, 30004, 'R'],
                [30156, 30544, 'U2'],
            ],
        )
