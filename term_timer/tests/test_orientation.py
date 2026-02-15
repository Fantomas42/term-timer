"""Tests for orientation."""
import unittest

from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import remove_ending_rotations

from term_timer.orientation import get_orientation_faces


class TestAutoRotation(unittest.TestCase):
    """Tests for automatic orientation detection."""

    def test_solve_500(self) -> None:
        """Test solve 500."""
        scramble = Algorithm.parse_moves(
            "F R' F' U' D2 B' L F U' F L' U F2 U' F2 B2 L2 D2 B2 D' L2",
        )
        solution = Algorithm.parse_moves(
            """
            L B' F' U L' D2 B2 U
            B' D' B D' B' D B
            L D' L' D D' B D B' D B D' B'
            D' F D' F' D R' D R
            D D2 F' D' F D' F' D F
            D D2 D2 F D2 F' D2 F' R F r' B' D' B D B R' B' r
            D2 F' D2 F D2 F' R F D F' D' F' R' F2 D2 D'
            """,
        )

        self.assertEqual(
            get_orientation_faces(scramble, solution),
            'DR',
        )

    def test_solve_501(self) -> None:
        """Test solve 501."""
        scramble = Algorithm.parse_moves(
            "U F2 L' D' R2 B R F L' D2 F U2 D' F2 R2 U' B2 R2 U' D2 R2 F2",
        )
        solution = Algorithm.parse_moves(
            """
            F R L B' D F2 U'
            D' B D B' D D F' D' F
            B D B' D' B D B' D' B' D B D2 B' D2 B D' B' D B
            D' F D' F' D L' D L D2 L' D2 L D' L' D L
            D2 R' D R D2 R' D2 R D' R' D R
            D2 D' D2 D R' D2 R D R' D R F' R' D' R D F
            L D L' F' L D L' D' L' F L2 D' L'
            """,
        )

        self.assertEqual(
            get_orientation_faces(scramble, solution),
            'DL',
        )

    def test_solve_roux(self) -> None:
        """Test solve roux."""
        scramble = Algorithm.parse_moves(
            "B L2 B D2 B2 U L2 D2 R U L R2 D R D U2 L' U2",
        )
        solution = Algorithm.parse_moves(
            """
            y' x // inspection
            R' U' r' // 1x2x2
            z' U' M2' U' x // 1x2x3
            M2' U' R2 U2 r' // 1x2x2
            U' M' U R' U2 R // 1x2x3
            R' U' R U' R' U2 R // CLL
            U' M U M' U2 M U' M' // EO
            U M U2 M' U' // UL/UR
            M' U2 M U2 // EP
            // from http://cubesolv.es/solve/1519
            """,
        ).transform(
            degrip_full_moves,
            remove_ending_rotations,
        )

        self.assertEqual(
            get_orientation_faces(scramble, solution),
            'LD',
        )

    def test_solve_wr(self) -> None:
        """Test solve wr."""
        scramble = Algorithm.parse_moves(
            "F U2 L2 B2 F' U L2 U R2 D2 L' B L2 B' R2 U2",
        )
        solution = Algorithm.parse_moves(
            """
            y x' // inspection
            U R2 U' F' L F' U' L' // XX-Cross + EO
            U' R U R' // 3rd slot
            R' U R U2' R' U R // 4th slot
            U R' U' R U' R' U2 R // OLL / ZBLL
            U // AUF
            // from http://cubesolv.es/solve/5757
            """,
        ).transform(
            degrip_full_moves,
            remove_ending_rotations,
        )

        self.assertEqual(
            get_orientation_faces(scramble, solution),
            'LU',
        )


class TestOrientationDetection(unittest.TestCase):
    """
    Tests for orientation detection with first layer validation.

    The algorithm detects orientation when a face is completed AND
    the first layer is valid (top row of adjacent faces match).
    This ensures proper CFOP orientation detection.
    """

    def test_solve_40_first_two_layers_validation(self) -> None:
        """
        Test solve 40 - Face B complete but first layer invalid.

        Face B becomes complete at move 64, but first layer is NOT valid.
        Algorithm continues and detects valid first layer with D-top.
        """
        scramble = Algorithm.parse_moves(
            "B2 L2 B2 L2 U' F2 U2 F2 R2 F' L2 B' U R' B2 R B R2 U' R'",
        )
        solution = Algorithm.parse_moves(
            """
            L' L' R' F' B R' B' U R U U D' D D L' D' L B B' D' B D B'
            L' D' L D D' D' B' D B B D B' D' B D' B' R' D' R D' D' D'
            B D' D' B' L' D D L D' L' D L F' D F D' D' F' D F D L D L'
            D' L' F L F' D' L' D D L D' D' L' F L D L' D' L' F' L L
            """,
        )

        result = get_orientation_faces(scramble, solution)

        self.assertEqual(
            result,
            'DL',
            f"Expected 'DL' but got '{result}'. "
            "Face B completes early but first layer invalid, "
            "should continue to find valid D-top orientation.",
        )

    def test_solve_144_first_two_layers_validation(self) -> None:
        """
        Test solve 144 - Face B complete but first layer invalid.

        Face B completes at move 40 without valid first layer.
        Algorithm waits for valid first layer with D-top.
        """
        scramble = Algorithm.parse_moves(
            "F' L2 F U L D' F2 R U' B2 R' U' F' D' R F U2 L U' L B L' "
            "D2 F' L D2",
        )
        solution = Algorithm.parse_moves(
            """
            R F' R' D L L U' U' F' D D F D' F' D F L' D D L D F D F'
            D' D B' D' B D' B' D B D' L' D' L D' B D B' D D R' D' B' D
            B R B D B' L L U' F D' F' D F' U L L D'
            """,
        )

        result = get_orientation_faces(scramble, solution)

        self.assertEqual(
            result,
            'DL',
            f"Expected 'DL' but got '{result}'. "
            "Face B complete at move 40 but first layer invalid.",
        )

    def test_solve_174_first_two_layers_validation(self) -> None:
        """
        Test solve 174 - Face B complete but first layer invalid.

        Face B completes at move 45 without valid first layer.
        Algorithm waits for valid first layer with D-top.
        """
        scramble = Algorithm.parse_moves(
            "D U2 L2 F2 R2 B2 U' B2 F2 U2 L B D' R B D' L2 R2 D2 F' L2",
        )
        solution = Algorithm.parse_moves(
            """
            U B' D' D' R R D' L L U U D L D' D' L' D L D' L' R D' R'
            D' B D D B' D B D' B' D' R' D' R D' R D R' D F D' F' D' D'
            B' D B D' D' D' R' B R B' D' B' D B D R' D' B' R D R' D' R'
            B R R D' R' D' R D R' D R D' D D
            """,
        )

        result = get_orientation_faces(scramble, solution)

        self.assertEqual(
            result,
            'DB',
            f"Expected 'DB' but got '{result}'. "
            "Face B complete at move 45 but first layer invalid.",
        )
