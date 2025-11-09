"""Cube representation with state management and display capabilities."""

from cubing_algs.algorithm import Algorithm
from cubing_algs.display import VCubeDisplay
from magiccube.cube import Cube as BaseCube

from term_timer.config import CUBE_EFFECT
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.orientation import get_orientation_moves


class Cube(BaseCube):  # type: ignore[misc]
    """
    Extended Rubik's cube with Algorithm support and display capabilities.

    Extends magiccube.cube.Cube with support for cubing_algs.Algorithm
    objects and customizable visual display.
    """

    face_number = 6

    def rotate(self, movements: Algorithm | list[str]) -> None:
        """Apply move sequence to cube, accepting Algorithm or list."""
        if isinstance(movements, list):
            for move in movements:
                self._rotate_once(move)
        else:
            super().rotate(str(movements))

    @property
    def state(self) -> str:
        """Get cube state as 54-character facelet string."""
        return self.get_kociemba_facelet_positions()  # type: ignore[no-any-return]

    def display(self, orientation: str) -> str:
        """
        Generate colored terminal display of cube.

        Returns:
            Formatted string with ANSI color codes for terminal display.

        """
        orientation_moves = get_orientation_moves(orientation)

        if orientation_moves:
            self.rotate(orientation_moves)

        display = VCubeDisplay(self, CUBE_PALETTE, CUBE_EFFECT).display()

        if orientation_moves:
            for _ in orientation_moves:
                self.undo()

        return display

    def __str__(self) -> str:
        """
        Return string representation of cube with default orientation.

        Returns:
            Formatted cube display string.

        """
        return self.display(CUBE_ORIENTATION)
