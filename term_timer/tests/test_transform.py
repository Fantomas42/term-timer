import unittest

from term_timer.transform import invert
from term_timer.transform import is_japanesable_move
from term_timer.transform import is_japanese_move
from term_timer.transform import japanese_move
from term_timer.transform import japanese_moves
from term_timer.transform import mirror_moves


class TestTransform(unittest.TestCase):
    def test_invert_regular_move(self):
        """Test inverting a regular move adds the invert character."""
        self.assertEqual(invert('F'), "F'")

    def test_invert_already_inverted_move(self):
        """Test inverting an already inverted move
        removes the invert character."""
        self.assertEqual(invert("F'"), 'F')

    def test_mirror_moves_with_double_moves(self):
        """Test mirroring a sequence with double moves."""
        moves = ['F', 'R2', "U'"]
        expected = ['U', 'R2', "F'"]
        self.assertEqual(mirror_moves(moves), expected)

    def test_mirror_moves_with_only_regular_moves(self):
        """Test mirroring a sequence with only regular moves."""
        moves = ['F', 'R', 'U']
        expected = ["U'", "R'", "F'"]
        self.assertEqual(mirror_moves(moves), expected)

    def test_mirror_moves_with_only_inverted_moves(self):
        """Test mirroring a sequence with only inverted moves."""
        moves = ["F'", "R'", "U'"]
        expected = ['U', 'R', 'F']
        self.assertEqual(mirror_moves(moves), expected)

    def test_is_japanese_move_true(self):
        """Test identification of Japanese moves."""
        self.assertTrue(is_japanese_move('Fw'))
        self.assertTrue(is_japanese_move('fw'))

    def test_is_japanese_move_false(self):
        """Test identification of non-Japanese moves."""
        self.assertFalse(is_japanese_move('F'))
        self.assertFalse(is_japanese_move("F'"))
        self.assertFalse(is_japanese_move('F2'))

    def test_japanese_move_conversion(self):
        """Test converting a move to Japanese notation."""
        self.assertEqual(japanese_move('f'), 'Fw')
        self.assertEqual(japanese_move("f'"), "Fw'")
        self.assertEqual(japanese_move('f2'), 'Fw2')

    def test_is_japanesable_move_true(self):
        """Test identification of moves that can be converted
        to Japanese notation."""
        self.assertTrue(is_japanesable_move('f'))
        self.assertTrue(is_japanesable_move("f'"))
        self.assertTrue(is_japanesable_move('f2'))

    def test_is_japanesable_move_false(self):
        """Test identification of moves that cannot be converted
        to Japanese notation."""
        self.assertFalse(is_japanesable_move('F'))  # Uppercase
        self.assertFalse(is_japanesable_move('Fw'))  # Already Japanese
        self.assertFalse(is_japanesable_move('x'))  # Rotation

    def test_japanese_moves_conversion(self):
        """Test converting a sequence of moves to Japanese notation."""
        moves = ['f', 'R', 'Uw', 'x', 'fw']
        expected = ['Fw', 'R', 'Uw', 'x', 'fw']
        self.assertEqual(japanese_moves(moves), expected)

    def test_japanese_moves_mixed_notation(self):
        """Test converting a mixed sequence with some already
        in Japanese notation."""
        moves = ['f', 'F', 'Fw', "r'", 'R2']
        expected = ['Fw', 'F', 'Fw', "Rw'", 'R2']
        self.assertEqual(japanese_moves(moves), expected)
