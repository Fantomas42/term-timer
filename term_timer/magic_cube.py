from cubing_algs.display import VCubeDisplay
from magiccube.cube import Cube as BaseCube

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
        if CUBE_ORIENTATION:
            self.rotate(str(CUBE_ORIENTATION))

        display = VCubeDisplay(self).display()

        if CUBE_ORIENTATION:
            for _ in CUBE_ORIENTATION:
                self.undo()

        return display
