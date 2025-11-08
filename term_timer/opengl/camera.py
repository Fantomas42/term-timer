"""OpenGL camera controls for 3D cube visualization."""

from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import glLoadIdentity
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glRotatef
from OpenGL.GL import glTranslatef


class Camera:

    def __init__(self) -> None:
        self.x, self.y, self.z = 0.0, 0.0, 0.0
        self.rot_x, self.rot_y, self.rot_z = 0.0, 0.0, 0.0

    def get_position(self) -> tuple[float, float, float]:
        return self.x, self.y, self.z

    def get_rotation(self) -> tuple[float, float, float]:
        return self.rot_x, self.rot_y, self.rot_z

    def increase_position(self, dx: float, dy: float, dz: float) -> None:
        self.x -= dx
        self.y -= dy
        self.z -= dz

    def increase_rotation(self,
                          d_pitch: float,
                          d_yaw: float,
                          d_roll: float) -> None:
        self.rot_x -= d_pitch
        self.rot_y -= d_yaw
        self.rot_z -= d_roll

    def move(self) -> None:
        glTranslatef(self.x, self.y, self.z)

    def rotate(self) -> None:
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)
        glRotatef(self.rot_z, 0, 0, 1)

    def update(self) -> None:
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        self.move()
        self.rotate()
