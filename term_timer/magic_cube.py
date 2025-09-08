from cubing_algs.display import VCubeDisplay
from magiccube.cube import Cube as BaseCube

from term_timer.config import CUBE_ORIENTATION_MOVES


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


class Cube(BaseCube):  # type: ignore[misc]
    face_number = 6

    def rotate(self, movements) -> None:
        if isinstance(movements, list):
            for move in movements:
                self._rotate_once(move)
        else:
            super().rotate(str(movements))

    @property
    def state(self):
        return self.get_kociemba_facelet_positions()

    def __str__(self) -> str:
        if CUBE_ORIENTATION_MOVES:
            self.rotate(str(CUBE_ORIENTATION_MOVES))

        display = VCubeDisplay(self).display()

        if CUBE_ORIENTATION_MOVES:
            for _ in CUBE_ORIENTATION_MOVES:
                self.undo()

        return display
