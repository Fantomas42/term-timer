import logging
import threading

from term_timer.bluetooth.types import QuaternionDict
from term_timer.opengl.cube import Cube
from term_timer.opengl.renderer import render
from term_timer.opengl.window import Window

logger = logging.getLogger(__name__)


class CubeGLThread(threading.Thread):
    def __init__(
        self,
        cube_ready_event: threading.Event,
        width: int = 800,
        height: int = 600,
        *,
        daemon: bool = True,
    ) -> None:
        super().__init__(daemon=daemon)

        self.cube_ready_event = cube_ready_event

        self.width = width
        self.height = height

        self.window: Window | None = None
        self.cube: Cube | None = None
        self.running = True

        self.title = ''
        self.move_queue: list[tuple[str, int]] = []
        self.move_lock = threading.Lock()
        self.last_quaternion: QuaternionDict | None = None
        self.has_new_quaternion = True

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
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

    def process_moves(self) -> None:
        moves_to_process: list[tuple[str, int]] = []

        with self.move_lock:
            if self.move_queue:
                moves_to_process = self.move_queue.copy()
                self.move_queue.clear()

        if self.cube and self.window:
            for face, direction in moves_to_process:
                self.cube.animate_moves(self.window, [(face, direction)])

    def add_move(self, face: str, direction: int) -> None:
        with self.move_lock:
            self.move_queue.append((face, direction))

    def process_quaternion(self) -> None:
        quaternion: QuaternionDict | None = None
        with self.move_lock:
            if self.has_new_quaternion:
                quaternion = self.last_quaternion
                self.has_new_quaternion = False

        if quaternion and self.cube:
            self.cube.set_rotation_from_quaternion(quaternion)

    def add_quaternion(self, quaternion: QuaternionDict) -> None:
        with self.move_lock:
            self.last_quaternion = quaternion
            self.has_new_quaternion = True

    def set_title(self, title: str) -> None:
        with self.move_lock:
            self.title = title

        if self.window:
            self.window.title_prefix = self.title
