"""Tests for solve with XCross."""
import unittest

from term_timer.solve import Solve
from term_timer.tests.utils import get_method_applied


class TestSolveXCross(unittest.TestCase):
    """Test Solve with XCross for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1739130391
        self.time = 31932000000
        self.scramble = """
        D L2 D' B2 L2 B2 U2 B2 D R2 U R2 B' U' R2 B2 L' B' F D2 L
        """
        self.solution = """
        F'@0 U@283 B'@853 B'@917 F'@4320 F'@4399 R@4576 F@4743 U@5484 D@8402
        B@8609 D'@8918 B'@9117 D@9369 D@9625 F'@9907 D@10124 F@10251 D'@12240
        F@12592 D@12735 F'@12810 D@13114 D@13356 F@13525 D'@13590 F'@13789
        D'@14152 D'@14377 L@15020 L@15111 L'@15195 D@15514 L@15635 L@16320
        D'@16422 L'@16523 D'@17057 D'@17295 B@18042 D'@18147 B'@18230 D@18475
        B'@18766 D'@18931 B@19001 B@20649 D@20804 D@21099 B'@21248 D'@21383
        D'@21614 B@21713 D@21796 B'@21848 D'@22890 B@23295 D'@23442 D'@23653
        B@23873 B@23927 D'@24427 B@24763 B@24842 D'@25374 B@26109 B@26182
        D'@26365 D'@26611 B@26802 D'@28094 D'@29985 B@30322 D@30415 B'@30491
        L'@30747 B@30912 D@31033 B'@31100 D'@31214 B'@31402 L@31486 B@31638
        B@31702 D'@31766 B'@31932
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'auto'

    def test_summary(self) -> None:
        """Test summary."""
        method_applied = get_method_applied(self.solve)
        inputs = method_applied.summary
        outputs = [
            ('XCross', 'step'),
            ('F2L', 'virtual'),
            ('F2L 2', 'substep'),
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

    def test_reconstruction_step_text(self) -> None:
        """Test reconstruction step text."""
        method_applied = get_method_applied(self.solve)
        inputs = [
            info
            for info in method_applied.summary
            if info['type'] != 'virtual'
        ]
        outputs = [
            "L' D R2 . L2 B L . D . U R U' R' U2 L' U L . "
            "U' L U L' U2 L U' L' U2 . F2",
            "F' U F . F U' F'",
            "U2 . R U' R' U R' U' R .",
            "R U2 R' U2 R U R' .",
            "U' R U2 R2 U' R2 U' . R2 U2 R .",
            "U' . U' R U R' F' R U R' U' R' F R2 U' R'",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            self.assertEqual(
                self.solve.reconstruction_step_text(source, multiple=False),
                expected,
            )


class TestSolveXXCross(unittest.TestCase):
    """Test Solve with XXCross for checking output."""

    maxDiff = None

    def setUp(self) -> None:
        """Test setup."""
        self.date = 1713907485
        self.time = 41206000000
        self.scramble = """
  U' B L2 F L F U D B R B2 L2 B2 R' F2 L' F2 L' B2 L'
        """
        self.solution = """
        B@0 U'@327 L@1295 D'@2015 F@2334 F@2424 U@3583 D'@4719 D@7229 F'@7825
        D@7953 D@8249 F@8459 D'@8689 F'@8841 D@8909 F@9092 D@10498 B@10893
        D'@11160 D'@11409 B'@11552 D@11740 B@11868 D'@11951 B'@12121 R@12934
        D@13026 R'@13107 D'@13218 D@14248 R@14732 D'@14954 D'@15197 R'@15365
        D@15513 R@15633 D'@15720 R'@15869 F@17120 D@17223 F'@17352 D'@17485
        F'@18117 R@18285 F@18516 D@19568 R@19722 D'@19829 R'@19948 D'@20884
        D@22189 R'@22481 D@22726 D@23033 R@23383 D'@23629 D'@23883 R'@24348
        D@24689 R@24982 D'@25714 F@26211 L@26406 D@26556 L'@26601 D'@26718
        F'@27357 D@28376 L@28971 L@29052 U@29307 L'@29494 D'@29687 D'@29937
        L@30217 U'@30569 L'@30676 D'@30810 D'@31021 L'@31178 R@35307 L'@35310
        L'@35588 R@35588 D@36351 B@36961 F'@36967 B@37286 F'@37287 U'@37576
        F'@38266 B@38301 D@38781 U'@38785 U'@39132 D@39141 B@39784 F'@39919
        D@40944 D@41206
        """

        self.solve = Solve(
            self.date,
            self.time,
            self.scramble,
            moves=self.solution,
        )

        self.solve.method_name = 'cf4op'
        self.solve.orientation = 'auto'

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
            with self.subTest(name=source['name']):
                self.assertEqual(
                    source['name'],
                    expected[0],
                )
                self.assertEqual(
                    source['type'],
                    expected[1],
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
            "L D' . B . U' R2 . D . U' . U R' U2 R U' R' U R . "
            "U L U2 L' U L U' L' . F",
            "U F' U' . U F U2 F' U F U' F' . R U R' U' R' F R . "
            "U F U' F' .",
            "U' . U F' U2 F U2 F' U F .",
            "U' R B U B' U' R' . U B2 D B' U2 B D' B' U2 B' .",
            "F B2 F . U L R' L R' D' R' L U D2 U L R' . U2",
        ]

        for source, expected in zip(inputs, outputs, strict=True):
            with self.subTest(name=source['name']):
                self.assertEqual(
                    self.solve.reconstruction_step_text(source, multiple=False),
                    expected,
                )
