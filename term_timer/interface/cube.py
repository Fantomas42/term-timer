from functools import cached_property

from cubing_algs.algorithm import Algorithm

from term_timer.orientation import get_orientation_moves
from term_timer.transform import reorient_moves


class Orienter:

    def __init__(self):
        super().__init__()

        self.orientation = ''

    @cached_property
    def cube_orientation_moves(self):
        return get_orientation_moves(self.orientation)

    def reorient(self, algorithm: Algorithm) -> Algorithm:
        return reorient_moves(self.cube_orientation_moves, algorithm)
