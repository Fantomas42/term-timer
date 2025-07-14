from cubing_algs.algorithm import Algorithm

from term_timer.config import CUBE_ORIENTATION
from term_timer.transform import reorient_moves


class Orienter:

    def __init__(self):
        super().__init__()

        self.cube_orientation = CUBE_ORIENTATION

    def reorient(self, algorithm: Algorithm) -> Algorithm:
        return reorient_moves(self.cube_orientation, algorithm)
