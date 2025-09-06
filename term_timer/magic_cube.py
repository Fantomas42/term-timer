from cubing_algs.algorithm import Algorithm
from cubing_algs.display import VCubeDisplay
from magiccube.cube import Cube as BaseCube
from magiccube.cube import Face

from term_timer.config import CUBE_ORIENTATION

COLOR_TO_FACE = {
    'R': 'R',
    'B': 'B',
    'Y': 'D',
    'G': 'F',
    'W': 'U',
    'O': 'L',
}


# Patch VCubeDisplay
def display_rich_facelet(_, facelet: str, mask: str = '') -> str:
    face_color = facelet.lower()
    if mask == '0':
        face_color += '_hidden'

    return (
        f'[face_{ face_color }]'
        f' { facelet } '
        f'[/face_{ face_color }]'
    )


VCubeDisplay.display_facelet = display_rich_facelet

# End patch


class CubePrintRich:
    def __init__(self, cube: 'Cube'):
        self.cube = cube

    @staticmethod
    def _format_color(color: str) -> str:
        face = COLOR_TO_FACE[color]
        face_color = COLOR_TO_FACE[color].lower()

        return f'[face_{ face_color }] { face } [/face_{ face_color }]'

    def _print_top_down_face(self, face: Face) -> str:
        result = ''
        cube = self.cube

        for index, color in enumerate(cube.get_face_flat(face)):
            if index % cube.size == 0:
                result += (' ' * (3 * cube.size))

            result += self._format_color(color.name)

            if index % cube.size == cube.size - 1:
                result += (' ' * (2 * 3 * cube.size))
                result += '\n'

        return result

    def print_cube(self, orientation: Algorithm) -> str:
        cube = self.cube

        if orientation:
            cube.rotate(str(orientation))

        # Flatten middle layer
        print_order_mid = zip(
            cube.get_face(Face.L),
            cube.get_face(Face.F),
            cube.get_face(Face.R),
            cube.get_face(Face.B),
            strict=True,
        )

        # Top
        result = self._print_top_down_face(Face.U)

        # Middle
        for order_mid in print_order_mid:
            for line_index, face_line in enumerate(order_mid):
                for face_line_index, color in enumerate(face_line):

                    result += self._format_color(color.name)

                    if face_line_index % cube.size == cube.size - 1:
                        result += ''
                if line_index == 3:
                    result += '\n'

        # Bottom
        result += self._print_top_down_face(Face.D)

        if orientation:
            for _ in orientation:
                cube.undo()

        return result


class Cube(BaseCube):  # type: ignore[misc]

    def rotate(self, movements) -> None:
        if isinstance(movements, list):
            for move in movements:
                self._rotate_once(move)
        else:
            super().rotate(str(movements))

    def full_cube(self, orientation: Algorithm):
        printer = CubePrintRich(self)
        return printer.print_cube(orientation)

    def __str__(self) -> str:
        printer = CubePrintRich(self)
        return printer.print_cube(CUBE_ORIENTATION)
