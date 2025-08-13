# ruff: noqa: SLF001
import unittest
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

from magiccube.cube import Face

from term_timer.magic_cube import Cube
from term_timer.magic_cube import CubePrintRich


class TestCubePrintRich(unittest.TestCase):
    def setUp(self):
        self.mock_cube = MagicMock()
        self.mock_cube.size = 3
        self.printer = CubePrintRich(self.mock_cube)

    def test_format_color(self):
        result = self.printer._format_color('W')
        expected = '[face_w] W [/face_w]'
        self.assertEqual(result, expected)

    @patch.object(CubePrintRich, '_format_color', return_value='[W]')
    def test_print_top_down_face(self, mock_format_color):
        # Créer des objets Color simulés avec une propriété name
        mock_colors = []
        for _ in range(9):
            color_mock = MagicMock()
            color_mock.name = 'W'
            mock_colors.append(color_mock)

        self.mock_cube.get_face_flat.return_value = mock_colors

        result = self.printer._print_top_down_face(Face.U)

        # Vérifier que _format_color a été appelé 9 fois
        # (une fois pour chaque couleur)
        self.assertEqual(mock_format_color.call_count, 9)

        # Vérifier que le résultat est une chaîne non vide
        self.assertTrue(isinstance(result, str))
        self.assertTrue(len(result) > 0)

        # Vérifier que le résultat contient le marqueur [W] 9 fois
        self.assertEqual(result.count('[W]'), 9)

        # Vérifier que le résultat contient des caractères d'espacement
        self.assertTrue(' ' in result)

        # Vérifier que le résultat contient des retours à la ligne
        # pour former la grille
        # Nombre de caractères de nouvelle ligne = nombre de lignes - 1
        # Pour un cube 3x3, nous attendons 3 lignes,
        # donc 2 caractères de nouvelle ligne
        self.assertEqual(result.count('\n'), 3)

    @patch.object(
        CubePrintRich, '_print_top_down_face',
        side_effect=['TOP\n', 'BOTTOM\n'],
    )
    @patch.object(CubePrintRich, '_format_color', return_value='[C]')
    def test_print_cube(self, mock_format_color, mock_print_face):  # noqa: ARG002
        """Test que la méthode print_cube génère le cube complet."""

        # Créer des mocks pour les faces avec des couleurs simulées
        def create_mock_colors(color_name):
            result = []
            for _ in range(3):
                row = []
                for _ in range(3):
                    color_mock = MagicMock()
                    color_mock.name = color_name
                    row.append(color_mock)
                result.append(row)
            return result

        mock_colors_u = create_mock_colors('W')
        mock_colors_l = create_mock_colors('O')
        mock_colors_f = create_mock_colors('G')
        mock_colors_r = create_mock_colors('R')
        mock_colors_b = create_mock_colors('B')

        self.mock_cube.get_face.side_effect = lambda face: {
            Face.U: mock_colors_u,
            Face.L: mock_colors_l,
            Face.F: mock_colors_f,
            Face.R: mock_colors_r,
            Face.B: mock_colors_b,
        }.get(face, [])

        result = self.printer.print_cube('')

        # Vérifier que _print_top_down_face a été appelé deux fois (pour U et D)
        mock_print_face.assert_has_calls([call(Face.U), call(Face.D)])

        # Vérifier que le résultat contient les parties attendues
        self.assertIn('TOP', result)
        self.assertIn('BOTTOM', result)
        self.assertIn('[C]', result)


class TestCube(unittest.TestCase):
    def setUp(self):
        self.cube = Cube()

    def test_initialization(self):
        self.assertEqual(
            self.cube.size, 3,
        )

    @patch(
        'term_timer.magic_cube.CubePrintRich.print_cube',
        return_value='Cube Representation',
    )
    def test_str_representation(self, mock_print_cube):
        """Test que la méthode __str__ renvoie la représentation du cube."""
        result = str(self.cube)
        self.assertEqual(result, 'Cube Representation')

        # Vérifier que print_cube a été appelé avec la bonne instance de cube
        mock_print_cube.assert_called_once()
