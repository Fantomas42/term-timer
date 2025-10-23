from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
from OpenGL.GL import GL_AMBIENT
from OpenGL.GL import GL_AMBIENT_AND_DIFFUSE
from OpenGL.GL import GL_BGRA
from OpenGL.GL import GL_COLOR_BUFFER_BIT
from OpenGL.GL import GL_COLOR_MATERIAL
from OpenGL.GL import GL_DEPTH_BUFFER_BIT
from OpenGL.GL import GL_DEPTH_TEST
from OpenGL.GL import GL_DIFFUSE
from OpenGL.GL import GL_FRONT_AND_BACK
from OpenGL.GL import GL_LIGHT0
from OpenGL.GL import GL_LIGHTING
from OpenGL.GL import GL_LINEAR
from OpenGL.GL import GL_LINEAR_MIPMAP_LINEAR
from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import GL_POSITION
from OpenGL.GL import GL_PROJECTION
from OpenGL.GL import GL_QUADS
from OpenGL.GL import GL_RESCALE_NORMAL
from OpenGL.GL import GL_SHININESS
from OpenGL.GL import GL_SPECULAR
from OpenGL.GL import GL_TEXTURE_2D
from OpenGL.GL import GL_TEXTURE_MAG_FILTER
from OpenGL.GL import GL_TEXTURE_MIN_FILTER
from OpenGL.GL import GL_UNSIGNED_BYTE
from OpenGL.GL import glBegin
from OpenGL.GL import glBindTexture
from OpenGL.GL import glClear
from OpenGL.GL import glClearColor
from OpenGL.GL import glColor3f
from OpenGL.GL import glColorMaterial
from OpenGL.GL import glDisable
from OpenGL.GL import glEnable
from OpenGL.GL import glEnd
from OpenGL.GL import glGenTextures
from OpenGL.GL import glLightfv
from OpenGL.GL import glLoadIdentity
from OpenGL.GL import glMaterialfv
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glPopMatrix
from OpenGL.GL import glPushMatrix
from OpenGL.GL import glTexParameterf
from OpenGL.GL import glVertex2f
from OpenGL.GLU import gluBuild2DMipmaps
from OpenGL.GLU import gluPerspective
from pygame import DOUBLEBUF
from pygame import FULLSCREEN
from pygame import K_DOWN
from pygame import K_ESCAPE
from pygame import K_LEFT
from pygame import K_RIGHT
from pygame import K_UP
from pygame import KEYDOWN
from pygame import KEYUP
from pygame import OPENGL
from pygame import K_b
from pygame import K_d
from pygame import K_f
from pygame import K_l
from pygame import K_r
from pygame import K_u
from pygame import K_x
from pygame import K_y
from pygame import K_z

from term_timer.opengl.camera import Camera

if TYPE_CHECKING:
    from term_timer.opengl.cube import Cube


class Window:

    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        fps: int = 60,
        *,
        fullscreen: bool = False,
    ) -> None:
        self.fps = fps
        self.camera = Camera()
        self.events: dict[
            tuple[int, int],
            tuple[Callable[..., None], tuple[object, ...]]] = {}

        self.clock = pygame.time.Clock()

        self.horizontal_rotation = 0
        self.vertical_rotation = 0

        self.title_prefix = 'Cube 3D'

        pygame.display.init()

        if (width, height) == (0, 0):
            self.display = (
                pygame.display.Info().current_w,
                pygame.display.Info().current_h,
            )
        else:
            self.display = (width, height)
        if fullscreen:
            pygame.display.set_mode(
                self.display,
                DOUBLEBUF | OPENGL | FULLSCREEN,
            )
        else:
            pygame.display.set_mode(
                self.display,
                DOUBLEBUF | OPENGL,
            )
        pygame.display.set_caption('Cube 3D')
        pygame.mouse.set_visible(True)

        glMatrixMode(GL_PROJECTION)
        # Dark neutral background (will be enhanced with gradient)
        glClearColor(0.08, 0.08, 0.12, 1.0)
        glLoadIdentity()
        gluPerspective(50, (self.display[0] / self.display[1]), 0.1, 50.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.camera.increase_position(0, 0, 12)
        self.camera.increase_rotation(-30, 0, 0)
        self.camera.update()

        glEnable(GL_DEPTH_TEST)

        # Enable lighting for realistic 3D appearance
        self.setup_lighting()

        self.load_texture(Path(__file__).parent / 'facelet.bmp')

    def setup_lighting(self) -> None:
        """Setup OpenGL lighting for realistic 3D cube appearance."""
        # Enable lighting
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

        # Enable automatic normal rescaling after transformations
        # GL_RESCALE_NORMAL is faster than GL_NORMALIZE because
        # uses uniform scale factor. Since we only rotate
        # (no non-uniform scaling), this is sufficient
        glEnable(GL_RESCALE_NORMAL)

        # Ambient light - higher for softer, more natural appearance
        # Prevents faces from being too dark
        ambient_light = [0.5, 0.5, 0.5, 1.0]
        glLightfv(GL_LIGHT0, GL_AMBIENT, ambient_light)

        # Diffuse light - moderate for subtle depth without harsh shadows
        diffuse_light = [0.6, 0.6, 0.6, 1.0]
        glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse_light)

        # Specular light - strong for pronounced glossy highlights
        specular_light = [0.8, 0.8, 0.8, 1.0]
        glLightfv(GL_LIGHT0, GL_SPECULAR, specular_light)

        # Light position - from above and slightly to side for natural look
        # Not too extreme to avoid harsh shadows
        light_position = [3.0, 8.0, 5.0, 1.0]
        glLightfv(GL_LIGHT0, GL_POSITION, light_position)

        # Material properties - very high shininess for glossy speedcube plastic
        # Higher values create more pronounced, tighter specular highlights
        specular_material = [1.0, 1.0, 1.0, 1.0]
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, specular_material)
        glMaterialfv(GL_FRONT_AND_BACK, GL_SHININESS, [80.0])

    def load_texture(self, filename: Path) -> None:
        texture_surface = pygame.image.load(filename)
        texture_data = pygame.image.tostring(
            texture_surface, 'RGBA', True,  # noqa: FBT003
        )

        self.texID = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texID)
        gluBuild2DMipmaps(
            GL_TEXTURE_2D, 4,
            texture_surface.get_width(),
            texture_surface.get_height(),
            GL_BGRA, GL_UNSIGNED_BYTE,
            texture_data,
        )
        glTexParameterf(
            GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
        )
        glTexParameterf(
            GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR,
        )

    def render_gradient_background(self) -> None:
        """Render a subtle gradient background for better aesthetics."""
        # Save current matrices
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        # Disable lighting and depth test for background
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        # Draw synthwave/80s style gradient (cyan/blue to purple)
        glBegin(GL_QUADS)
        # Bottom - dark cyan/blue (retro horizon)
        glColor3f(0.03, 0.08, 0.20)
        glVertex2f(-1.0, -1.0)
        glVertex2f(1.0, -1.0)
        # Top - deep purple/magenta (synthwave sky)
        glColor3f(0.12, 0.03, 0.18)
        glVertex2f(1.0, 1.0)
        glVertex2f(-1.0, 1.0)
        glEnd()

        # Re-enable lighting and depth test
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

        # Restore matrices
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def prepare(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Render gradient background
        self.render_gradient_background()

        self.handle_events()
        self.handle_camera()

    def update(self) -> None:
        pygame.display.flip()

        self.clock.tick(self.fps)

        pygame.display.set_caption(
            f'{ self.title_prefix } (FPS={ int(self.clock.get_fps())!s })',
        )

    def quit(self) -> None:
        pygame.quit()

    def set_keyboard_events(self, cube: 'Cube') -> None:
        self.add_event(KEYDOWN, K_ESCAPE, self.quit)
        self.add_event(KEYDOWN, K_LEFT, self.set_horizontal_rotation, 1)
        self.add_event(KEYDOWN, K_RIGHT, self.set_horizontal_rotation, -1)
        self.add_event(KEYDOWN, K_UP, self.set_vertical_rotation, 1)
        self.add_event(KEYDOWN, K_DOWN, self.set_vertical_rotation, -1)

        self.add_event(KEYUP, K_LEFT, self.set_horizontal_rotation, -1)
        self.add_event(KEYUP, K_RIGHT, self.set_horizontal_rotation, 1)
        self.add_event(KEYUP, K_UP, self.set_vertical_rotation, -1)
        self.add_event(KEYUP, K_DOWN, self.set_vertical_rotation, 1)

        self.add_event(KEYDOWN, K_u, cube.animate_moves, self, [('U', 1)])
        self.add_event(KEYDOWN, K_d, cube.animate_moves, self, [('D', 1)])
        self.add_event(KEYDOWN, K_r, cube.animate_moves, self, [('R', 1)])
        self.add_event(KEYDOWN, K_l, cube.animate_moves, self, [('L', 1)])
        self.add_event(KEYDOWN, K_f, cube.animate_moves, self, [('F', 1)])
        self.add_event(KEYDOWN, K_b, cube.animate_moves, self, [('B', 1)])

        self.add_event(KEYDOWN, K_x, cube.animate_rotations, self, 'x', 90)
        self.add_event(KEYDOWN, K_y, cube.animate_rotations, self, 'y', 90)
        self.add_event(KEYDOWN, K_z, cube.animate_rotations, self, 'z', 90)

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type in {KEYDOWN, KEYUP}:
                event_key = (event.type, event.key)
                if event_key in self.events:
                    f, args = self.events[event_key]
                    f(*args)

    def add_event(
        self,
        event_type: int,
        key: int,
        f: Callable[..., None],
        *args: object,
    ) -> None:
        self.events[event_type, key] = (f, args)

    def set_horizontal_rotation(self, value: int) -> None:
        self.horizontal_rotation += value

    def set_vertical_rotation(self, value: int) -> None:
        self.vertical_rotation += value

    def handle_camera(self) -> None:
        self.camera.increase_rotation(
            self.vertical_rotation,
            self.horizontal_rotation,
            0,
        )

        self.camera.update()
