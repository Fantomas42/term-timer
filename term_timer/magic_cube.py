from cubing_algs.algorithm import Algorithm
from cubing_algs.display import VCubeDisplay
from magiccube.cube import Cube as BaseCube

from term_timer.config import CUBE_EFFECT
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.orientation import get_orientation_moves


class Cube(BaseCube):  # type: ignore[misc]
    face_number = 6

    def rotate(self, movements: Algorithm | list[str]) -> None:
        if isinstance(movements, list):
            for move in movements:
                self._rotate_once(move)
        else:
            super().rotate(str(movements))

    @property
    def state(self) -> str:
        return self.get_kociemba_facelet_positions()  # type: ignore[no-any-return]

    def display(self, orientation: str) -> str:
        orientation_moves = get_orientation_moves(orientation)

        if orientation_moves:
            self.rotate(orientation_moves)

        display = VCubeDisplay(self, CUBE_PALETTE, CUBE_EFFECT).display()

        if orientation_moves:
            for _ in orientation_moves:
                self.undo()

        return display

    def __str__(self) -> str:
        return self.display(CUBE_ORIENTATION)
