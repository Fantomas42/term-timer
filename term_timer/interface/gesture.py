import asyncio
import logging

logger = logging.getLogger(__name__)


class Gesture:

    def __init__(self):
        super().__init__()

        self.save_moves = []
        self.save_gesture = ''
        self.save_gesture_event = asyncio.Event()

    def handle_save_gestures(self, move):
        move = self.reorient(move)[0]

        self.save_moves.append(move)

        if len(self.save_moves) < 2:
            return

        l_move = self.save_moves[-1]
        a_move = self.save_moves[-2]

        if l_move.base_move != a_move.base_move:
            return

        if l_move == a_move:
            return

        base_move = l_move.base_move
        if base_move in {'R', 'U'}:
            self.save_gesture = 'o'
        elif base_move == 'L':
            self.save_gesture = 'z'
        elif base_move == 'D':
            self.save_gesture = 'q'
        else:
            return

        self.save_gesture_event.set()
        logger.info(
            'Save gesture: %s => %s',
            move, self.save_gesture,
        )
