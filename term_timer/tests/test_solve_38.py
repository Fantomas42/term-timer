"""Tests for solve 38."""
import datetime
import unittest
from typing import cast

from term_timer.methods.base import Analyser
from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.solve import Solve


def get_method_applied(solve: Solve) -> Analyser:
    """
    Get method_applied, asserting it's not None in tests.

    Returns:
        The method_applied Analyser instance.

    """
    return cast('Analyser', solve.method_applied)


class TestSolve38(unittest.TestCase):  # noqa: PLR0904
    """Tests for solve 38 reconstruction and analysis."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
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
        self.solve.orientation = 'DF'

    def test_datetime(self) -> None:
        """Test datetime."""
        self.assertEqual(
            self.solve.datetime,
            datetime.datetime(
                2025, 5, 26, 17, 34, 9,
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
                ('B', 0),
                ("R'", 389),
                ('D', 1561),
                ("F'", 1800),
                ("F'", 1890),
                ("D'", 4230),
                ("D'", 4440),
                ('B', 4830),
                ('D', 4951),
                ("B'", 5040),
                ("D'", 5131),
                ('D', 5730),
                ("L'", 6061),
                ("D'", 6390),
                ('L', 6721),
                ('D', 7050),
                ('D', 7290),
                ('R', 7650),
                ('D', 8010),
                ("R'", 8430),
                ('D', 9391),
                ('D', 10050),
                ("L'", 10290),
                ('D', 10440),
                ('L', 10800),
                ("D'", 11010),
                ("L'", 11310),
                ("D'", 11610),
                ('L', 11850),
                ('L', 12510),
                ('D', 12570),
                ("L'", 12660),
                ("D'", 12750),
                ('D', 13920),
                ("D'", 14100),
                ('F', 14820),
                ('D', 14971),
                ('D', 15210),
                ("F'", 15270),
                ('D', 15630),
                ('D', 15840),
                ('F', 15960),
                ("D'", 15990),
                ("F'", 16170),
                ('D', 18330),
                ('D', 18571),
                ("F'", 19110),
                ('D', 19260),
                ('F', 19621),
                ("D'", 19831),
                ("F'", 20099),
                ("D'", 20371),
                ('F', 20610),
                ("D'", 21810),
                ("D'", 22590),
                ("R'", 23160),
                ('L', 23161),
                ("R'", 23490),
                ('B', 23670),
                ('B', 23910),
                ('R', 24091),
                ('B', 24212),
                ("R'", 24331),
                ('B', 24450),
                ('R', 24571),
                ('B', 24750),
                ("L'", 25199),
                ('R', 25200),
                ('D', 25920),
                ("L'", 26342),
                ("D'", 26461),
                ("F'", 26790),
                ('L', 27180),
                ('D', 27301),
                ("L'", 27360),
                ("D'", 27481),
                ("L'", 27660),
                ('F', 27750),
                ('L', 27930),
                ('L', 28020),
                ("D'", 28110),
                ("L'", 28260),
                ("D'", 28410),
                ('L', 28620),
                ('D', 28771),
                ("L'", 28800),
                ('D', 29161),
                ('L', 29280),
                ("D'", 29641),
                ("D'", 29820),
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
            90,
        )

    def test_reconstruction(self) -> None:
        """Test reconstruction."""
        self.assertEqual(
            str(self.solve.reconstruction),
            "B L' U F2 U2 B U B' U' U R' U' R U2 L U L' U2 R' U R U' R' U' R2 U R' U' U U' F U2 F' U2 F U' F' U2 F' U F U' F' U' F U2 L' R L' B2 L B L' B L B R' L U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",  # noqa: E501
        )

    def test_reconstruction_orientation_auto(self) -> None:
        """Test reconstruction orientation auto."""
        self.solve.orientation = 'auto'
        self.assertEqual(
            str(self.solve.reconstruction),
            "B L' U F2 U2 B U B' U' U R' U' R U2 L U L' U2 R' U R U' R' U' R2 U R' U' U U' F U2 F' U2 F U' F' U2 F' U F U' F' U' F U2 L' R L' B2 L B L' B L B R' L U R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R U2",  # noqa: E501
        )

    def test_tps(self) -> None:
        """Test tps."""
        self.assertEqual(
            self.solve.tps,
            3.0182983157248375,
        )

    def test_all_missed_moves(self) -> None:
        """Test all missed moves."""
        self.assertEqual(
            self.solve.all_missed_moves,
            4,
        )

    def test_step_missed_moves(self) -> None:
        """Test step missed moves."""
        self.assertEqual(
            self.solve.step_missed_moves,
            4,
        )

    def test_step_pauses(self) -> None:
        """Test step pauses."""
        self.assertEqual(
            self.solve.step_pauses,
            8,
        )

    def test_execution_pauses(self) -> None:
        """Test execution pauses."""
        self.assertEqual(
            self.solve.execution_pauses,
            8,
        )

    def test_execution_missed_moves(self) -> None:
        """Test execution missed moves."""
        self.assertEqual(
            self.solve.execution_missed_moves,
            4,
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
            8041000000,
        )

    def test_execution_time(self) -> None:
        """Test execution time."""
        self.assertEqual(
            self.solve.execution_time,
            21779000000,
        )

    def test_recognition_percent(self) -> None:
        """Test recognition percent."""
        self.assertEqual(
            self.solve.recognition_percent,
            26.965124077800127,
        )

    def test_execution_percent(self) -> None:
        """Test execution percent."""
        self.assertEqual(
            self.solve.execution_percent,
            73.03487592219987,
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
            241988888.8888889,
        )

    def test_pause_threshold(self) -> None:
        """Test pause threshold."""
        self.assertEqual(
            self.solve.pause_threshold,
            483977777.7777778,
        )

    def test_score(self) -> None:
        """Test score."""
        self.assertEqual(
            self.solve.score,
            12.6863747658,
        )

    def test_method_score(self) -> None:
        """Test method score."""
        method_applied = get_method_applied(self.solve)
        self.assertEqual(
            method_applied.score,
            18.25,
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
            "B L' [pause].[/pause] U F2 [reco-pause].[/reco-pause]",

            "U2 [pair-ie]B U B'[/pair-ie] "
            "[deletion]U'[/deletion] "
            "[pause].[/pause] [deletion]U[/deletion] "
            "[pair-ie]R' U' R[/pair-ie] "
            "U2 [pair-ie]L U L'[/pair-ie] [reco-pause].[/reco-pause]",

            "U [pause].[/pause] "
            "U R' U [sa]R U' R' U'[/sa] "
            "R [reco-pause].[/reco-pause]",

            "[pair-ie]R U R'[/pair-ie] [deletion]U'[/deletion] "
            "[pause].[/pause] [deletion]U[/deletion] U' "
            "[pause].[/pause] [ne]F U2 F'[/ne] "
            "U2 [pair-ie]F U' F'[/pair-ie] [reco-pause].[/reco-pause]",

            "U2 [pause].[/pause] "
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

    def test_reconstruction_step_line_multiple(self) -> None:
        """Test reconstruction step line multiple."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "B L' [pause].[/pause] [pause].[/pause] U F2 "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "U2 [pair-ie]B U B'[/pair-ie] "
            "[deletion]U'[/deletion] "
            "[pause].[/pause] [deletion]U[/deletion] "
            "[addition].[/addition] [pair-ie]R' U' R[/pair-ie] "
            "U2 [pair-ie]L U L'[/pair-ie] [reco-pause].[/reco-pause]",

            "U [pause].[/pause] "
            "U R' U [sa]R U' R' U'[/sa] "
            "R [reco-pause].[/reco-pause]",

            "[pair-ie]R U R'[/pair-ie] [deletion]U'[/deletion] "
            "[pause].[/pause] [pause].[/pause] [deletion]U[/deletion] "
            "U' [pause].[/pause] "
            "[ne]F U2 F'[/ne] U2 [pair-ie]F U' F'[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "U2 [pause].[/pause] "
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

    def test_reconstruction_step_text(self) -> None:
        """Test reconstruction step text."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
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

    def test_reconstruction_step_text_multiple(self) -> None:
        """Test reconstruction step text multiple."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
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

    def test_link_alg_cubing(self) -> None:
        """Test link alg cubing."""
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation_(DF)%0AB_L-_._._U_F2_._._._._%2F%2F_Cross_Reco:_0.00s_Exec:_1.89s_HTM:_4_%0AU2_B_U_B-_U-_._U_R-_U-_R_U2_L_U_L-_._%2F%2F_F2L_1_(28_Back_Left)_Reco:_2.34s_Exec:_4.20s_HTM:_13_%0AU_._U_R-_U_R_U-_R-_U-_R_._%2F%2F_F2L_2_(13_Back_Right)_Reco:_0.96s_Exec:_2.46s_HTM:_8_%0AR_U_R-_U-_._._U_U-_._F_U2_F-_U2_F_U-_F-_._._._._%2F%2F_F2L_3_(25_Front_Left)_Reco:_0.66s_Exec:_3.66s_HTM:_13_%0AU2_._F-_U_F_U-_F-_U-_F_._._%2F%2F_F2L_4_(13_Front_Right)_Reco:_2.16s_Exec:_2.28s_HTM:_8_%0AU-_._U-_._M_L-_U2_L_U_L-_U_L_U_M-_._%2F%2F_OLL_(10)_Reco:_1.20s_Exec:_3.39s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_R-_U-_F-_R_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_U_R_U2_%2F%2F_PLL_(F)_Reco:_0.72s_Exec:_3.90s_HTM:_20_Pre%26%2345%3BAUF:_%26%232b%3B1_Post%26%2345%3BAUF:_%26%232b%3B2%0A&setup=D2_R2_D2_U-_R2_U_R2_F2_R-_B2_F-_L_F-_R_F_U2_B_L-',
            self.solve.link_alg_cubing,
        )

    def test_link_cube_db(self) -> None:
        """Test link cube db."""
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation_(DF)%0AB_L-_._._U_F2_._._._._%2F%2F_Cross_Reco:_0.00s_Exec:_1.89s_HTM:_4_%0AU2_B_U_B-_U-_._U_R-_U-_R_U2_L_U_L-_._%2F%2F_F2L_1_(28_Back_Left)_Reco:_2.34s_Exec:_4.20s_HTM:_13_%0AU_._U_R-_U_R_U-_R-_U-_R_._%2F%2F_F2L_2_(13_Back_Right)_Reco:_0.96s_Exec:_2.46s_HTM:_8_%0AR_U_R-_U-_._._U_U-_._F_U2_F-_U2_F_U-_F-_._._._._%2F%2F_F2L_3_(25_Front_Left)_Reco:_0.66s_Exec:_3.66s_HTM:_13_%0AU2_._F-_U_F_U-_F-_U-_F_._._%2F%2F_F2L_4_(13_Front_Right)_Reco:_2.16s_Exec:_2.28s_HTM:_8_%0AU-_._U-_._M_L-_U2_L_U_L-_U_L_U_M-_._%2F%2F_OLL_(10)_Reco:_1.20s_Exec:_3.39s_HTM:_13_Pre%26%2345%3BAUF:_%26%232b%3B2%0AU_R-_U-_F-_R_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_U_R_U2_%2F%2F_PLL_(F)_Reco:_0.72s_Exec:_3.90s_HTM:_20_Pre%26%2345%3BAUF:_%26%232b%3B1_Post%26%2345%3BAUF:_%26%232b%3B2%0A&scramble=D2_R2_D2_U-_R2_U_R2_F2_R-_B2_F-_L_F-_R_F_U2_B_L-',
            self.solve.link_cube_db,
        )

    def test_reconstruction_steps_timing(self) -> None:
        """Test reconstruction steps timing."""
        self.assertEqual(
            self.solve.reconstruction_steps_timing,
            [
                (0, 387, 'z2'),
                (387, 628, 'B'),
                (775, 1017, "L'"),
                (1361, 1603, '.'),
                (1947, 2189, 'U'),
                (2189, 2518, 'F2'),
                (3446, 3688, '.'),
                (4680, 5068, 'U2'),
                (5216, 5458, 'B'),
                (5458, 5579, 'U'),
                (5579, 5668, "B'"),
                (5668, 5759, "U'"),
                (5817, 6059, '.'),
                (6116, 6358, 'U'),
                (6447, 6689, "R'"),
                (6776, 7018, "U'"),
                (7107, 7349, 'R'),
                (7530, 7918, 'U2'),
                (8036, 8278, 'L'),
                (8396, 8638, 'U'),
                (8816, 9058, "L'"),
                (9297, 9539, '.'),
                (9777, 10019, 'U'),
                (10107, 10349, '.'),
                (10436, 10678, 'U'),
                (10678, 10918, "R'"),
                (10918, 11068, 'U'),
                (11186, 11428, 'R'),
                (11428, 11638, "U'"),
                (11696, 11938, "R'"),
                (11996, 12238, "U'"),
                (12238, 12478, 'R'),
                (12566, 12808, '.'),
                (12896, 13138, 'R'),
                (13138, 13198, 'U'),
                (13198, 13288, "R'"),
                (13288, 13378, "U'"),
                (13721, 13963, '.'),
                (14306, 14548, 'U'),
                (14548, 14728, "U'"),
                (14846, 15088, '.'),
                (15206, 15448, 'F'),
                (15450, 15838, 'U2'),
                (15838, 15898, "F'"),
                (16080, 16468, 'U2'),
                (16468, 16588, 'F'),
                (16588, 16618, "U'"),
                (16618, 16798, "F'"),
                (17636, 17878, '.'),
                (18811, 19199, 'U2'),
                (19227, 19469, '.'),
                (19496, 19738, "F'"),
                (19738, 19888, 'U'),
                (20007, 20249, 'F'),
                (20249, 20459, "U'"),
                (20485, 20727, "F'"),
                (20757, 20999, "U'"),
                (20999, 21238, 'F'),
                (21596, 21838, '.'),
                (22196, 22438, "U'"),
                (22586, 22828, '.'),
                (22976, 23218, "U'"),
                (23261, 23503, '.'),
                (23546, 23788, 'M'),
                (23876, 24118, "L'"),
                (24150, 24538, 'U2'),
                (24538, 24719, 'L'),
                (24719, 24840, 'U'),
                (24840, 24959, "L'"),
                (24959, 25078, 'U'),
                (25078, 25199, 'L'),
                (25199, 25378, 'U'),
                (25585, 25827, "M'"),
                (25946, 26188, '.'),
                (26306, 26548, 'U'),
                (26728, 26970, "R'"),
                (26970, 27089, "U'"),
                (27176, 27418, "F'"),
                (27566, 27808, 'R'),
                (27808, 27929, 'U'),
                (27929, 27988, "R'"),
                (27988, 28109, "U'"),
                (28109, 28288, "R'"),
                (28288, 28378, 'F'),
                (28378, 28648, 'R2'),
                (28648, 28738, "U'"),
                (28738, 28888, "R'"),
                (28888, 29038, "U'"),
                (29038, 29248, 'R'),
                (29248, 29399, 'U'),
                (29399, 29428, "R'"),
                (29547, 29789, 'U'),
                (29789, 29908, 'R'),
                (30060, 30448, 'U2'),
            ],
        )

    def test_orientation_faces(self) -> None:
        """Test orientation faces."""
        self.solve.orientation = 'auto'

        self.assertEqual(
            self.solve.orientation_faces,
            'DF',
        )

    def test_reconstruction_f2l_slot_naming_dr(self) -> None:
        """Test reconstruction of F2L slot naming (DR)."""
        self.solve.orientation = 'DR'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos'][0]
            for info in method_applied.summary
            if info['type'] != 'virtual' and 'F2L ' in info['name']
        ]

        self.assertEqual(
            pairs,
            [
                'Front Left', 'Back Left',
                'Front Right', 'Back Right',
            ],
        )

    def test_reconstruction_f2l_slot_naming_df(self) -> None:
        """Test reconstruction of F2L slot naming (DF)."""
        self.solve.orientation = 'DF'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos'][0]
            for info in method_applied.summary
            if info['type'] != 'virtual' and 'F2L ' in info['name']
        ]

        self.assertEqual(
            pairs,
            [
                'Back Left', 'Back Right',
                'Front Left', 'Front Right',
            ],
        )

    def test_reconstruction_f2l_slot_naming_dl(self) -> None:
        """Test reconstruction of F2L slot naming (DL)."""
        self.solve.orientation = 'DL'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos'][0]
            for info in method_applied.summary
            if info['type'] != 'virtual' and 'F2L ' in info['name']
        ]

        self.assertEqual(
            pairs,
            [
                'Back Right', 'Front Right',
                'Back Left', 'Front Left',
            ],
        )

    def test_reconstruction_f2l_slot_naming_db(self) -> None:
        """Test reconstruction of F2L slot naming (DB)."""
        self.solve.orientation = 'DB'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos'][0]
            for info in method_applied.summary
            if info['type'] != 'virtual' and 'F2L ' in info['name']
        ]

        self.assertEqual(
            pairs,
            [
                'Front Right', 'Front Left',
                'Back Right', 'Back Left',
            ],
        )

    def test_reconstruction_f2l_case_consistency(self) -> None:
        """
        Test reconstruction of F2L cases detection consistency
        accross orientations.
        """
        orientations = ['DF', 'DB', 'DL', 'DR']

        for orientation in orientations:
            self.solve.orientation = orientation

            method_applied = get_method_applied(self.solve)
            pairs = [
                info['case']
                for info in method_applied.summary
                if info['type'] != 'virtual' and 'F2L ' in info['name']
            ]

            with self.subTest(
                    orientation=orientation,
                    orientation_moves=str(self.solve.orientation_moves),
            ):
                self.assertEqual(
                    pairs,
                    ['28', '13', '25', '13'],
                )

            del self.solve.method_applied
            del self.solve.orientation_faces
            del self.solve.orientation_moves
