"""Tests for interface gesture."""
import unittest
from typing import override

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.move import Move
from cubing_algs.transform.timing import untime_moves

from term_timer.interface.cube import Orienter
from term_timer.interface.gesture import Gesture

MOVE_INTERVAL = 400


class MockGesture(Gesture):
    """Mock class for testing Gesture mixin."""

    @override
    def reorient(self, algorithm: Algorithm) -> Algorithm:
        """
        Return the algorithm untouched.

        Returns:
            The algorithm, as sent by a cube in default orientation.

        """
        return algorithm


class OrienterGesture(Orienter, Gesture):
    """Test class combining Orienter and Gesture."""

    def __init__(self, orientation_faces: CubeOrientation) -> None:
        """Initialize with specified cube orientation."""
        super().__init__()
        self.orientation_faces = orientation_faces


class BaseGestureTestCase(unittest.TestCase):
    """Base test case feeding moves one by one, as the cube does."""

    def setUp(self) -> None:
        """Test setup."""
        self.gesture: Gesture = MockGesture()
        self.clock = 1000

    def feed_moves(
            self,
            moves: str,
            interval: int = MOVE_INTERVAL,
    ) -> None:
        """Feed each move separately, timed and spaced by interval."""
        for move in moves.split():
            self.gesture.handle_save_gestures(
                Move(f'{ move }@{ self.clock }'),
            )
            self.clock += interval


class TestSaveGestureNotDetected(BaseGestureTestCase):
    """Tests for move sequences that must not trigger a save gesture."""

    def test_no_move(self) -> None:
        """Test no move at all."""
        self.assertFalse(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, '')

    def test_single_move(self) -> None:
        """Test a lonely move."""
        self.feed_moves('U')

        self.assertFalse(self.gesture.save_gesture_event.is_set())

    def test_different_faces(self) -> None:
        """Test two moves on different faces."""
        self.feed_moves('R U')

        self.assertFalse(self.gesture.save_gesture_event.is_set())

    def test_same_move_twice(self) -> None:
        """Test the same move repeated, which undoes nothing."""
        self.feed_moves('U U')

        self.assertFalse(self.gesture.save_gesture_event.is_set())

    def test_solution_moves(self) -> None:
        """Test a regular algorithm without any undone move."""
        self.feed_moves("R U R' U' R' F R2 U' R' U' R U R' F'")

        self.assertFalse(self.gesture.save_gesture_event.is_set())

    def test_rotations(self) -> None:
        """Test rotations, which are not mapped to any command."""
        self.feed_moves("x x'")

        self.assertFalse(self.gesture.save_gesture_event.is_set())

        self.feed_moves("y y'")

        self.assertFalse(self.gesture.save_gesture_event.is_set())


class TestSaveGestureCommands(BaseGestureTestCase):
    """Tests for the command each undone face maps to."""

    def test_outer_faces_save_and_continue(self) -> None:
        """Test outer faces answering with the default command."""
        for moves in ("F F'", "R R'", "U U'", "B B'", "L L'"):
            with self.subTest(moves=moves):
                self.gesture = MockGesture()

                self.feed_moves(moves)

                self.assertTrue(self.gesture.save_gesture_event.is_set())
                self.assertEqual(self.gesture.save_gesture, '')

    def test_down_face_saves_and_quits(self) -> None:
        """Test the down face answering with the quit command."""
        self.feed_moves("D D'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')

    def test_middle_slices_zap(self) -> None:
        """Test the M and S slices answering with the zap command."""
        for moves in ("M M'", "S S'"):
            with self.subTest(moves=moves):
                self.gesture = MockGesture()

                self.feed_moves(moves)

                self.assertTrue(self.gesture.save_gesture_event.is_set())
                self.assertEqual(self.gesture.save_gesture, 'z')

    def test_equator_slice_keeps(self) -> None:
        """Test the E slice answering with the keep command."""
        self.feed_moves("E E'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'k')

    def test_inverted_order(self) -> None:
        """Test a gesture started by the counter clockwise move."""
        self.feed_moves("D' D")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')

    def test_wide_moves(self) -> None:
        """Test wide moves, resolved as their outer face."""
        self.feed_moves("u u'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, '')


class TestSaveGestureSequences(BaseGestureTestCase):
    """Tests for gestures surrounded by other moves."""

    def test_repeated_move_then_undone(self) -> None:
        """Test the same move done twice before being undone once."""
        self.feed_moves("U U U'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, '')

    def test_repeated_move_then_undone_quits(self) -> None:
        """Test that repeating a move does not lose the command."""
        self.feed_moves("D D D'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')

    def test_gesture_after_solution_moves(self) -> None:
        """Test a gesture made after unrelated moves."""
        self.feed_moves("R U R' U' D D'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')

    def test_only_last_two_moves_matter(self) -> None:
        """Test that an earlier gesture is replaced by the last one."""
        self.feed_moves("U U'")

        self.assertEqual(self.gesture.save_gesture, '')

        self.gesture.save_gesture_event.clear()
        self.feed_moves("D D'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')

    def test_moves_are_accumulated(self) -> None:
        """Test that every move received is kept."""
        self.feed_moves("R U U'")

        self.assertEqual(len(self.gesture.save_moves), 3)

    def test_fast_gesture(self) -> None:
        """Test a gesture made with tightly timed moves."""
        self.feed_moves("D D'", interval=50)

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')


class TestSaveGestureOrientation(BaseGestureTestCase):
    """Tests for gestures made on a reoriented cube."""

    def test_default_orientation(self) -> None:
        """Test that an upright cube maps the faces as they are."""
        self.gesture = OrienterGesture('UF')

        self.feed_moves("D D'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')

    def test_upside_down_cube_quits_on_up_face(self) -> None:
        """Test that a flipped cube quits on the physical up face."""
        self.gesture = OrienterGesture('DF')

        self.feed_moves("U U'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, 'q')

    def test_upside_down_cube_continues_on_down_face(self) -> None:
        """Test that a flipped cube saves on the physical down face."""
        self.gesture = OrienterGesture('DF')

        self.feed_moves("D D'")

        self.assertTrue(self.gesture.save_gesture_event.is_set())
        self.assertEqual(self.gesture.save_gesture, '')

    def test_reoriented_moves_are_stored(self) -> None:
        """Test that the moves are stored once reoriented."""
        self.gesture = OrienterGesture('DF')

        self.feed_moves("U U'")

        self.assertEqual(
            self.gesture.save_moves.transform(untime_moves),
            Algorithm.parse_moves("D D'"),
        )
