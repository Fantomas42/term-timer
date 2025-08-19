from cubing_algs.algorithm import Algorithm
from magiccube.cube import Cube as BaseCube
from magiccube.cube import Face

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import LL_ORIENTATION

COLOR_TO_FACE = {
    'R': 'R',
    'B': 'B',
    'Y': 'D',
    'G': 'F',
    'W': 'U',
    'O': 'L',
}


class CubePrintRich:
    def __init__(self, cube: 'Cube'):
        self.cube = cube

    @staticmethod
    def _format_color(color: str, *, oll=False) -> str:
        face = COLOR_TO_FACE[color]

        if oll and color != 'Y':
            color = 'H'

        return f'[face_{ color.lower() }] { face } [/face_{ color.lower() }]'

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

    def _print_top_down_face_ll(self, face: Face, *,
                                oll=False, top=False) -> str:
        cube = self.cube

        result = '   '
        colors = cube.get_face_flat(face)[:3]
        if top:
            colors = reversed(colors)
        for color in colors:
            result += self._format_color(color.name, oll=oll)

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
        for line in print_order_mid:
            for line_index, face_line in enumerate(line):
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

    def print_top_face(self, orientation: Algorithm, *, oll=False):
        cube = self.cube

        if orientation:
            cube.rotate(str(orientation))

        result = self._print_top_down_face_ll(Face.B, oll=oll, top=True)

        for line in range(3):
            color = cube.get_face(Face.L)[0][line]
            result += self._format_color(color.name, oll=oll)

            for i in range(3):
                color = cube.get_face(Face.U)[line][i]
                result += self._format_color(color.name, oll=oll)

            color = cube.get_face(Face.R)[0][2 - line]
            result += self._format_color(color.name, oll=oll)

            result += '\n'

        result += self._print_top_down_face_ll(Face.F, oll=oll, top=False)

        if orientation:
            for _ in orientation:
                cube.undo()

        return result

    def print_oll(self, orientation: Algorithm):
        return self.print_top_face(orientation, oll=True)

    def print_pll(self, orientation: Algorithm):
        return self.print_top_face(orientation, oll=False)


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

    def oll(self):
        printer = CubePrintRich(self)
        return printer.print_oll(LL_ORIENTATION)

    def pll(self):
        printer = CubePrintRich(self)
        return printer.print_pll(LL_ORIENTATION)

    def __str__(self) -> str:
        return self.full_cube(CUBE_ORIENTATION)
