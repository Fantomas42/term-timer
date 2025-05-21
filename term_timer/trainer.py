import logging

from term_timer.interface import Interface

logger = logging.getLogger(__name__)


class Trainer(Interface):
    def __init__(self, *, mode: str,
                 show_cube: bool):

        self.mode = mode
        self.show_cube = show_cube

    def start(self):
        ...
