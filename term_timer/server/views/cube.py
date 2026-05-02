"""Cube image and render views."""
from bottle import response
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.display.mode import MODE_CONFIGS
from cubing_algs.display.palettes import PALETTES
from cubing_algs.transform.invert import invert_moves
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.constants import CUBE_SIZES
from term_timer.orientation import get_orientation_moves
from term_timer.server.annotations import CubeRenderContext
from term_timer.server.views.base import View


class CubeImageView(View):
    """View for displaying a cube in SVG."""

    def __init__(  # noqa: PLR0913, PLR0917
            self,
            cube_size: str,
            algorithm: str,
            case: str,
            mode: str,
            layout: str,
            orientation: CubeOrientation,
            mask: str,
            palette: str,
            image_size: str,
            rotation: str,
            distance: str,
            arrows: str,
    ) -> None:
        """
        Initialize algorithm image view.

        Args:
            cube_size: Cube size to use.
            algorithm: Algorithm to represent.
            case: Algorithm to represent to solve the case.
            mode: Mode to render to cube.
            layout: Render layout used.
            orientation: Orientation of the initial cube.
            mask: Mask of facelet display.
            palette: The cube palette color used.
            image_size: Image size to render.
            rotation: Rotation to apply to the 3D cube.
            distance: The camera distance.
            arrows: The arrows to draw.

        """
        self.algorithm = (
            algorithm and Algorithm.parse_moves(algorithm)
        ) or Algorithm.parse_moves(case).transform(invert_moves)

        self.cube_size = (cube_size and int(cube_size)) or 3
        self.image_size = (image_size and int(image_size)) or 200
        self.mode = mode
        self.layout = layout
        self.orientation = orientation or CUBE_ORIENTATION
        self.mask = mask
        self.palette = palette or CUBE_PALETTE
        self.rotation = rotation
        self.distance = (distance and int(distance)) or 10.0
        self.arrows = arrows

        if self.orientation:
            orientation_moves = get_orientation_moves(self.orientation)
            self.algorithm = orientation_moves + self.algorithm

    def as_view(self, _debug: bool) -> str:  # noqa: FBT001
        """
        Render the cube in SVG.

        Returns:
            The rendered cube.

        """
        response.content_type = 'image/svg+xml'
        response.set_header('Cache-Control', 'public, max-age=300')

        cube = VCube(size=self.cube_size)
        cube.rotate(self.algorithm)

        # Keep default orientation in AF2L mode for consistency
        orientation = self.orientation if self.mode == 'af2l' else ''

        return cube.image(
            mode=self.mode,
            layout=self.layout,
            orientation=orientation,
            mask=self.mask,
            palette=self.palette,
            image_size=self.image_size,
            rotation=self.rotation,
            distance=self.distance,
            arrows=self.arrows,
        )


class CubeRenderView(View):
    """View for cube rendering with live rotation."""

    template_name = 'cube_render.html'

    def __init__(
            self, orientation: CubeOrientation = '', mode: str = '',
            cube_size: str = '', palette: str = '',
            algorithm: str = '') -> None:
        """
        Initialize the cube render view.

        Args:
            orientation: Cube orientation for display.
            mode: Display mode override.
            cube_size: Cube size override for display.
            palette: Color palette override.
            algorithm: Optional algorithm applied before rendering.

        """
        self.orientation = orientation or CUBE_ORIENTATION
        self.display_mode = mode
        self.cube_size = int(cube_size) if cube_size else 3
        self.palette = palette or CUBE_PALETTE
        self.algorithm = algorithm

    def get_context(self) -> CubeRenderContext:
        """
        Build context for the cube render template.

        Returns:
            Dictionary with selector options and algorithm.

        """
        return {
            'algorithm': self.algorithm,
            'orientation_faces': self.orientation,
            'orientation_moves': get_orientation_moves(self.orientation),
            'available_orientations': ORIENTATION_FACE_MOVES,
            'mode': self.display_mode,
            'available_modes': ['', *sorted(MODE_CONFIGS.keys())],
            'cube_size': self.cube_size,
            'available_cube_sizes': CUBE_SIZES,
            'palette': self.palette,
            'available_palettes': sorted(PALETTES.keys()),
        }
