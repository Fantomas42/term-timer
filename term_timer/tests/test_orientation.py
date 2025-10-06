import unittest

from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import remove_final_rotations

from term_timer.orientation import auto_orientation


class TestAutoRotation(unittest.TestCase):

    def test_solve_500(self) -> None:
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
            auto_orientation(scramble, solution),
            'DR',
        )

    def test_solve_501(self) -> None:
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
            auto_orientation(scramble, solution),
            'DL',
        )

    def test_solve_roux(self) -> None:
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
            remove_final_rotations,
        )

        self.assertEqual(
            auto_orientation(scramble, solution),
            'LD',
        )

    def test_solve_wr(self) -> None:
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
            remove_final_rotations,
        )

        self.assertEqual(
            auto_orientation(scramble, solution),
            'LU',
        )
