from cubing_algs.algorithm import Algorithm
from cubing_algs.display import VCubeDisplay
from magiccube.cube import Cube as BaseCube

from term_timer.config import CUBE_EFFECT
from term_timer.config import CUBE_ORIENTATION_MOVES
from term_timer.config import CUBE_PALETTE


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

        display = VCubeDisplay(self, CUBE_PALETTE, CUBE_EFFECT).display()

        if orientation:
            for _ in orientation:
                self.undo()

        return display

    def __str__(self) -> str:
        return self.display(CUBE_ORIENTATION_MOVES)
