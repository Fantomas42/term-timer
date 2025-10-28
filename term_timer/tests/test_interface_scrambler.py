import unittest

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves

from term_timer.interface.cube import Orienter
from term_timer.interface.scrambler import Scrambler


class MockScrambler(Scrambler):
    """Mock class for testing Scrambler mixin."""

    def __init__(self) -> None:
        self.reorient_return_value = parse_moves('')
        super().__init__()

    def reorient(self, _algorithm: Algorithm) -> Algorithm:
        return self.reorient_return_value


class OrienterScrambler(Orienter, Scrambler):

    def __init__(self, orientation_faces: str) -> None:
        self.orientation_faces = orientation_faces


class TestComputeScrambleDisplayComplete(unittest.TestCase):
    """Tests for compute_scramble_display when scramble is complete."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_complete_returns_completion_message(self) -> None:
        scrambled = parse_moves("R U R' U'")
        scramble_oriented = parse_moves("R U R' U'")
        cube_orientation_moves = parse_moves('')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=True,
        )

        expected_message = (
            '[result]Cube scrambled and ready to be solved ![/result] '
            '[consign]Start solving to launch the timer.[/consign]'
        )
        self.assertEqual(out, expected_message)
        self.assertTrue(full_clear)

    def test_complete_with_orientation_moves_still_shows_completion(
        self,
    ) -> None:
        scrambled = parse_moves("R U R' U'")
        scramble_oriented = parse_moves("R U R' U'")
        cube_orientation_moves = parse_moves('x y')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=True,
        )

        expected_message = (
            '[result]Cube scrambled and ready to be solved ![/result] '
            '[consign]Start solving to launch the timer.[/consign]'
        )
        self.assertEqual(out, expected_message)
        self.assertTrue(full_clear)

    def test_complete_with_empty_scramble(self) -> None:
        scrambled = parse_moves('')
        scramble_oriented = parse_moves('')
        cube_orientation_moves = parse_moves('')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=True,
        )

        expected_message = (
            '[result]Cube scrambled and ready to be solved ![/result] '
            '[consign]Start solving to launch the timer.[/consign]'
        )
        self.assertEqual(out, expected_message)
        self.assertTrue(full_clear)


class TestComputeScrambleDisplayIncomplete(unittest.TestCase):
    """Tests for compute_scramble_display when scramble is incomplete."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_empty_scramble_no_orientation(self) -> None:
        scrambled = parse_moves('')
        scramble_oriented = parse_moves('')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertEqual(out, '')
        self.assertTrue(full_clear)

    def test_single_move_scramble(self) -> None:
        scrambled = parse_moves('R')
        scramble_oriented = parse_moves('R')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]R[/move] '
        self.assertEqual(out, expected_output)
        self.assertTrue(full_clear)

    def test_two_moves_scramble_both_correct(self) -> None:
        scrambled = parse_moves('R U')
        scramble_oriented = parse_moves('R U')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]R[/move] [move]U[/move] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_orientation_moves_displayed(self) -> None:
        scrambled = parse_moves('R')
        scramble_oriented = parse_moves('R')
        cube_orientation_moves = parse_moves('x y')
        self.scrambler.reorient_return_value = parse_moves('R')

        out, _ = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertTrue(
            out.startswith(
                '[rotation_x]x[/rotation_x] [rotation_y]y[/rotation_y] ',
            ),
        )
        self.assertTrue('[move]R[/move]' in out)


class TestComputeScrambleDisplayCorrectMoves(unittest.TestCase):
    """Tests for correct move styling."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_all_correct_moves_styled_as_move(self) -> None:
        scrambled = parse_moves("R U R' U'")
        scramble_oriented = parse_moves("R U R' U'")
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves("R U R' U'")

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            "[move]R[/move] [move]U[/move] [move]R'[/move] [move]U'[/move] "
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_first_two_correct_of_three(self) -> None:
        scrambled = parse_moves('R U')
        scramble_oriented = parse_moves('R U F')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]R[/move] [move]U[/move] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)


class TestComputeScrambleDisplayCautionStyling(unittest.TestCase):
    """Tests for caution styling (same face, wrong direction/amount)."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_same_face_wrong_direction_styled_as_caution(self) -> None:
        scrambled = parse_moves('R')
        scramble_oriented = parse_moves("R'")
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[caution]R[/caution] '
        self.assertEqual(out, expected_output)
        self.assertTrue(full_clear)

    def test_same_face_wrong_amount_styled_as_caution(self) -> None:
        scrambled = parse_moves('R2')
        scramble_oriented = parse_moves('R')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R2')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[caution]R2[/caution] '
        self.assertEqual(out, expected_output)
        self.assertTrue(full_clear)

    def test_first_correct_second_caution(self) -> None:
        scrambled = parse_moves('R U')
        scramble_oriented = parse_moves("R U'")
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]R[/move] [caution]U[/caution] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)


class TestComputeScrambleDisplayWarningStyling(unittest.TestCase):
    """Tests for warning styling (completely wrong move)."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_wrong_face_styled_as_warning(self) -> None:
        scrambled = parse_moves('R')
        scramble_oriented = parse_moves('U')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[warning]R[/warning] '
        self.assertEqual(out, expected_output)
        self.assertTrue(full_clear)

    def test_first_correct_second_wrong_face(self) -> None:
        scrambled = parse_moves('R F')
        scramble_oriented = parse_moves('R U')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R F')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]R[/move] [warning]F[/warning] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)


class TestComputeScrambleDisplayOffTrackBehavior(unittest.TestCase):
    """Tests for off-track behavior (once wrong, all subsequent are wrong)."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_once_off_track_all_subsequent_warning(self) -> None:
        scrambled = parse_moves('R F U')
        scramble_oriented = parse_moves('R U D')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R F U')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            '[move]R[/move] [warning]F[/warning] [warning]U[/warning] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_once_off_track_same_face_later_is_warning(self) -> None:
        scrambled = parse_moves('R F D')
        scramble_oriented = parse_moves('R U D')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R F D')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            '[move]R[/move] [warning]F[/warning] [warning]D[/warning] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_first_wrong_direction_triggers_off_track(self) -> None:
        scrambled = parse_moves('R U F')
        scramble_oriented = parse_moves("R' U F")
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U F')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            '[caution]R[/caution] [warning]U[/warning] [warning]F[/warning] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_long_sequence_off_track_after_first_error(self) -> None:
        scrambled = parse_moves('R U F D L B')
        scramble_oriented = parse_moves('R L F D L B')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U F D L B')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            '[move]R[/move] '
            '[warning]U[/warning] '
            '[warning]F[/warning] '
            '[warning]D[/warning] '
            '[warning]L[/warning] '
            '[warning]B[/warning] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)


class TestComputeScrambleDisplayFullClearBehavior(unittest.TestCase):
    """Tests for full_clear flag behavior."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_full_clear_true_when_algo_length_less_than_previous(
        self,
    ) -> None:
        scrambled = parse_moves('R')
        scramble_oriented = parse_moves('R U')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R')

        _, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertTrue(full_clear)

    def test_full_clear_true_when_algo_length_equals_one(self) -> None:
        scrambled = parse_moves('R')
        scramble_oriented = parse_moves('R')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R')

        _, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertTrue(full_clear)

    def test_full_clear_true_when_algo_empty(self) -> None:
        scrambled = parse_moves('')
        scramble_oriented = parse_moves('')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('')

        _, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertTrue(full_clear)

    def test_full_clear_false_when_algo_length_equals_previous(
        self,
    ) -> None:
        scrambled = parse_moves('R U')
        scramble_oriented = parse_moves('R U')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U')

        _, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertFalse(full_clear)

    def test_full_clear_false_when_algo_length_greater_than_previous(
        self,
    ) -> None:
        scrambled = parse_moves('R U F')
        scramble_oriented = parse_moves('R U F')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U F')

        _, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertFalse(full_clear)


class TestComputeScrambleDisplayEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions."""

    def setUp(self) -> None:
        self.scrambler = MockScrambler()

    def test_very_long_scramble(self) -> None:
        long_scramble_str = (
            "R U R' U' F' R U R' U' R' F R2 U' R' U' R U R' F' R U R' U' F"
        )
        scrambled = parse_moves(long_scramble_str)
        scramble_oriented = parse_moves(long_scramble_str)
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves(long_scramble_str)

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertIn('[move]R[/move]', out)
        self.assertIn('[move]U[/move]', out)
        self.assertNotIn('[warning]', out)
        self.assertNotIn('[caution]', out)
        self.assertFalse(full_clear)

    def test_scramble_with_double_moves(self) -> None:
        scrambled = parse_moves('R2 U2')
        scramble_oriented = parse_moves('R2 U2')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R2 U2')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]R2[/move] [move]U2[/move] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_scramble_with_wide_moves(self) -> None:
        scrambled = parse_moves('Rw Uw')
        scramble_oriented = parse_moves('Rw Uw')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('Rw Uw')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]Rw[/move] [move]Uw[/move] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_scramble_with_slice_moves(self) -> None:
        scrambled = parse_moves('M E S')
        scramble_oriented = parse_moves('M E S')
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('M E S')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = '[move]M[/move] [move]E[/move] [move]S[/move] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_reorient_transforms_algorithm(self) -> None:
        scrambled = parse_moves('R U')
        scramble_oriented = parse_moves('F R')
        cube_orientation_moves = parse_moves('x y')
        self.scrambler.reorient_return_value = parse_moves('F R')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            '[rotation_x]x[/rotation_x] [rotation_y]y[/rotation_y] '
            '[move]F[/move] [move]R[/move] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_mixed_correct_caution_warning(self) -> None:
        scrambled = parse_moves("R U' F D")
        scramble_oriented = parse_moves("R U F' L")
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves("R U' F D")

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            '[move]R[/move] '
            "[caution]U'[/caution] "
            '[warning]F[/warning] '
            '[warning]D[/warning] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_all_moves_same_face_wrong_direction(self) -> None:
        scrambled = parse_moves('R U F')
        scramble_oriented = parse_moves("R' U' F'")
        cube_orientation_moves = parse_moves('')
        self.scrambler.reorient_return_value = parse_moves('R U F')

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        expected_output = (
            '[caution]R[/caution] [warning]U[/warning] [warning]F[/warning] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_orientation_moves_with_complex_algorithm(self) -> None:
        scrambled = parse_moves("R U R' U'")
        scramble_oriented = parse_moves("R U R' U'")
        cube_orientation_moves = parse_moves("x' y2")
        self.scrambler.reorient_return_value = parse_moves("R U R' U'")

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=cube_orientation_moves,
            is_complete=False,
        )

        self.assertTrue(
            out.startswith(
                "[rotation_x]x'[/rotation_x] [rotation_y]y2[/rotation_y] ",
            ),
        )
        self.assertIn('[move]R[/move]', out)
        self.assertIn('[move]U[/move]', out)
        self.assertFalse(full_clear)


class TestComputeDisplayRotationRealCases(unittest.TestCase):
    """Tests for rotations cases and conditions."""
    maxDiff = None

    def setUp(self) -> None:
        self.scrambler = OrienterScrambler('DF')

    def test_index_error_issue_1(self) -> None:
        scrambled = parse_moves(
            "F@2568664285 L@2568665426 D@2568665936 L'@2568666625 "
            "D@2568668965 y@2568669776 F'@2568688166 "
            "D'@2568688827 F@2568689307 D'@2568689726 F'@2568690476",
        )
        scramble_oriented = parse_moves("F R U R' d R' U' R U' R'")

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=parse_moves('z2'),
            is_complete=False,
        )

        expected_output = (
            "[rotation_z]z2[/rotation_z] "
            "[move]F[/move] "
            "[move]R[/move] "
            "[move]U[/move] "
            "[move]R'[/move] "
            "[move]d[/move] "
            "[move]R'[/move] "
            "[move]U'[/move] "
            "[move]R[/move] "
            "[move]U'[/move] "
            "[move]R'[/move] "
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_index_error_issue_2(self) -> None:
        scrambled = parse_moves(
            "B'@2600539431 L'@2600543301 D'@2600543961 "
            "L@2600544621 D'@2600546391 y'@2600546840 "
            "B@2600550230 D@2600551700 B'@2600552240 "
            "D@2600552840 B@2600553530",
        )
        scramble_oriented = parse_moves("B' R' U' R d' R U R' U R")

        out, full_clear = self.scrambler.compute_scramble_display(
            scrambled=scrambled,
            scramble_oriented=scramble_oriented,
            cube_orientation_moves=parse_moves('z2'),
            is_complete=False,
        )

        expected_output = (
            "[rotation_z]z2[/rotation_z] "
            "[move]B'[/move] "
            "[move]R'[/move] "
            "[move]U'[/move] "
            "[move]R[/move] "
            "[move]d'[/move] "
            "[move]R[/move] "
            "[move]U[/move] "
            "[move]R'[/move] "
            "[move]U[/move] "
            "[move]R[/move] "
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)
