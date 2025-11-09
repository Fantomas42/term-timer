"""Tests for magic cube."""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.magic_cube import Cube


class TestCube(unittest.TestCase):
    """Tests for Cube class."""

    def setUp(self) -> None:
        """Set up test fixture with a default Cube instance."""
        self.cube = Cube()

    def test_initialization(self) -> None:
        """Test that Cube initializes with correct default values."""
        self.assertEqual(
            self.cube.size, 3,
        )
        self.assertEqual(
            self.cube.face_number, 6,
        )
        self.assertEqual(
            self.cube.state,
            'UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB',
        )

    @patch(
        'cubing_algs.display.VCubeDisplay.display',
        return_value='Cube Representation',
    )
    def test_str_representation(self, mock_print_cube: Mock) -> None:
        """Test that the __str__ method returns the cube representation."""
        result = str(self.cube)
        self.assertEqual(result, 'Cube Representation')

        # Verify that print_cube was called with the correct cube instance
        mock_print_cube.assert_called_once()
