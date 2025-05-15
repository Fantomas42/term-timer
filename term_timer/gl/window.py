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
from pygame import K_y
from pygame import K_z

from term_timer.gl.camera import Camera


class Window:

    def __init__(self, width=0, height=0,
                 fps=60, fullscreen=False):
        self.fps = fps
        self.camera = Camera()
        self.events = {}
        self.setup_events()

        self.animation_queue = []
        self.animation_active = False

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
        glClearColor(13 / 0xFF, 26 / 0xFF, 74 / 0xFF, 1.0)
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

        self.add_event(KEYDOWN, K_x, self.queue_camera_animation, 90, 0, 0)
        self.add_event(KEYDOWN, K_y, self.queue_camera_animation, 0, 90, 0)
        self.add_event(KEYDOWN, K_z, self.queue_camera_animation, 0, 0, 90)

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

        # Gérer l'animation si elle est active
        if self.animation_active:
            if self.current_step < self.animation_steps:
                # Appliquer une étape de l'animation
                self.camera.increase_rotation(
                    self.animation_x_step,
                    self.animation_y_step,
                    self.animation_z_step,
                )
                self.current_step += 1
            else:
                # Fin de l'animation actuelle
                self.animation_active = False
                # Démarrer la prochaine animation s'il y en a
                self.start_next_animation()

        self.camera.update()

    def queue_camera_animation(self, x_angle, y_angle, z_angle):
        # Ajouter l'animation à la file d'attente
        self.animation_queue.append((x_angle, y_angle, z_angle))

        # Si aucune animation n'est en cours, démarrer celle-ci
        if not self.animation_active:
            self.start_next_animation()

    def start_next_animation(self):
        # S'il y a des animations en attente, démarrer la prochaine
        if self.animation_queue:
            # Récupérer la prochaine animation
            x_angle, y_angle, z_angle = self.animation_queue.pop(0)

            # Configuration de l'animation
            self.animation_active = True
            self.animation_steps = 30  # Nombre total d'étapes pour l'animation
            self.current_step = 0

            # Angles à atteindre pour chaque étape
            self.animation_x_step = x_angle / self.animation_steps
            self.animation_y_step = y_angle / self.animation_steps
            self.animation_z_step = z_angle / self.animation_steps
