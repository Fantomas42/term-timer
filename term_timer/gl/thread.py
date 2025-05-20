import logging
import threading

from term_timer.gl.cube import Cube
from term_timer.gl.renderer import render
from term_timer.gl.window import Window

logger = logging.getLogger(__name__)


class CubeGLThread(threading.Thread):
    def __init__(self, cube_ready_event, width=800, height=600,
                 daemon=True):
        super().__init__()

        self.cube_ready_event = cube_ready_event

        self.width = width
        self.height = height

        self.window = None
        self.cube = None
        self.running = True
        self.daemon = daemon

        self.title = ''
        self.move_queue = []
        self.move_lock = threading.Lock()
        self.last_quaternion = None
        self.has_new_quaternion = True

    def stop(self):
        self.running = False

    def run(self):
        logger.info('Waiting for bluetooth connection')
        self.cube_ready_event.wait()
        logger.info('Bluetooth connection established')

        self.window = Window(width=self.width, height=self.height, fps=144)
        self.window.title_prefix = self.title
        self.cube = Cube()

        while self.running:
            self.process_moves()
            self.process_quaternion()

            self.window.prepare()
            render(self.cube)
            self.window.update()

        self.window.quit()

    def process_moves(self):
        moves_to_process = []

        with self.move_lock:
            if self.move_queue:
                moves_to_process = self.move_queue.copy()
                self.move_queue.clear()

        for face, direction in moves_to_process:
            self.cube.animate_moves(self.window, [(face, direction)])

    def add_move(self, face, direction):
        with self.move_lock:
            self.move_queue.append((face, direction))

    def process_quaternion(self):
        quaternion = None
        with self.move_lock:
            if self.has_new_quaternion:
                quaternion = self.last_quaternion
                self.has_new_quaternion = False

        if quaternion:
            self.cube.set_rotation_from_quaternion(quaternion)

    def add_quaternion(self, quaternion):
        with self.move_lock:
            self.last_quaternion = quaternion
            self.has_new_quaternion = True

    def set_title(self, title):
        with self.move_lock:
            self.title = title

        if self.window:
            self.window.title_prefix = self.title
