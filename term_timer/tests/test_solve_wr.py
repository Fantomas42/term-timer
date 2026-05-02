"""Tests for solve wr."""
import unittest

from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolveWR(unittest.TestCase):
    """
    Test Solve WR for color neutral analyse.

    http://cubesolv.es/solve/5757
    """

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1751998918
        self.time = 2549969965
        self.scramble = "F U2 L2 B2 F' U L2 U R2 D2 L' B L2 B' R2 U2"
        self.solution = """
        L@10 B2@20 L'@30 U'@40 F@50 U'@60 L'@70 F'@80
        L'@90 B@100 L@110 B'@120
        B'@130 L@140 B@150 L'@160 L'@170 B'@180 L@190 B@200
        L@210 B'@220 L'@230 B@240 L'@250 B'@260 L2@270 B@280
        L@290
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'auto'

    def test_reconstruction(self) -> None:
        """Test reconstruction."""
        self.assertEqual(
            str(self.solve.reconstruction),
            "U R2 U' F' L F' U' L' U' R U R2 U R U2 R' U R "
            "U R' U' R U' R' U2 R U",
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
            27.5,
        )

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('XXCross', 'step'),
            ('F2L', 'virtual'),
            ('F2L 3', 'substep'),
            ('F2L 4', 'substep'),
            ('OLL', 'step'),
            ('PLL', 'step'),
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

    def test_reconstruction_step_line(self) -> None:
        """Test reconstruction step line."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "U R2 U' F' L F' U' L'",
            "U' [slot-extract]R U R'[/slot-extract]",
            "R' U [slot-extended]R U2 R'[/slot-extended] U R",
            (
                "[pre-auf]U[/pre-auf] "
                "[sune-trigger]R' U' R U'[/sune-trigger] "
                "[slot-extended]R' U2 R[/slot-extended]"
            ),
            '[post-auf]U[/post-auf]',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
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
            "U R2 U' F' L F' U' L'",
            "U' R U R'",
            "R' U R U2 R' U R",
            "U R' U' R U' R' U2 R",
            'U',
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )

    def test_orientation_faces(self) -> None:
        """Test orientation faces."""
        self.solve.orientation = 'auto'

        self.assertEqual(
            self.solve.orientation_faces,
            'LU',
        )

    def test_reconstruction_f2l_slot_naming_lu(self) -> None:
        """Test reconstruction of F2L slot naming (LU)."""
        self.solve.orientation = 'LU'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos']
            for info in method_applied.summary
            if info['type'] != 'virtual' and (
                    'F2L ' in info['name']
                    or 'XXCross' in info['name']
            )
        ]

        self.assertEqual(
            pairs,
            [
                ['Back Left', 'Front Left'],
                ['Front Right'], ['Back Right'],
            ],
        )

    def test_reconstruction_f2l_slot_naming_ld(self) -> None:
        """Test reconstruction of F2L slot naming (LD)."""
        self.solve.orientation = 'LD'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos']
            for info in method_applied.summary
            if info['type'] != 'virtual' and (
                    'F2L ' in info['name']
                    or 'XXCross' in info['name']
            )
        ]

        self.assertEqual(
            pairs,
            [
                ['Back Right', 'Front Right'],
                ['Back Left'], ['Front Left'],
            ],
        )

    def test_reconstruction_f2l_slot_naming_lf(self) -> None:
        """Test reconstruction of F2L slot naming (LF)."""
        self.solve.orientation = 'LF'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos']
            for info in method_applied.summary
            if info['type'] != 'virtual' and (
                    'F2L ' in info['name']
                    or 'XXCross' in info['name']
            )
        ]

        self.assertEqual(
            pairs,
            [
                ['Front Left', 'Front Right'],
                ['Back Right'], ['Back Left'],
            ],
        )

    def test_reconstruction_f2l_slot_naming_lb(self) -> None:
        """Test reconstruction of F2L slot naming (LB)."""
        self.solve.orientation = 'LB'

        method_applied = get_method_applied(self.solve)
        pairs = [
            info['case_infos']
            for info in method_applied.summary
            if info['type'] != 'virtual' and (
                    'F2L ' in info['name']
                    or 'XXCross' in info['name']
            )
        ]

        self.assertEqual(
            pairs,
            [
                ['Back Left', 'Back Right'],
                ['Front Left'], ['Front Right'],
            ],
        )

    def test_reconstruction_f2l_case_consistency(self) -> None:
        """
        Test reconstruction of F2L cases detection consistency
        accross orientations.
        """
        orientations = ['LU', 'LD', 'LF', 'LB']

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
                    ['04', '34'],
                )

            del self.solve.method_applied
            del self.solve.orientation_faces
            del self.solve.orientation_moves
