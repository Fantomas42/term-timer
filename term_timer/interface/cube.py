from functools import cached_property

from cubing_algs.algorithm import Algorithm

from term_timer.orientation import get_orientation_moves
from term_timer.transform import reorient_moves


class Orienter:
    """
    Mixin providing cube orientation and reorientation capabilities.
    """

    def __init__(self) -> None:
        super().__init__()

        self.orientation: str = ''

    @cached_property
    def cube_orientation_moves(self) -> Algorithm:
        """
        Get the orientation moves for the current cube orientation.
        """
        return get_orientation_moves(self.orientation)

    def reorient(self, algorithm: Algorithm) -> Algorithm:
        """
        Reorient an algorithm based on the current cube orientation.
        """
        return reorient_moves(self.cube_orientation_moves, algorithm)
