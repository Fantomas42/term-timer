"""Tests for solve 54."""
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


class TestSolve54(unittest.TestCase):  # noqa: PLR0904
    """Tests for solve 54 reconstruction and analysis."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
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
        self.solve.orientation = 'DF'

    def test_datetime(self) -> None:
        """Test datetime."""
        self.assertEqual(
            self.solve.datetime,
            datetime.datetime(
                2025, 7, 3, 20, 53, 27,
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
                ('L', 0),
                ('L', 88),
                ('D', 538),
                ('F', 1108),
                ('R', 1350),
                ('D', 2249),
                ('F', 2608),
                ('F', 2818),
                ("D'", 3119),
                ('B', 3419),
                ('B', 3748),
                ("D'", 5069),
                ('L', 5428),
                ('D', 5549),
                ("L'", 5639),
                ('D', 5968),
                ('B', 6329),
                ("D'", 6689),
                ("B'", 6959),
                ('D', 9388),
                ("F'", 9718),
                ('D', 9898),
                ('F', 10229),
                ("D'", 10469),
                ('F', 10798),
                ('D', 11099),
                ("F'", 11279),
                ("D'", 12328),
                ("D'", 12598),
                ('L', 13198),
                ("D'", 13288),
                ("L'", 13408),
                ('D', 13738),
                ("D'", 14188),
                ('L', 14549),
                ("D'", 14638),
                ("D'", 14849),
                ("L'", 14908),
                ('D', 15208),
                ("F'", 15419),
                ("D'", 15659),
                ('F', 15930),
                ('D', 17908),
                ('R', 18059),
                ("D'", 18149),
                ("R'", 18358),
                ("D'", 18419),
                ("B'", 18809),
                ('D', 18958),
                ('B', 19078),
                ("D'", 19529),
                ('L', 20099),
                ("R'", 20101),
                ('D', 20519),
                ('B', 20609),
                ("D'", 20699),
                ("B'", 21149),
                ("D'", 21358),
                ('R', 21508),
                ('D', 21658),
                ("L'", 22019),
                ('L', 24238),
                ('D', 24329),
                ("L'", 24419),
                ("D'", 24539),
                ("L'", 24718),
                ('F', 24838),
                ('L', 24988),
                ('L', 25051),
                ("D'", 25139),
                ("L'", 25289),
                ("D'", 25409),
                ('L', 25768),
                ('D', 25919),
                ("L'", 26008),
                ('L', 26458),
                ("L'", 26492),
                ("F'", 26818),
                ("D'", 27148),
                ("D'", 27359),
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
            80,
        )

    def test_reconstruction(self) -> None:
        """Test reconstruction."""
        self.assertEqual(
            str(self.solve.reconstruction),
            "R2 U F L U F2 U' B2 U' R U R' U B U' B' U F' U F U' F U F' U2 R U' R' U U' R U2 R' U F' U' F U L U' L' U' B' U B U' R L' U B U' B' U' L U R' R U R' U' R' F R2 U' R' U' R U R' R R' F' U2",  # noqa: E501
        )

    def test_reconstruction_orientation_uf(self) -> None:
        """Test reconstruction orientation uf."""
        self.solve.orientation = 'UF'
        self.assertEqual(
            str(self.solve.reconstruction),
            "L2 D F R D F2 D' B2 D' L D L' D B D' B' D F' D F D' F D F' D2 L D' L' D D' L D2 L' D F' D' F D R D' R' D' B' D B D' L R' D B D' B' D' R D L' L D L' D' L' F L2 D' L' D' L D L' L L' F' D2",  # noqa: E501
        )

    def test_reconstruction_orientation_auto(self) -> None:
        """Test reconstruction orientation auto."""
        self.solve.orientation = 'auto'
        self.assertEqual(
            str(self.solve.reconstruction),
            "R2 U F L U F2 U' B2 U' R U R' U B U' B' U F' U F U' F U F' U2 R U' R' U U' R U2 R' U F' U' F U L U' L' U' B' U B U' R L' U B U' B' U' L U R' R U R' U' R' F R2 U' R' U' R U R' R R' F' U2",  # noqa: E501
        )

    def test_tps(self) -> None:
        """Test tps."""
        self.assertEqual(
            self.solve.tps,
            2.924190942726092,
        )

    def test_all_missed_moves(self) -> None:
        """Test all missed moves."""
        self.assertEqual(
            self.solve.all_missed_moves,
            10,
        )

    def test_step_missed_moves(self) -> None:
        """Test step missed moves."""
        self.assertEqual(
            self.solve.step_missed_moves,
            8,
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
            8,
        )

    def test_transition_missed_moves(self) -> None:
        """Test transition missed moves."""
        self.assertEqual(
            self.solve.transition_missed_moves,
            2,
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
            9447000000,
        )

    def test_execution_time(self) -> None:
        """Test execution time."""
        self.assertEqual(
            self.solve.execution_time,
            17912000000,
        )

    def test_move_speed(self) -> None:
        """Test move speed."""
        self.assertEqual(
            self.solve.move_speed,
            223900000.0,
        )

    def test_pause_threshold(self) -> None:
        """Test pause threshold."""
        self.assertEqual(
            self.solve.pause_threshold,
            447800000.0,
        )

    def test_score(self) -> None:
        """Test score."""
        self.assertEqual(
            self.solve.score,
            5.9284010814000005,
        )

    def test_method_score(self) -> None:
        """Test method score."""
        method_applied = get_method_applied(self.solve)
        self.assertEqual(
            method_applied.score,
            16.0,
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
            "R2 [pause].[/pause] U [pause].[/pause] F L [pause].[/pause] "
            "U F2 U' B2 [reco-pause].[/reco-pause]",

            "U' "
            "[su]R U R' U[/su] "
            "[pair-ie]B U' B'[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "U "
            "[pair-ie]F' U F[/pair-ie] "
            "U' "
            "[pair-ie]F U F'[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "U2 [pause].[/pause] "
            "R [deletion]U'[/deletion] [deletion]R'[/deletion] "
            "[addition].[/addition] U [deletion].[/deletion] "
            "[deletion]U'[/deletion] [deletion]R[/deletion] "
            "[deletion]U2[/deletion] R' U [pair-ie]F' U' F[/pair-ie] "
            "[reco-pause].[/reco-pause]",

            "U "
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

    def test_reconstruction_step_line_multiple(self) -> None:
        """Test reconstruction step line multiple."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "R2 [pause].[/pause] U [pause].[/pause] F L [pause].[/pause] "
            "[pause].[/pause] U F2 U' B2 "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "U' "
            "[su]R U R' U[/su] "
            "[pair-ie]B U' B'[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause]",

            "U "
            "[pair-ie]F' U F[/pair-ie] "
            "U' "
            "[pair-ie]F U F'[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "U2 [pause].[/pause] "
            "R [deletion]U'[/deletion] [deletion]R'[/deletion] "
            "[addition].[/addition] [addition].[/addition] "
            "[addition].[/addition] U [deletion].[/deletion] "
            "[deletion]U'[/deletion] [deletion]R[/deletion] "
            "[deletion]U2[/deletion] R' U [pair-ie]F' U' F[/pair-ie] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause] "
            "[reco-pause].[/reco-pause] [reco-pause].[/reco-pause]",

            "U "
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

    def test_reconstruction_step_text(self) -> None:
        """Test reconstruction step text."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
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

    def test_reconstruction_step_text_multiple(self) -> None:
        """Test reconstruction step text multiple."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
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

    def test_link_alg_cubing(self) -> None:
        """Test link alg cubing."""
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation_(DF)%0AR2_._U_._F_L_._._U_F2_U-_B2_._._%2F%2F_Cross_Reco:_0.00s_Exec:_3.75s_HTM:_8_%0AU-_R_U_R-_U_B_U-_B-_._._._._._%2F%2F_F2L_1_(05_Back_Right)_Reco:_1.32s_Exec:_1.89s_HTM:_8_%0AU_F-_U_F_U-_F_U_F-_._._%2F%2F_F2L_2_(15_Front_Left)_Reco:_2.43s_Exec:_1.89s_HTM:_8_%0AU2_._R_U-_R-_U_._U-_R_U2_R-_U_F-_U-_F_._._._._%2F%2F_F2L_3_(35_Front_Right)_Reco:_1.05s_Exec:_3.60s_HTM:_13_%0AU_L_U-_L-_U-_B-_U_B_._%2F%2F_F2L_4_(26_Back_Left)_Reco:_1.98s_Exec:_1.17s_HTM:_8_%0AU-_._M_F_U_F-_._U-_F-_L_F_l-_._._._._%2F%2F_OLL_(32)_Reco:_0.45s_Exec:_2.49s_HTM:_11_Pre%26%2345%3BAUF:_%26%232b%3B1%0AR_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_._R_R-_F-_U2_%2F%2F_PLL_(T)_Reco:_2.22s_Exec:_3.12s_HTM:_17_Post%26%2345%3BAUF:_%26%232b%3B2%0A&setup=F2_D2_F2_D-_U-_L2_B2_L2_B2_U_L_U-_B_D_R2_U_L_F2_U_R2_U2',
            self.solve.link_alg_cubing,
        )

    def test_link_cube_db(self) -> None:
        """Test link cube db."""
        self.assertIn(
            '&alg=z2_%2F%2F_Orientation_(DF)%0AR2_._U_._F_L_._._U_F2_U-_B2_._._%2F%2F_Cross_Reco:_0.00s_Exec:_3.75s_HTM:_8_%0AU-_R_U_R-_U_B_U-_B-_._._._._._%2F%2F_F2L_1_(05_Back_Right)_Reco:_1.32s_Exec:_1.89s_HTM:_8_%0AU_F-_U_F_U-_F_U_F-_._._%2F%2F_F2L_2_(15_Front_Left)_Reco:_2.43s_Exec:_1.89s_HTM:_8_%0AU2_._R_U-_R-_U_._U-_R_U2_R-_U_F-_U-_F_._._._._%2F%2F_F2L_3_(35_Front_Right)_Reco:_1.05s_Exec:_3.60s_HTM:_13_%0AU_L_U-_L-_U-_B-_U_B_._%2F%2F_F2L_4_(26_Back_Left)_Reco:_1.98s_Exec:_1.17s_HTM:_8_%0AU-_._M_F_U_F-_._U-_F-_L_F_l-_._._._._%2F%2F_OLL_(32)_Reco:_0.45s_Exec:_2.49s_HTM:_11_Pre%26%2345%3BAUF:_%26%232b%3B1%0AR_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_._R_R-_F-_U2_%2F%2F_PLL_(T)_Reco:_2.22s_Exec:_3.12s_HTM:_17_Post%26%2345%3BAUF:_%26%232b%3B2%0A&scramble=F2_D2_F2_D-_U-_L2_B2_L2_B2_U_L_U-_B_D_R2_U_L_F2_U_R2_U2',
            self.solve.link_cube_db,
        )

    def test_reconstruction_steps_timing(self) -> None:
        """Test reconstruction steps timing."""
        self.assertEqual(
            self.solve.reconstruction_steps_timing,
            [
                (0, 358, 'z2'),
                (358, 669, 'R2'),
                (670, 894, '.'),
                (895, 1119, 'U'),
                (1180, 1404, '.'),
                (1465, 1689, 'F'),
                (1707, 1931, 'L'),
                (2157, 2381, '.'),
                (2606, 2830, 'U'),
                (3040, 3399, 'F2'),
                (3476, 3700, "U'"),
                (3970, 4329, 'B2'),
                (4766, 4990, '.'),
                (5426, 5650, "U'"),
                (5785, 6009, 'R'),
                (6009, 6130, 'U'),
                (6130, 6220, "R'"),
                (6325, 6549, 'U'),
                (6686, 6910, 'B'),
                (7046, 7270, "U'"),
                (7316, 7540, "B'"),
                (8531, 8755, '.'),
                (9745, 9969, 'U'),
                (10075, 10299, "F'"),
                (10299, 10479, 'U'),
                (10586, 10810, 'F'),
                (10826, 11050, "U'"),
                (11155, 11379, 'F'),
                (11456, 11680, 'U'),
                (11680, 11860, "F'"),
                (12161, 12385, '.'),
                (12820, 13179, 'U2'),
                (13255, 13479, '.'),
                (13555, 13779, 'R'),
                (13779, 13869, "U'"),
                (13869, 13989, "R'"),
                (14095, 14319, 'U'),
                (14320, 14544, '.'),
                (14545, 14769, "U'"),
                (14906, 15130, 'R'),
                (15130, 15430, 'U2'),
                (15430, 15489, "R'"),
                (15565, 15789, 'U'),
                (15789, 16000, "F'"),
                (16016, 16240, "U'"),
                (16287, 16511, 'F'),
                (17276, 17500, '.'),
                (18265, 18489, 'U'),
                (18489, 18640, 'L'),
                (18640, 18730, "U'"),
                (18730, 18939, "L'"),
                (18939, 19000, "U'"),
                (19166, 19390, "B'"),
                (19390, 19539, 'U'),
                (19539, 19659, 'B'),
                (19661, 19885, '.'),
                (19886, 20110, "U'"),
                (20171, 20395, '.'),
                (20456, 20680, 'M'),
                (20876, 21100, 'F'),
                (21100, 21190, 'U'),
                (21190, 21280, "F'"),
                (21281, 21505, '.'),
                (21506, 21730, "U'"),
                (21730, 21939, "F'"),
                (21939, 22089, 'L'),
                (22089, 22239, 'F'),
                (22376, 22600, "l'"),
                (23486, 23710, '.'),
                (24595, 24819, 'R'),
                (24819, 24910, 'U'),
                (24910, 25000, "R'"),
                (25000, 25120, "U'"),
                (25120, 25299, "R'"),
                (25299, 25419, 'F'),
                (25419, 25632, 'R2'),
                (25632, 25720, "U'"),
                (25720, 25870, "R'"),
                (25870, 25990, "U'"),
                (26125, 26349, 'R'),
                (26349, 26500, 'U'),
                (26500, 26589, "R'"),
                (26590, 26814, '.'),
                (26815, 27039, 'R'),
                (27039, 27073, "R'"),
                (27175, 27399, "F'"),
                (27581, 27940, 'U2'),
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
                'Back Left', 'Front Right',
                'Back Right', 'Front Left',
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
                'Back Right', 'Front Left',
                'Front Right', 'Back Left',
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
                'Front Right', 'Back Left',
                'Front Left', 'Back Right',
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
                'Front Left', 'Back Right',
                'Back Left', 'Front Right',
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
                    ['05', '15', '35', '26'],
                )

            del self.solve.method_applied
            del self.solve.orientation_faces
            del self.solve.orientation_moves
