import pygame
from OpenGL.GL import GL_BGRA
from OpenGL.GL import GL_COLOR_BUFFER_BIT
from OpenGL.GL import GL_DEPTH_BUFFER_BIT
from OpenGL.GL import GL_DEPTH_TEST
from OpenGL.GL import GL_LINEAR
from OpenGL.GL import GL_LINEAR_MIPMAP_LINEAR
from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import GL_PROJECTION
from OpenGL.GL import GL_TEXTURE_2D
from OpenGL.GL import GL_TEXTURE_MAG_FILTER
from OpenGL.GL import GL_TEXTURE_MIN_FILTER
from OpenGL.GL import GL_UNSIGNED_BYTE
from OpenGL.GL import glBindTexture
from OpenGL.GL import glClear
from OpenGL.GL import glClearColor
from OpenGL.GL import glEnable
from OpenGL.GL import glGenTextures
from OpenGL.GL import glLoadIdentity
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glTexParameterf
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

from term_timer.gl.camera import Camera


class Window:

    def __init__(self, width=0, height=0,
                 fps=60, fullscreen=False):
        self.fps = fps
        self.camera = Camera()
        self.events = {}
        self.setup_events()

        self.clock = pygame.time.Clock()

        self.horizontal_rotation = 0
        self.vertical_rotation = 0

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
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glLoadIdentity()
        gluPerspective(50, (self.display[0] / self.display[1]), 0.1, 50.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.camera.increase_position(0, 0, 12)
        self.camera.increase_rotation(-30, 30, 0)
        self.camera.update()

        glEnable(GL_DEPTH_TEST)

        self.load_texture('facelet.bmp')

    def load_texture(self, filename):
        texture_surface = pygame.image.load(filename)
        texture_data = pygame.image.tostring(
            texture_surface, 'RGBA', True,
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

    def prepare(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.handle_events()
        self.handle_camera()

    def update(self):
        pygame.display.flip()

        self.clock.tick(self.fps)

        pygame.display.set_caption(
            'Cube 3D (FPS = ' + str(int(self.clock.get_fps())) + ')',
        )

    def quit(self):
        pygame.quit()

    def setup_events(self):
        self.add_event(KEYDOWN, K_ESCAPE, self.quit)
        self.add_event(KEYDOWN, K_LEFT, self.set_horizontal_rotation, 1)
        self.add_event(KEYDOWN, K_RIGHT, self.set_horizontal_rotation, -1)
        self.add_event(KEYDOWN, K_UP, self.set_vertical_rotation, 1)
        self.add_event(KEYDOWN, K_DOWN, self.set_vertical_rotation, -1)

        self.add_event(KEYUP, K_LEFT, self.set_horizontal_rotation, -1)
        self.add_event(KEYUP, K_RIGHT, self.set_horizontal_rotation, 1)
        self.add_event(KEYUP, K_UP, self.set_vertical_rotation, -1)
        self.add_event(KEYUP, K_DOWN, self.set_vertical_rotation, 1)

    def add_event_rotations(self, cube):
        self.add_event(KEYDOWN, K_u, cube.animation, self, [('U', 1)])
        self.add_event(KEYDOWN, K_d, cube.animation, self, [('D', 1)])
        self.add_event(KEYDOWN, K_r, cube.animation, self, [('R', 1)])
        self.add_event(KEYDOWN, K_l, cube.animation, self, [('L', 1)])
        self.add_event(KEYDOWN, K_f, cube.animation, self, [('F', 1)])
        self.add_event(KEYDOWN, K_b, cube.animation, self, [('B', 1)])

        #self.add_event(KEYDOWN, K_x, cube.animation, self, [('x', 1)])

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type in {KEYDOWN, KEYUP}:
                try:
                    f, args = self.events[event.type, event.key]
                except KeyError:
                    ...
                else:
                    f(*args)

    def add_event(self, event_type, key, f, *args):
        self.events[event_type, key] = (f, args)

    def set_horizontal_rotation(self, value):
        self.horizontal_rotation += value

    def set_vertical_rotation(self, value):
        self.vertical_rotation += value

    def handle_camera(self):
        self.camera.increase_rotation(
            self.vertical_rotation,
            self.horizontal_rotation,
            0,
        )
        self.camera.update()
