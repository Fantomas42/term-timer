from term_timer.interface.bluetooth import Bluetooth
from term_timer.interface.console import Console
from term_timer.interface.controler import Controler
from term_timer.interface.cube import Orienter
from term_timer.interface.gesture import Gesture
from term_timer.interface.getcher import Getcher
from term_timer.interface.inspection import Inspecter
from term_timer.interface.scrambler import Scrambler
from term_timer.interface.state import State
from term_timer.interface.stopwatch import StopWatch
from term_timer.interface.terminal import Terminal


class Interface(
        State,
        Terminal,
        Console,
        Controler,
        Getcher,
        Orienter,
        StopWatch,
        Inspecter,
        Scrambler,
        Gesture,
        Bluetooth,
):

    def init_solve(self):
        self.end_time = 0
        self.start_time = 0
        self.elapsed_time = 0

        self.moves = []

        self.save_moves = []
        self.save_gesture = ''
        self.save_gesture_event.clear()

        self.scramble = []
        self.scrambled = []
        self.scramble_oriented = []
        self.facelets_scrambled = ''
        self.scramble_completed_event.clear()

        self.solve_started_event.clear()
        self.solve_completed_event.clear()

        self.inspection_completed_event.clear()
