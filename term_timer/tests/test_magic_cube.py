# ruff: noqa: SLF001
import unittest
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

from magiccube.cube import Face

from term_timer.magic_cube import FACES_ORDER
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

        result = self.printer.print_cube()

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
        """Test que le cube s'initialise correctement."""
        self.assertEqual(
            self.cube.size, 3,
        )  # Par défaut, le cube est de taille 3x3

    def test_convert_moves(self):
        """
        Test que la méthode convert_moves convertit
        correctement les mouvements.
        """
        # Tester avec différents types de mouvements
        moves = ['R', "U'", 'F2', 'x', 'y', "z'"]
        result = Cube.convert_moves(moves)

        # Les rotations x, y, z devraient être en majuscules
        self.assertIn('X', result)
        self.assertIn('Y', result)
        self.assertIn("Z'", result)

        # Vérifier que les mouvements sont séparés par des espaces
        self.assertIn(' ', result)
        self.assertEqual(len(result.split()), len(moves))

    @patch('term_timer.magic_cube.japanese_moves', return_value=['F', 'U', 'D'])
    def test_japanese_moves_conversion(self, mock_japanese_moves):
        """Test que les mouvements japonais sont convertis correctement."""
        # Mouvements japonais à convertir
        jp_moves = ['mae', 'ue', 'shita']

        result = Cube.convert_moves(jp_moves)

        # Vérifier que japanese_moves a été appelé avec les bons arguments
        mock_japanese_moves.assert_called_once_with(jp_moves)

        # Vérifier que les mouvements japonais ont été convertis
        self.assertIn('F', result)
        self.assertIn('U', result)
        self.assertIn('D', result)

    @patch.object(Cube, 'convert_moves', return_value="R U' F2")
    @patch('magiccube.cube.Cube.rotate')
    def test_rotate(self, mock_parent_rotate, mock_convert):
        """Test que la méthode rotate appelle correctement la méthode parent."""
        moves = ['R', "U'", 'F2']
        self.cube.rotate(moves)

        # Vérifier que convert_moves a été appelé avec les bons arguments
        mock_convert.assert_called_once_with(moves)

        # Vérifier que la méthode parent rotate a été appelée
        # avec le résultat de convert_moves
        mock_parent_rotate.assert_called_once_with("R U' F2")

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


class TestFacesOrder(unittest.TestCase):
    def test_faces_order(self):
        """Test que FACES_ORDER contient les faces dans le bon ordre."""
        self.assertEqual(FACES_ORDER, ['W', 'O', 'G', 'R', 'B', 'Y'])
        self.assertEqual(len(FACES_ORDER), 6)
