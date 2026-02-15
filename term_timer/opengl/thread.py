"""Threading support for OpenGL visualization window."""
import logging
import threading
from typing import Final

import pygame
from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glPopMatrix
from OpenGL.GL import glPushMatrix
from OpenGL.GL import glScalef

from term_timer.bluetooth.annotations import CubeStateDict
from term_timer.bluetooth.annotations import QuaternionDict
from term_timer.constants import Face
from term_timer.opengl.cube import Cube
from term_timer.opengl.renderer import render
from term_timer.opengl.text_renderer import WAITING_MESSAGE_FONT_SIZE
from term_timer.opengl.text_renderer import render_waiting_message
from term_timer.opengl.window import Window
from term_timer.orientation import get_orientation_moves

logger = logging.getLogger(__name__)

# Constant for cube ready check timeout
CUBE_READY_CHECK_TIMEOUT: Final = 0.016  # ~60fps


class CubeGLThread(threading.Thread):
    """
    Thread that manages OpenGL cube visualization with async updates.

    Runs an OpenGL window in a separate thread to render a 3D Rubik's cube
    visualization. Supports real-time cube state updates, move animations,
    and quaternion-based rotation from Bluetooth cube input.
    """

    def __init__(
            self,
            cube_ready_event: threading.Event,
            orientation_faces: str,
            width: int = 800,
            height: int = 600,
            *,
            daemon: bool = True,
    ) -> None:
        """
        Initialize the OpenGL cube visualization thread.

        Args:
            cube_ready_event: Event signaling when cube is ready to render.
            orientation_faces: Two-character string defining cube orientation
                (e.g., 'UF' for up-front).
            width: Window width in pixels.
            height: Window height in pixels.
            daemon: Whether to run as daemon thread.

        """
        super().__init__(daemon=daemon)

        self.cube_ready_event = cube_ready_event
        self.orientation_faces = orientation_faces
        self.orientation_moves = get_orientation_moves(orientation_faces)

        self.width = width
        self.height = height

        self.window: Window | None = None
        self.cube: Cube | None = None
        self.running = True

        self.title = ''
        self.move_queue: list[tuple[Face, int]] = []
        self.move_lock = threading.Lock()
        self.last_quaternion: QuaternionDict | None = None
        self.has_new_quaternion = True
        self.font: pygame.font.Font | None = None
        self.cube_scale = 0.0
        self.is_animating_entrance = False
        self.pending_state: CubeStateDict | None = None

    def stop(self) -> None:
        """Signals the thread to stop running and exit the render loop."""
        self.running = False

    def run(self) -> None:
        """
        Execute the main render loop for the OpenGL visualization.

        Initializes the window and font, then enters a render loop that waits
        for cube readiness, processes moves and quaternions, animates entrance
        effects, and updates the display until stopped.
        """
        logger.info('Starting OpenGL window')
        self.window = Window(width=self.width, height=self.height, fps=144)
        self.window.title_prefix = self.title

        pygame.font.init()
        self.font = pygame.font.Font(None, WAITING_MESSAGE_FONT_SIZE)

        while self.running:
            if not self.cube_ready_event.is_set():
                self.window.handle_events()
                render_waiting_message(self.window, self.font)
                self.window.update()

                # Check if cube is ready with non-blocking timeout
                if self.cube_ready_event.wait(timeout=CUBE_READY_CHECK_TIMEOUT):
                    logger.info('Bluetooth connection established')
                    # Get state if available
                    state = None
                    with self.move_lock:
                        state = self.pending_state

                    # Initialize cube with state
                    if state:
                        self.cube = Cube(state, self.orientation_moves)
                        self.is_animating_entrance = True
                        self.cube_scale = 0.0
            else:
                self.process_moves()
                self.process_quaternion()

                # Animate entrance if needed
                if self.is_animating_entrance:
                    self.cube_scale = min(1.0, self.cube_scale + 0.05)
                    if self.cube_scale >= 1.0:
                        self.is_animating_entrance = False

                self.window.prepare()
                if self.cube:
                    self.render_cube_with_scale()
                self.window.update()

        self.window.quit()

    def process_moves(self) -> None:
        """
        Process queued cube moves and animate them on the display.

        Retrieves all pending moves from the thread-safe queue and applies
        them to the cube with animation if cube and window are available.
        """
        moves_to_process: list[tuple[Face, int]] = []

        with self.move_lock:
            if self.move_queue:
                moves_to_process = self.move_queue.copy()
                self.move_queue.clear()

        if self.cube and self.window:
            for face, direction in moves_to_process:
                self.cube.animate_moves(self.window, [(face, direction)])

    def add_move(self, face: Face, direction: int) -> None:
        """
        Add a cube move to the animation queue.

        Args:
            face: The face to rotate.
            direction: Rotation direction (1 for clockwise, -1 for
                counterclockwise, 2 for 180 degrees).

        """
        with self.move_lock:
            self.move_queue.append((face, direction))

    def process_quaternion(self) -> None:
        """
        Apply the latest quaternion rotation to the cube.

        Retrieves the most recent quaternion from the thread-safe queue and
        updates the cube's rotation if a new quaternion is available.
        """
        quaternion: QuaternionDict | None = None
        with self.move_lock:
            if self.has_new_quaternion:
                quaternion = self.last_quaternion
                self.has_new_quaternion = False

        if quaternion and self.cube:
            self.cube.set_rotation_from_quaternion(quaternion)

    def add_quaternion(self, quaternion: QuaternionDict) -> None:
        """
        Update the cube rotation using a quaternion from the smart cube.

        Args:
            quaternion: Quaternion representing the cube's physical
                orientation.

        """
        with self.move_lock:
            self.last_quaternion = quaternion
            self.has_new_quaternion = True

    def set_title(self, title: str) -> None:
        """
        Update the window title prefix.

        Args:
            title: New title prefix to display in the window.

        """
        with self.move_lock:
            self.title = title

        if self.window:
            self.window.title_prefix = self.title

    def set_state(self, state: CubeStateDict) -> None:
        """Set the cube state (permutations) to initialize the cube with."""
        with self.move_lock:
            self.pending_state = state

    def render_cube_with_scale(self) -> None:
        """Render the cube with current scale transformation."""
        if not self.cube:
            return

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glScalef(self.cube_scale, self.cube_scale, self.cube_scale)
        render(self.cube)
        glPopMatrix()
