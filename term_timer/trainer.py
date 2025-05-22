import logging

from term_timer.interface import Interface

logger = logging.getLogger(__name__)


class Trainer(Interface):
    def __init__(self, *, mode: str,
                 show_cube: bool):

        self.moves = []
        self.state = 'init'

        self.mode = mode
        self.show_cube = show_cube

    def handle_bluetooth_move(self, event):
        ...

    def start(self) -> bool:
        self.set_state('start')
        self.moves = []
