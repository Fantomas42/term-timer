"""Tests for solve 500."""
import unittest
from typing import cast

from term_timer.methods.base import Analyser
from term_timer.solve import Solve


def get_method_applied(solve: Solve) -> Analyser:
    """
    Get method_applied, asserting it's not None in tests.

    Returns:
        The method_applied Analyser instance.

    """
    return cast('Analyser', solve.method_applied)


class TestSolve500(unittest.TestCase):
    """Tests for solve 500 reconstruction and analysis."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1751576007
        self.time = 27357994593
        self.scramble = "F R' F' U' D2 B' L F U' F L' U F2 U' F2 B2 L2 D2 B2 D' L2"  # noqa: E501
        self.solution = """
        L@0 B'@622 F'@1483 U@2055 L'@2614 D@4254 D@4539 B@4921 B@5174 U@5492 B'@8661 D'@8955 B@9252 D'@9480 B'@9799 D@9947 B@10318 L@12356 D'@12503 L'@12637 D@12944 D'@13266 B@13741 D@14043 B'@14234 D@14432 B@14749 D'@14951 B'@15258 D'@16896 F@17219 D'@17523 F'@17658 D@18532 R'@18749 D@18899 R@19230 D@20016 D@20977 D@21255 F'@21658 D'@21844 F@22011 D'@22135 F'@22292 D@22434 F@22549 D@23205 D'@24988 D'@25196 D'@25817 D'@26023 F@27326 D@27632 D@27939 F'@28101 D@28528 D@28784 F'@29019 R@29239 F@29372 R'@29694 L'@31253 R@31253 D'@31880 F'@32042 D@32131 F@32241 D@32474 R'@32690 D'@32929 L@33343 D'@34918 D'@35140 F'@35607 D@35793 D@36046 F@36150 D'@36275 D'@36481 F'@36752 R@37060 F@37203 D@37383 F'@37460 D'@37564 F'@37919 R'@38221 F@38392 F@38462 D'@38697 D'@38969 D'@39196
        """  # noqa: E501

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'auto'

    def test_orientation_faces(self) -> None:
        """Test orientation faces."""
        self.assertEqual(
            self.solve.orientation_faces,
            'DR',
        )

    def test_reconstruction(self) -> None:
        """Test reconstruction."""
        self.assertEqual(
            str(self.solve.reconstruction),
            "B L' R' D B' U2 L2 D L' U' L U' L' U L B U' B' U U' L U L' U L U' L' U' R U' R' U F' U F U2 U R' U' R U' R' U R U U2 U2 R U2 R' U2 R' F R F' B' F U' R' U R U F' U' B U2 R' U2 R U2 R' F R U R' U' R' F' R2 U2 U'",  # noqa: E501
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
            "B L' . R' D B' . U2 L2 D .",

            "L' U' L U' L' U L .",

            "B U' B' U U' L U L' U L U' L' .",

            "U' R U' R' . U F' U F .",

            "U . U2 R' U' R U' R' U R .",

            "U . U2 U2 . R U2 R' U2 R' F R f' . L' U' L U L F' L' f .",

            "U2 R' U2 R U2 R' F R U R' U' R' F' R2 U2 U'",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )

    def test_reconstruction_f2l_slot_naming_auto(self) -> None:
        """Test reconstruction of F2L slot naming (DR)."""
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
