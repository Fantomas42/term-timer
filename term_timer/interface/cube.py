"""Cube orientation and reorientation capabilities."""
from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.translate import translate_moves

from term_timer.orientation import get_orientation_moves

if TYPE_CHECKING:
    from cubing_algs.annotations import CubeOrientation


class Orienter:
    """Mixin providing cube orientation and reorientation capabilities."""

    def __init__(self) -> None:
        """Initialize cube orientation with empty orientation faces."""
        super().__init__()

        self.orientation_faces: CubeOrientation = ''

    @cached_property
    def cube_orientation_moves(self) -> Algorithm:
        """Get the orientation moves for the current cube orientation."""
        return get_orientation_moves(self.orientation_faces)

    @cached_property
    def translation(self) -> Callable[[Algorithm], Algorithm]:
        """Cache the translation function to reorient."""
        return translate_moves(self.cube_orientation_moves)

    def reorient(self, algorithm: Algorithm) -> Algorithm:
        """
        Reorient an algorithm based on the current cube orientation.

        Returns:
            Algorithm translated based on cube orientation moves.

        """
        return self.translation(algorithm)
