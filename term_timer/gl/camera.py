from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import glLoadIdentity
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glRotatef
from OpenGL.GL import glTranslatef


class Camera:

    def __init__(self):
        self.x, self.y, self.z = 0, 0, 0
        self.rot_x, self.rot_y, self.rot_z = 0, 0, 0

        # Attributs pour l'animation
        self.animation_queue = []
        self.animation_active = False
        self.current_step = 0
        self.animation_steps = 30  # Nombre d'étapes par défaut
        self.animation_x_step = 0
        self.animation_y_step = 0
        self.animation_z_step = 0

    def get_position(self):
        return self.x, self.y, self.z

    def get_rotation(self):
        return self.rot_x, self.rot_y, self.rot_z

    def increase_position(self, dx, dy, dz):
        self.x -= dx
        self.y -= dy
        self.z -= dz

    def increase_rotation(self, d_pitch, d_yaw, d_roll):
        self.rot_x -= d_pitch
        self.rot_y -= d_yaw
        self.rot_z -= d_roll

    def move(self):
        glTranslatef(self.x, self.y, self.z)

    def rotate(self):
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)
        glRotatef(self.rot_z, 0, 0, 1)

    def update(self):
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        self.move()
        self.rotate()
