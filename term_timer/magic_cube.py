from magiccube.cube import Cube as BaseCube
from magiccube.cube import Face

from term_timer.constants import ROTATIONS
from term_timer.transform import japanese_moves

INITIAL_SCRAMBLE = ''.join(  # noqa: FLY002
    [
        'WWWWWWWWW',
        'OOOOOOOOO',
        'GGGGGGGGG',
        'RRRRRRRRR',
        'BBBBBBBBB',
        'YYYYYYYYY',
    ],
)


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

        facelets = facelets.replace('W', 'U')
        facelets = facelets.replace('Y', 'D')
        facelets = facelets.replace('G', 'F')
        facelets = facelets.replace('O', 'L')

        return facelets  # noqa: RET504
