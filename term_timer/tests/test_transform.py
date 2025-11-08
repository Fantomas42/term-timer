"""Tests for transform."""

import unittest

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.mirror import mirror_moves
from cubing_algs.transform.translate import translate_moves
from cubing_algs.vcube import VCube

from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves


class TransformReorientTestCase(unittest.TestCase):
    # Keep for reference

    def test_reorient_moves_with_orientation(self) -> None:
        orientation = parse_moves('x y')
        algorithm = parse_moves("R U R'")
        expect = parse_moves("F R F'")

        result = translate_moves(orientation)(algorithm)

        self.assertEqual(result, expect)

    def test_reorient_moves_without_orientation(self) -> None:
        orientation = parse_moves('')
        algorithm = parse_moves("R U R'")

        result = translate_moves(orientation)(algorithm)

        self.assertEqual(result, algorithm)

    def test_reorient_issue_simple(self) -> None:
        scramble = parse_moves("R U R' U'")
        solution = scramble.transform(mirror_moves)

        cube = VCube()
        cube.rotate(scramble)
        cube.rotate(solution)
        self.assertTrue(cube.is_solved)

        solution_z2 = translate_moves(
            parse_moves('z2'),
        )(solution)

        cube = VCube()
        cube.rotate(scramble)
        cube.rotate('z2')
        cube.rotate(solution_z2)
        self.assertTrue(cube.is_solved)

        solution_y = translate_moves(
            parse_moves('y'),
        )(solution)

        cube = VCube()
        cube.rotate(scramble)
        cube.rotate('y')
        cube.rotate(solution_y)
        self.assertTrue(cube.is_solved)

        solution_xyprime = translate_moves(
            parse_moves("x y'"),
        )(solution)

        cube = VCube()
        cube.rotate(scramble)
        cube.rotate("x y'")
        cube.rotate(solution_xyprime)
        self.assertTrue(cube.is_solved)

    def test_reorient_issue_without_inverse(self) -> None:
        scramble = parse_moves(
            "F R' F' U' D2 B' L F U' F "
            "L' U F2 U' F2 B2 L2 D2 B2 D' L2",
        )
        solution = parse_moves(
            "L B' F' U L' D2 B2 U B' D' "
            "B D' B' D B L D' L' D D' B "
            "D B' D B D' B' D' F D' F' "
            "D R' D R D2 D F' D' F D' F' "
            "D F D D2 D2 F D2 F' D2 F' R "
            "F R' L' R D' F' D F D R' D' "
            "L D2 F' D2 F D2 F' R F D F' "
            "D' F' R' F2 D2 D'",
        )
        cube = VCube()
        cube.rotate(scramble)
        cube.rotate(solution)
        self.assertTrue(cube.is_solved)

        solution_z2 = translate_moves(
            parse_moves('z2'),
        )(solution)

        cube = VCube()
        cube.rotate(scramble)
        cube.rotate('z2')
        cube.rotate(solution_z2)
        self.assertTrue(cube.is_solved)

        solution_y = translate_moves(
            parse_moves('y'),
        )(solution)

        cube = VCube()
        cube.rotate(scramble)
        cube.rotate('y')
        cube.rotate(solution_y)
        self.assertTrue(cube.is_solved)

        solution_xyprime = translate_moves(
            parse_moves("x y'"),
        )(solution)

        cube = VCube()
        cube.rotate(scramble)
        cube.rotate("x y'")
        cube.rotate(solution_xyprime)
        self.assertTrue(cube.is_solved)


class TransformSliceTestCase(unittest.TestCase):

    def test_reslice_moves_issue_01(self) -> None:
        provide = parse_moves("B' F B' F U L R' R' L D' L' R U D' D' U R L' U")
        expect = parse_moves("S2 D M2 D' M' S2 M U")

        result = prettify_moves(
            humanize_moves(provide),
        )

        self.assertEqual(
            result,
            expect,
        )


class TransformPrettiyTestCase(unittest.TestCase):

    def test_prettify_moves_with_double_moves(self) -> None:
        algorithm = parse_moves('R R U U')
        expect = parse_moves('R2 U2')

        result = prettify_moves(algorithm)

        self.assertEqual(result, expect)


class TransformHumanizeTestCase(unittest.TestCase):

    def test_humanize_moves_with_rotation_at_end(self) -> None:
        algorithm = parse_moves("R U R' y")

        result = humanize_moves(algorithm)

        # Should return original if ends with rotation
        self.assertEqual(result, algorithm)

    def test_humanize_moves_with_rotation_at_end_wide(self) -> None:
        algorithm = parse_moves("R U R' x")
        expect = parse_moves("R U l'")

        result = humanize_moves(algorithm)

        self.assertEqual(result, expect)

    def test_humanize_moves_empty_algorithm(self) -> None:
        algorithm = parse_moves('')

        result = humanize_moves(algorithm)

        self.assertEqual(algorithm, result)

    def test_humanize_moves_issue_01(self) -> None:
        provide = parse_moves(
            "R'@23249 L@23279 "
            "R'@23520 L@23520 "
            "U@23789 "
            "B@24060 F'@24060 "
            "F'@24300 B@24301 "
            "D'@24809 "
            "B'@25499 F@25529 "
            "U@26309 D'@26311 "
            "D'@26639 U@26640 "
            "F@27089 B'@27090",
        )

        expect = parse_moves("M2 D S2 D' S M2 S'")

        result = prettify_moves(
            humanize_moves(provide),
        )

        self.assertEqual(
            result,
            expect,
        )
