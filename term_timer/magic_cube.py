from cubing_algs.algorithm import Algorithm
from cubing_algs.display import VCubeDisplay
from cubing_algs.vcube import VCube
from magiccube.cube import Cube as BaseCube

from term_timer.config import CUBE_ORIENTATION_MOVES
from term_timer.interface.console import console


# Patch VCube + VCubeDisplay
def show_rich(self, mode: str = '', orientation: str = '',
              mask: str = '') -> None:
    console.print(self.display(mode, orientation, mask), end='')


def display_rich_facelet(_, facelet: str, mask: str = '') -> str:
    face_color = facelet.lower()
    if mask == '0':
        face_color += '_hidden'

    return (
        f'[face_{ face_color }]'
        f' { facelet } '
        f'[/face_{ face_color }]'
    )


VCube.show = show_rich
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
    def state(self) -> str:
        return self.get_kociemba_facelet_positions()

    def display(self, orientation: Algorithm = None) -> str:
        if orientation:
            self.rotate(orientation)

        display = VCubeDisplay(self).display()

        if orientation:
            for _ in orientation:
                self.undo()

        return display

    def __str__(self) -> str:
        return self.display(CUBE_ORIENTATION_MOVES)
