import logging
import threading

from term_timer.gl.cube import Cube
from term_timer.gl.renderer import render
from term_timer.gl.window import Window

logger = logging.getLogger(__name__)


class CubeGLThread(threading.Thread):
    def __init__(self, cube_ready_event, width=800, height=600, daemon=True):
        super().__init__()

        self.cube_ready_event = cube_ready_event

        self.width = width
        self.height = height

        self.window = None
        self.cube = None
        self.running = True
        self.daemon = daemon

        self.move_queue = []
        self.move_lock = threading.Lock()

    def stop(self):
        self.running = False

    def run(self):
        logger.info('Waiting for bluetooth connection')
        self.cube_ready_event.wait()
        logger.info('Bluetooth connection established')

        self.window = Window(width=self.width, height=self.height, fps=144)
        self.cube = Cube()

        # self.window.add_event_rotations(self.cube)

        while self.running:
            # Traiter les mouvements provenant du Bluetooth (non-bloquant)
            self.process_moves()

            self.window.prepare()
            render(self.cube)
            self.window.update()

        self.window.quit()

    def process_moves(self):
        """Traite les mouvements en attente de manière non-bloquante"""
        moves_to_process = []

        with self.move_lock:
            if self.move_queue:
                moves_to_process = self.move_queue.copy()
                self.move_queue.clear()

        for face, direction in moves_to_process:
            logger.info(f"Thread OpenGL: Animation du mouvement {face}{'' if direction == 1 else '\''}")

            self.cube.animation(self.window, [(face, direction)])

    def add_move(self, face, direction):
        with self.move_lock:
            self.move_queue.append((face, direction))
