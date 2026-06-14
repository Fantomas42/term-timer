"""Academy overview, step, and case views."""
from typing import TYPE_CHECKING
from typing import ClassVar
from typing import cast

from bottle import abort
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases import get_case
from cubing_algs.cases import get_collection
from cubing_algs.constants import ORIENTATION_FACE_MOVES

if TYPE_CHECKING:
    from cubing_algs.cases.case import Case
from cubing_algs.display.mode import MODE_CONFIGS
from cubing_algs.display.palettes import PALETTES

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.constants import CUBE_SIZES
from term_timer.orientation import get_orientation_moves
from term_timer.server.annotations import AcademyCaseContext
from term_timer.server.annotations import AcademyOverviewContext
from term_timer.server.annotations import AcademyStepContext
from term_timer.server.annotations import MethodInfo
from term_timer.server.views.base import View


class AcademyView(View):
    """View for displaying academy overview with solving methods."""

    template_name = 'academy/overview.html'
    orientation: CubeOrientation = ''
    display_mode: str = ''
    cube_size: int = 3
    palette: str = ''
    methods: ClassVar[dict[str, MethodInfo]] = {
        'CFOP': {
            'cube_size': 3,
            'description': (
                'Cross, F2L, OLL, PLL - The most popular speedcubing method'
            ),
            'steps': {
                'F2L': {
                    'description': (
                        'First Two Layers - '
                        'Solve cross and first two layers simultaneously'
                    ),
                    'mode': 'f2l',
                },
                'OLL': {
                    'description': (
                        'Orientation of Last Layer - '
                        'Orient all pieces on the last layer'
                    ),
                    'mode': 'oll',
                },
                'PLL': {
                    'description': (
                        'Permutation of Last Layer - '
                        'Permute all pieces on the last layer'
                    ),
                    'mode': 'pll',
                },
                'AF2L': {
                    'description': (
                        'Advanced First Two Layers - '
                        'Solve first two layers with advanced techniques.'
                    ),
                    'mode': 'af2l',
                },
            },
        },
        'Roux': {
            'cube_size': 3,
            'description': (
                'First Two Block, CMLL, LSE - '
                'The blockbuilding speedcubing method'
            ),
            'steps': {
                'CMLL': {
                    'description': (
                        'Corners of last layer - '
                        'Solve of corner orientations and permutations'
                    ),
                    'mode': 'cmll',
                },
                'LSE': {
                    'description': (
                        'Last Six Edges - '
                        'Solve M-slice centers and edges together'
                    ),
                    'mode': 'lse',
                },
            },
        },
        'Ortega': {
            'cube_size': 2,
            'description': (
                'Solve D, OLL, PBL - The most popular 2x2x2 method'
            ),
            'steps': {
                'OLL': {
                    'description': (
                        'Orientation of Last Layer - '
                        'Orient all pieces on the last layer'
                    ),
                    'mode': 'oll',
                },
                'PBL': {
                    'description': (
                        'Permutation of Both Layers - '
                        'Orient all pieces on all layers'
                    ),
                    'mode': '',
                },
            },
        },
    }

    def __init__(self, orientation: CubeOrientation = '', mode: str = '',
                 cube_size: str = '', palette: str = '') -> None:
        """
        Initialize academy overview view.

        Args:
            orientation: Cube orientation for display.
            mode: Display mode override.
            cube_size: Cube size override for display.
            palette: Color palette override.

        """
        self.orientation = orientation
        self.display_mode = mode
        self.cube_size = int(cube_size) if cube_size else 3
        self.palette = palette

    def get_display_context(self, default_mode: str = '') -> dict[
        str,
        str | Algorithm | dict[str, str] | int | list[str] | list[int],
    ]:
        """
        Build shared display parameter context for academy views.

        Args:
            default_mode: Default mode when no GET override is provided.

        Returns:
            Dictionary with orientation, mode, cube size, and palette context.

        """
        orientation_faces = self.orientation or CUBE_ORIENTATION
        mode = self.display_mode or default_mode
        palette = self.palette or CUBE_PALETTE

        return {
            'orientation_faces': orientation_faces,
            'orientation_moves': get_orientation_moves(orientation_faces),
            'available_orientations': ORIENTATION_FACE_MOVES,
            'mode': mode,
            'available_modes': ['', *sorted(MODE_CONFIGS.keys())],
            'cube_size': self.cube_size,
            'available_cube_sizes': CUBE_SIZES,
            'palette': palette,
            'available_palettes': sorted(PALETTES.keys()),
        }

    def get_context(
            self,
    ) -> (
        AcademyOverviewContext
        | AcademyStepContext
        | AcademyCaseContext
    ):
        """
        Build context with available solving methods.

        Returns:
            Dictionary containing methods and their descriptions.

        """
        return cast(
            'AcademyOverviewContext',
            {
                'methods': self.methods,
                **self.get_display_context(),
            },
        )


class AcademyStepView(AcademyView):
    """View for displaying all cases for a specific method step."""

    template_name = 'academy/step.html'

    def __init__(  # noqa: PLR0913, PLR0917
            self, method: str, step: str, group: str, family: str,
            orientation: CubeOrientation, mode: str = '', cube_size: str = '',
            palette: str = '') -> None:
        """
        Initialize academy step view.

        Args:
            method: Method name (CFOP, Ortega).
            step: Method step name (F2L, OLL, or PLL).
            group: Step group filter.
            family: Step family filter.
            orientation: Cube orientation for display.
            mode: Display mode override.
            cube_size: Cube size override for display.
            palette: Color palette override.

        """
        self.method = method
        self.step = step
        self.group = group
        self.family = family
        self.orientation = orientation
        self.display_mode = mode
        self.palette = palette

        try:
            self.cases = get_collection(f'{ method }/{ step }').cases
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = (
                int(cube_size) if cube_size
                else self.methods[method]['cube_size']
            )
        except KeyError:
            abort(404, f'{ method }/{ step } does not exist')

        if group:
            self.cases = {
                c: case
                for c, case in self.cases.items()
                if group in case.groups
            }
        if family:
            self.cases = {
                c: case
                for c, case in self.cases.items()
                if family == case.family
            }

    def get_context(self) -> AcademyStepContext:
        """
        Build context with all cases for the step.

        Returns:
            Dictionary containing step information, case list.

        """
        tree: dict[str, list[Case]] = {}
        cases = []
        for case in self.cases.values():
            if case.code != 'SKIP':
                tree.setdefault(case.family, []).append(case)
                cases.append(case)

        return cast(
            'AcademyStepContext',
            {
                'method': self.method,
                'step': self.step,
                'step_info': self.step_info,
                'group': self.group,
                'family': self.family,
                'cases': cases,
                'tree': tree,
                **self.get_display_context(
                    default_mode=self.step_info['mode'],
                ),
            },
        )


class AcademyCaseView(AcademyView):
    """View for displaying detailed information about a specific case."""

    template_name = 'academy/case.html'

    def __init__(  # noqa: PLR0913, PLR0917
            self, method: str, step: str, case_id: str,
            orientation: CubeOrientation, mode: str = '', cube_size: str = '',
            palette: str = '') -> None:
        """
        Initialize academy case view.

        Args:
            method: Method name (CFOP).
            step: CFOP step name (F2L, OLL, or PLL).
            case_id: Case identifier within the step.
            orientation: Cube orientation for display.
            mode: Display mode override.
            cube_size: Cube size override for display.
            palette: Color palette override.

        """
        self.method = method
        self.step = step
        self.case_id = case_id
        self.orientation = orientation
        self.display_mode = mode
        self.palette = palette

        try:
            self.case = get_case(f'{ method }/{ step }', case_id)
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = (
                int(cube_size) if cube_size
                else self.methods[method]['cube_size']
            )
        except KeyError:
            abort(404, f'{ method }/{ step } { case_id } does not exist')

    def get_context(self) -> AcademyCaseContext:
        """
        Build context with case details, algorithms, and orientations.

        Returns:
            Dictionary containing case information.

        """
        return cast(
            'AcademyCaseContext',
            {
                'method': self.method,
                'step': self.step,
                'step_info': self.step_info,
                'case': self.case,
                **self.get_display_context(
                    default_mode=self.step_info['mode'],
                ),
            },
        )


class AcademyCaseAlgorithmsDebugView(AcademyCaseView):
    """Debug view listing a case's algorithms with sortable scores."""

    template_name = 'academy/case_debug.html'
