from magiccube.cube import Cube as BaseCube
from magiccube.cube import Face

from term_timer.constants import ROTATIONS
from term_timer.transform import japanese_moves

FACES_ORDER = ['W', 'O', 'G', 'R', 'B', 'Y']


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

    def print_cube(self) -> str:
        cube = self.cube

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

        return result


class Cube(BaseCube):  # type: ignore[misc]

    def rotate(self, moves: list[str]) -> None:
        converted_moves = self.convert_moves(moves)
        super().rotate(converted_moves)

    @classmethod
    def convert_moves(cls, old_moves: list[str]) -> str:
        old_moves = japanese_moves(old_moves)
        moves = []
        for _move in old_moves:
            move = str(_move)

            if move[0] in ROTATIONS:
                move = move.upper()

            moves.append(move)

        return ' '.join(moves)

    @property
    def as_twophase_facelets(self) -> str:
        faces = [
            ''.join(
                [
                    fc.name
                    for fc in self.get_face_flat(
                            Face.create(f),
                    )
                ],
            )
            for f in ['U', 'R', 'F', 'D', 'L', 'B']
        ]

        facelets = ''.join(faces).upper()

        for color, face in (
                ('W', 'U'), ('Y', 'D'),
                ('G', 'F'), ('O', 'L'),
        ):
            facelets = facelets.replace(color, face)

        return facelets

    def __str__(self) -> str:
        printer = CubePrintRich(self)
        return printer.print_cube()
