import unittest
from unittest.mock import patch

from term_timer.scrambler import is_valid_next_move
from term_timer.scrambler import random_moves
from term_timer.scrambler import scrambler
from term_timer.scrambler import solve_moves


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

    @patch('term_timer.scrambler.choices')
    @patch('term_timer.scrambler.randint')
    def test_random_moves_normal_mode(self, mock_randint, mock_choices):
        """Test random moves generation in normal mode."""
        # Setup mocks
        mock_choices.side_effect = [['F'], ['R'], ['U'], ['L']]
        mock_randint.return_value = 4  # 4 moves

        moves = random_moves(3, 0, easy_cross=False)

        # Should have 4 moves
        self.assertEqual(len(moves), 4)
        self.assertEqual(moves, ['F', 'R', 'U', 'L'])

    @patch('term_timer.scrambler.choices')
    def test_random_moves_ec_mode(self, mock_choices):
        """Test random moves generation in ec mode."""
        # Setup mock
        mock_choices.side_effect = [
            ['F'],
            ['R'],
            ['B'],
            ['L'],
            ['F'],
            ['R'],
            ['B'],
            ['L'],
            ['F'],
            ['R'],
        ]

        moves = random_moves(3, 0, easy_cross=True)

        # Should have exactly 10 moves for ec mode
        self.assertEqual(len(moves), 10)

    @patch('term_timer.scrambler.choices')
    def test_random_moves_with_specified_iterations(self, mock_choices):
        """Test random moves generation with specified iterations."""
        # Setup mock for 5 moves
        mock_choices.side_effect = [['F'], ['R'], ['U'], ['L'], ['D']]

        moves = random_moves(3, 5, easy_cross=False)

        # Should have exactly 5 moves
        self.assertEqual(len(moves), 5)

    @patch('term_timer.scrambler.solve')
    def test_solve_moves_valid_solution(self, mock_solve):
        """Test parsing twophase solver output."""
        # Mock a solution string from the solver
        mock_solve.return_value = "F R U R' U' F' (8 moves)"

        moves = solve_moves('some_state_string')

        expected = ['F', 'R', 'U', "R'", "U'", "F'"]
        self.assertEqual(moves, expected)

    @patch('term_timer.scrambler.solve')
    def test_solve_moves_error(self, mock_solve):
        """Test handling error from twophase solver."""
        # Mock an error response
        mock_solve.return_value = 'Error: Invalid cube state'

        moves = solve_moves('invalid_state')

        # Should return empty list for errors
        self.assertEqual(moves, [])

    @patch('term_timer.scrambler.random_moves')
    @patch('term_timer.scrambler.solve_moves')
    def test_scrambler_2x2(self, mock_solve_moves, mock_random_moves):
        """Test scrambler for 2x2 cube."""
        # Setup mocks
        mock_random_moves.return_value = ['R', 'U', "R'"]

        moves, cube = scrambler(2, 0, easy_cross=False)

        # For 2x2, should just return random moves (no solve)
        self.assertEqual(moves, ['R', 'U', "R'"])
        self.assertEqual(cube.size, 2)

        # solve_moves should not be called for 2x2
        mock_solve_moves.assert_not_called()

    @patch('term_timer.scrambler.TWO_PHASE_INSTALLED', False)  # noqa: FBT003
    @patch('term_timer.scrambler.random_moves')
    @patch('term_timer.scrambler.solve_moves')
    def test_scrambler_3x3_no_twophase(
        self, mock_solve_moves, mock_random_moves,
    ):
        """Test scrambler for 3x3 without twophase installed."""
        # Setup mocks
        mock_random_moves.return_value = ['F', 'R', 'U', "R'", "U'", "F'"]

        moves, cube = scrambler(3, 0, easy_cross=False)

        # Without twophase, should just return random moves
        self.assertEqual(moves, ['F', 'R', 'U', "R'", "U'", "F'"])
        self.assertEqual(cube.size, 3)

        # solve_moves should not be called without twophase
        mock_solve_moves.assert_not_called()
