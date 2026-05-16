"""Tests for interface scrambler."""
import unittest
from unittest.mock import Mock

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.invert import invert_moves
from cubing_algs.vcube import VCube

from term_timer.interface.cube import Orienter
from term_timer.interface.scrambler import Scrambler


class MockScrambler(Scrambler):
    """Mock class for testing Scrambler mixin."""

    def __init__(self) -> None:
        """Initialize mock scrambler with empty reorient value."""
        self.reorient_return_value = parse_moves('')
        super().__init__()

    def reorient(self, _algorithm: Algorithm) -> Algorithm:
        """
        Return the configured reorient value for testing.

        Returns:
            The pre-configured reorient_return_value algorithm.

        """
        return self.reorient_return_value


class OrienterScrambler(Orienter, Scrambler):
    """Test class combining Orienter and Scrambler."""

    def __init__(self, orientation_faces: CubeOrientation) -> None:
        """Initialize with specified cube orientation."""
        super().__init__()
        self.orientation_faces = orientation_faces

    def clear_line(self, *, full: bool) -> None:
        """Fake clear_line."""

    def beep_scramble(self) -> None:
        """Fake beep_scramble."""


class TestComputeScrambleDisplayComplete(unittest.TestCase):
    """Tests for compute_scramble_display when scramble is complete."""

    def setUp(self) -> None:
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_complete_returns_completion_message(self) -> None:
        """Test complete returns completion message."""
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
        """Test complete with orientation moves still shows completion."""
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
        """Test complete with empty scramble."""
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
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_empty_scramble_no_orientation(self) -> None:
        """Test empty scramble no orientation."""
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
        """Test single move scramble."""
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

        expected_output = '[moves]R[/moves] '
        self.assertEqual(out, expected_output)
        self.assertTrue(full_clear)

    def test_two_moves_scramble_both_correct(self) -> None:
        """Test two moves scramble both correct."""
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

        expected_output = '[move]R[/move] [moves]U[/moves] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_orientation_moves_displayed(self) -> None:
        """Test orientation moves displayed."""
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
        self.assertTrue('[moves]R[/moves]' in out)


class TestComputeScrambleDisplayCorrectMoves(unittest.TestCase):
    """Tests for correct move styling."""

    def setUp(self) -> None:
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_all_correct_moves_styled_as_move(self) -> None:
        """Test all correct moves styled as move."""
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
            "[move]R[/move] [move]U[/move] [move]R'[/move] [moves]U'[/moves] "
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_first_two_correct_of_three(self) -> None:
        """Test first two correct of three."""
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

        expected_output = '[move]R[/move] [moves]U[/moves] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)


class TestComputeScrambleDisplayCautionStyling(unittest.TestCase):
    """Tests for caution styling (same face, wrong direction/amount)."""

    def setUp(self) -> None:
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_same_face_wrong_direction_styled_as_caution(self) -> None:
        """Test same face wrong direction styled as caution."""
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
        """Test same face wrong amount styled as caution."""
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
        """Test first correct second caution."""
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
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_wrong_face_styled_as_warning(self) -> None:
        """Test wrong face styled as warning."""
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
        """Test first correct second wrong face."""
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
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_once_off_track_all_subsequent_warning(self) -> None:
        """Test once off track all subsequent warning."""
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
        """Test once off track same face later is warning."""
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
        """Test first wrong direction triggers off track."""
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
        """Test long sequence off track after first error."""
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
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_full_clear_true_when_algo_length_less_than_previous(
        self,
    ) -> None:
        """Test full clear true when algo length less than previous."""
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
        """Test full clear true when algo length equals one."""
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
        """Test full clear true when algo empty."""
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
        """Test full clear false when algo length equals previous."""
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
        """Test full clear false when algo length greater than previous."""
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
        """Test setup."""
        self.scrambler = MockScrambler()

    def test_very_long_scramble(self) -> None:
        """Test very long scramble."""
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
        """Test scramble with double moves."""
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

        expected_output = '[move]R2[/move] [moves]U2[/moves] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_scramble_with_wide_moves(self) -> None:
        """Test scramble with wide moves."""
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

        expected_output = '[move]Rw[/move] [moves]Uw[/moves] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_scramble_with_slice_moves(self) -> None:
        """Test scramble with slice moves."""
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

        expected_output = '[move]M[/move] [move]E[/move] [moves]S[/moves] '
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_reorient_transforms_algorithm(self) -> None:
        """Test reorient transforms algorithm."""
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
            '[move]F[/move] [moves]R[/moves] '
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_mixed_correct_caution_warning(self) -> None:
        """Test mixed correct caution warning."""
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
        """Test all moves same face wrong direction."""
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
        """Test orientation moves with complex algorithm."""
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
        """Test setup."""
        self.scrambler = OrienterScrambler('DF')

    def test_index_error_issue_1(self) -> None:
        """Test index error issue 1."""
        scrambled = parse_moves(
            "F@3959546374 L@3959546735 D@3959547335 L'@3959547724 "
            "D@3959549974 y@3959550034 "
            "F'@3959551534 D'@3959551895 "
            "F@3959552855 D'@3959553245 F'@3959555076",
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
            "[moves]R'[/moves] "
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_index_error_issue_2(self) -> None:
        """Test index error issue 2."""
        scrambled = parse_moves(
            "B'@3959864761 L'@3959865782 D'@3959866892 "
            "L@3959867522 D'@3959868602 y'@3959868663 "
            "B@3959869892 D@3959870612 B'@3959871483 "
            "D@3959872292 B@3959873012",
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
            "[moves]R[/moves] "
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)

    def test_index_error_issue_3(self) -> None:
        """Test index error issue 3. Real overflow."""
        scrambled = parse_moves(
            "F@3959546374 L@3959546735 D@3959547335 L'@3959547724 "
            "D@3959549974 y@3959550034 "
            "F'@3959551534 D'@3959551895 "
            "F@3959552855 D'@3959553245 F'@3959555076 "
            "B@3959555076",
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
            "[warning]L[/warning] "
        )
        self.assertEqual(out, expected_output)
        self.assertFalse(full_clear)


class TestScrambleCompletionVerification(unittest.TestCase):
    """Tests verifying is_complete using handle_scrambled method."""

    def check_completion(self, scrambled: Algorithm,
                         scramble_oriented: Algorithm) -> None:
        """Check completion is detected."""
        cube = VCube(size=3)
        cube.rotate('z2' + scramble_oriented)
        orientations = Algorithm()

        # Create scrambler with mocked dependencies
        scrambler = OrienterScrambler('DF')
        scrambler.bluetooth_cube = VCube(size=3)
        scrambler.facelets_scrambled = cube.state
        scrambler.scramble_oriented = scramble_oriented
        scrambler.console = Mock()

        # Apply each move via handle_scrambled
        # Also update bluetooth_cube to simulate physical cube state changes
        for move in scrambled:
            move_untimed = move.untimed
            if move.is_rotation_move:
                orientations.append(move_untimed)
                scrambler.bluetooth_cube.rotate(move_untimed)
            elif orientations:
                # Convert moves for bluetooth cube when orientations
                # because bluetooth cube does not rotate itself, it stay in UF.
                oriented_moves = invert_moves(orientations) + move_untimed
                move_desoriented = oriented_moves.transform(
                    degrip_full_moves,
                )[0]
                scrambler.bluetooth_cube.rotate(move_desoriented)
            else:
                scrambler.bluetooth_cube.rotate(move_untimed)

            scrambler.handle_scrambled(move)

        self.assertTrue(
            scrambler.scramble_completed_event.is_set(),
            'scramble_completed_event should be set after all moves',
        )

    def test_handle_scrambled_completion_issue_1(self) -> None:
        """
        Verify scramble completes using handle_scrambled method.

        Tests issue 1 scramble sequence.
        """
        scrambled = parse_moves(
            "F@3959546374 L@3959546735 D@3959547335 L'@3959547724 "
            "D@3959549974 y@3959550034 "
            "F'@3959551534 D'@3959551895 "
            "F@3959552855 D'@3959553245 F'@3959555076",
        )
        scramble_oriented = parse_moves("F R U R' d R' U' R U' R'")

        cube = VCube(size=3)
        cube.rotate('z2' + scramble_oriented)

        self.check_completion(scrambled, scramble_oriented)

    def test_handle_scrambled_completion_issue_2(self) -> None:
        """
        Verify scramble completes using handle_scrambled method.

        Tests issue 2 scramble sequence.
        """
        scrambled = parse_moves(
            "B'@3959864761 L'@3959865782 D'@3959866892 "
            "L@3959867522 D'@3959868602 y'@3959868663 "
            "B@3959869892 D@3959870612 B'@3959871483 "
            "D@3959872292 B@3959873012",
        )
        scramble_oriented = parse_moves("B' R' U' R d' R U R' U R")

        self.check_completion(scrambled, scramble_oriented)

    def test_handle_scrambled_completion_issue_3(self) -> None:
        """
        Verify scramble completes using handle_scrambled method.

        Tests issue 3 scramble sequence with multiple rotations.
        """
        scrambled = parse_moves(
            "B@3973238994 z@3973239144 "
            "B'@3973241724 D'@3973242744 R'@3973245384 D@3973246854 "
            "R'@3973248893 y'@3973249044 B@3973250453 R@3973251444 "
            "B'@3973252404 R@3973253124 B@3973254685",
        )

        scramble_oriented = parse_moves("f B' R' U' R d' R U R' U R")

        self.check_completion(scrambled, scramble_oriented)
