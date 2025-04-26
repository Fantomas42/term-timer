from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.japanese import japanese_moves
from cubing_algs.transform.mirror import mirror_moves
from magiccube.cube import Cube as BaseCube
from magiccube.cube import Face

from term_timer.config import CUBE_ORIENTATION


class CubePrintRich:
    def __init__(self, cube: 'Cube'):
        self.cube = cube

    @staticmethod
    def _format_color(color: str) -> str:
        return f'[face_{ color.lower() }] { color } [/face_{ color.lower() }]'

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
            cube.rotate(str(orientation).upper())

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


class Cube(BaseCube):  # type: ignore[misc]

    def rotate(self, movements) -> None:
        if isinstance(movements, list):
            for move in movements:
                self._rotate_once(move)
        else:
            super().rotate(str(movements))

    def printed(self, orientation: Algorithm):
        printer = CubePrintRich(self)
        return printer.print_cube(orientation)

    def __str__(self) -> str:
        return self.printed(CUBE_ORIENTATION)
