"""OpenGL camera controls for 3D cube visualization."""

from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import glLoadIdentity
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glRotatef
from OpenGL.GL import glTranslatef


class Camera:
    """
    Manage camera position and rotation for OpenGL 3D visualization.

    The camera controls the view transformation in the 3D scene, allowing
    movement along three axes and rotation around pitch, yaw, and roll axes.
    """

    def __init__(self) -> None:
        """Initialize the camera at origin with zero rotation."""
        self.x, self.y, self.z = 0.0, 0.0, 0.0
        self.rot_x, self.rot_y, self.rot_z = 0.0, 0.0, 0.0

    def get_position(self) -> tuple[float, float, float]:
        """
        Return the current camera position in 3D space.

        Returns:
            A tuple of (x, y, z) coordinates representing the camera
            position.

        """
        return self.x, self.y, self.z

    def get_rotation(self) -> tuple[float, float, float]:
        """
        Return the current camera rotation angles.

        Returns:
            A tuple of (pitch, yaw, roll) angles in degrees for rotation
            around the x, y, and z axes respectively.

        """
        return self.rot_x, self.rot_y, self.rot_z

    def increase_position(self, dx: float, dy: float, dz: float) -> None:
        """
        Adjust the camera position by specified deltas.

        Note: The method name suggests increasing, but implementation
        subtracts the deltas to achieve proper camera movement direction.

        Args:
            dx: Delta to apply to x position.
            dy: Delta to apply to y position.
            dz: Delta to apply to z position.

        """
        self.x -= dx
        self.y -= dy
        self.z -= dz

    def increase_rotation(self,
                          d_pitch: float,
                          d_yaw: float,
                          d_roll: float) -> None:
        """
        Adjust the camera rotation by specified angle deltas.

        Note: The method name suggests increasing, but implementation
        subtracts the deltas to achieve proper rotation direction.

        Args:
            d_pitch: Delta angle in degrees for pitch (rotation around
                x-axis).
            d_yaw: Delta angle in degrees for yaw (rotation around y-axis).
            d_roll: Delta angle in degrees for roll (rotation around
                z-axis).

        """
        self.rot_x -= d_pitch
        self.rot_y -= d_yaw
        self.rot_z -= d_roll

    def move(self) -> None:
        """Apply the camera translation to the OpenGL modelview matrix."""
        glTranslatef(self.x, self.y, self.z)

    def rotate(self) -> None:
        """
        Apply the camera rotation to the OpenGL modelview matrix.

        Rotations are applied in order: pitch (x-axis), yaw (y-axis),
        then roll (z-axis).
        """
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)
        glRotatef(self.rot_z, 0, 0, 1)

    def update(self) -> None:
        """
        Update the OpenGL modelview matrix with camera transformations.

        Reset the modelview matrix to identity and apply the camera's
        translation and rotation transformations in sequence.
        """
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        self.move()
        self.rotate()
