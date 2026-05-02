"""Algorithm detail view."""
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.transform.invert import invert_moves
from cubing_algs.transform.offset import offset_y2_moves
from cubing_algs.transform.offset import offset_y_moves
from cubing_algs.transform.offset import offset_yprime_moves
from cubing_algs.transform.symmetry import symmetry_c_moves
from cubing_algs.transform.symmetry import symmetry_m_moves
from cubing_algs.transform.symmetry import symmetry_s_moves

from term_timer.config import CUBE_ORIENTATION
from term_timer.orientation import get_orientation_moves
from term_timer.server.annotations import AlgorithmDetailContext
from term_timer.server.annotations import AlgorithmVariation
from term_timer.server.views.base import View


class AlgorithmDetailView(View):
    """View for displaying algorithm with transformations and variations."""

    template_name = 'algorithm.html'

    def __init__(self, algorithm: str, orientation: CubeOrientation) -> None:
        """
        Initialize algorithm detail view.

        Args:
            algorithm: Algorithm string in standard cube notation.
            orientation: Cube orientation for display.

        """
        self.algorithm = Algorithm.parse_moves(algorithm)
        self.orientation = orientation

    def get_context(self) -> AlgorithmDetailContext:
        """
        Build context with algorithm variations and transformations.

        Returns:
            Dictionary containing original algorithm, Y-axis rotations,
            symmetry transformations, and invert variation.

        """
        # Generate Y-axis variations
        y_variations: list[AlgorithmVariation] = [
            {
                'label': 'Y',
                'algorithm': offset_y_moves(self.algorithm),
            },
            {
                'label': 'Y2',
                'algorithm': offset_y2_moves(self.algorithm),
            },
            {
                'label': "Y'",
                'algorithm': offset_yprime_moves(self.algorithm),
            },
        ]

        symmetry_variations: list[AlgorithmVariation] = [
            {
                'label': 'Symmetry M',
                'algorithm': symmetry_m_moves(self.algorithm),
            },
            {
                'label': 'Symmetry S',
                'algorithm': symmetry_s_moves(self.algorithm),
            },
            {
                'label': 'Symmetry C',
                'algorithm': symmetry_c_moves(self.algorithm),
            },
        ]

        selected_orientation = self.orientation or CUBE_ORIENTATION

        return {
            'algorithm': self.algorithm,
            'y_variations': y_variations,
            'symmetry_variations': symmetry_variations,
            'inverse_variation': invert_moves(self.algorithm),
            'orientation_faces': selected_orientation,
            'orientation_moves': get_orientation_moves(selected_orientation),
            'available_orientations': ORIENTATION_FACE_MOVES,
        }
