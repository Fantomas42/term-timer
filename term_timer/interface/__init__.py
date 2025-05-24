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
    pass
