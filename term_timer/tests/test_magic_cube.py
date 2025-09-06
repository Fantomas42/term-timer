import unittest
from unittest.mock import patch

from term_timer.magic_cube import Cube


class TestCube(unittest.TestCase):
    def setUp(self):
        self.cube = Cube()

    def test_initialization(self):
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
    def test_str_representation(self, mock_print_cube):
        """Test que la méthode __str__ renvoie la représentation du cube."""
        result = str(self.cube)
        self.assertEqual(result, 'Cube Representation')

        # Vérifier que print_cube a été appelé avec la bonne instance de cube
        mock_print_cube.assert_called_once()
