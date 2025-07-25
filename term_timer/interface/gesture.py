import asyncio
import logging

from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import compress_final_rotations
from cubing_algs.transform.slice import reslice_moves

logger = logging.getLogger(__name__)


class Gesture:

    def __init__(self):
        super().__init__()

        self.save_moves = Algorithm()
        self.save_gesture = ''
        self.save_gesture_event = asyncio.Event()

    def handle_save_gestures(self, move):
        move = self.reorient(move)

        self.save_moves += move

        if len(self.save_moves) < 2:
            return

        algo = self.save_moves.transform(
            reslice_moves,
            degrip_full_moves,
            compress_final_rotations,
        )

        l_move = algo[-1]
        a_move = algo[-2]

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
