import unittest

from term_timer.scrambler import is_valid_next_move


class TestScrambler(unittest.TestCase):
    def test_is_valid_next_move_valid(self):
        """Test that valid next moves are recognized."""
        # Different faces are valid
        self.assertTrue(is_valid_next_move('F', 'R'))
        self.assertTrue(is_valid_next_move("F'", 'R'))
        self.assertTrue(is_valid_next_move('F2', "R'"))

    def test_is_valid_next_move_invalid_same_face(self):
        """Test that moves on the same face are invalid."""
        # Same face moves are invalid
        self.assertFalse(is_valid_next_move('F', 'F'))
        self.assertFalse(is_valid_next_move('F', "F'"))
        self.assertFalse(is_valid_next_move('F2', 'F'))

    def test_is_valid_next_move_invalid_opposite_faces(self):
        """Test that moves on opposite faces are invalid."""
        # Opposite face moves are invalid
        self.assertFalse(is_valid_next_move('F', 'B'))
        self.assertFalse(is_valid_next_move('R', 'L'))
        self.assertFalse(is_valid_next_move('U', 'D'))

    def test_is_valid_next_move_with_modifiers(self):
        """Test that modifiers don't affect face validation."""
        # Wide moves on same face
        self.assertFalse(is_valid_next_move('Fw', 'F'))

        # Wide moves on opposite faces
        self.assertFalse(is_valid_next_move('Fw', 'B'))
