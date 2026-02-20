"""Gesture detection for save commands from cube movements."""
import asyncio
import logging
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.move import Move

from term_timer.transform import humanize_moves_unsecured

logger = logging.getLogger(__name__)


class Gesture:
    """Mixin providing gesture detection for save commands."""

    if TYPE_CHECKING:
        # Method from Orienter mixin
        def reorient(self, algorithm: Algorithm) -> Algorithm:
            """Transform algorithm using cube orientation."""
            ...

        # Method from Bluetooth mixin
        def cube_is_solved(self) -> bool:
            """Check if the Bluetooth cube is in solved state."""
            ...

    def __init__(self) -> None:
        """Initialize gesture detection with empty save gesture state."""
        super().__init__()

        self.save_moves = Algorithm()
        self.save_gesture = ''
        self.save_gesture_event = asyncio.Event()

    def handle_save_gestures(self, timed_move: Move) -> None:
        """Detect and handle save gestures from cube movements."""
        move = self.reorient(Algorithm([timed_move]))

        self.save_moves += move

        if len(self.save_moves) < 2:
            return

        if not self.cube_is_solved():
            return

        algo = self.save_moves.transform(
            humanize_moves_unsecured,
        )

        if len(algo) < 2:
            return

        l_move = algo[-1].untimed
        a_move = algo[-2].untimed

        if l_move.base_move != a_move.base_move:
            return

        if l_move == a_move:
            return

        base_move = l_move.base_move

        if base_move in {'F', 'R', 'U', 'B', 'L'}:
            self.save_gesture = ''
        elif base_move in {'M', 'S', 'E'}:
            self.save_gesture = 'z'
        elif base_move == 'D':
            self.save_gesture = 'q'
        else:
            return

        self.save_gesture_event.set()
        logger.info(
            'Save gesture: %s => *%s*',
            base_move, self.save_gesture,
        )
