import math
from typing import Final

import numpy as np
from cubing_algs.algorithm import Algorithm
from numpy.typing import NDArray

from term_timer.bluetooth.gyroscope import Quaternion
from term_timer.bluetooth.types import CubeStateDict
from term_timer.bluetooth.types import QuaternionDict
from term_timer.opengl import renderer
from term_timer.opengl.data import corner_orientations
from term_timer.opengl.data import corner_permutations
from term_timer.opengl.data import edge_orientations
from term_timer.opengl.data import edge_permutations
from term_timer.opengl.window import Window

# Gimbal lock threshold for Euler angle extraction
GIMBAL_LOCK_THRESHOLD: Final = 0.99999  # Near ±1 detection for r[2][0]


class Cube:

    def __init__(
            self,
            state: CubeStateDict | None = None,
            orientation_moves: Algorithm | None = None,
    ) -> None:
        if state:
            self.corner_permutation = list(state['CP'])
            self.corners_orientations = list(state['CO'])
            self.edge_permutation = list(state['EP'])
            self.edges_orientations = list(state['EO'])
        else:
            self.edge_permutation = list(range(12))
            self.corner_permutation = list(range(8))
            self.edges_orientations = [0] * 12
            self.corners_orientations = [0] * 8

        self.rotation_matrix: NDArray[np.float64] = np.eye(3, dtype=np.float64)

        # Apply orientation transformation if provided
        if orientation_moves:
            for orientation in orientation_moves:
                angle = 90
                if orientation.is_counter_clockwise:
                    angle = -90
                elif orientation.is_double:
                    angle = 180

                if orientation.base_move == 'x':
                    self.rotate_x(angle)
                elif orientation.base_move == 'y':
                    self.rotate_y(angle)
                else:
                    self.rotate_z(angle)

        # Initial orientation for normalizing quaternions
        # The first quaternion received becomes the reference orientation
        self.initial_orientation: Quaternion | None = None
        # Store the base orientation from orientation_moves to preserve it
        self.base_orientation_matrix: NDArray[np.float64] = (
            self.rotation_matrix.copy()
        )

    def __repr__(self) -> str:
        return (
            'Cube('
            f'edge_permutation={ self.edge_permutation!s }, '
            f'corner_permutation={ self.corner_permutation!s }) '
        )

    def __str__(self) -> str:
        return self.__repr__()

    def move_corners(self, move: str) -> None:
        p = self.corner_permutation
        move_p = corner_permutations[move]
        move_o = corner_orientations[move]

        self.corner_permutation = [p[move_p[i]] for i in range(8)]
        self.corners_orientations = [
            (self.corners_orientations[move_p[i]] + move_o[i]) % 3
            for i in range(8)
        ]

    def move_edges(self, move: str) -> None:
        p = self.edge_permutation
        move_p = edge_permutations[move]
        move_o = edge_orientations[move]

        self.edge_permutation = [p[move_p[i]] for i in range(12)]
        self.edges_orientations = [
            (self.edges_orientations[move_p[i]] + move_o[i]) % 2
            for i in range(12)
        ]

    def move(self, move: list[tuple[str, int]]) -> None:
        for (face, power) in move:
            for _i in range(power):
                self.move_corners(face)
                self.move_edges(face)

    def _rotation_matrix_x(self, angle_deg: float) -> NDArray[np.float64]:
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return np.array([
            [1.0, 0.0, 0.0],
            [0.0, cos_a, -sin_a],
            [0.0, sin_a, cos_a],
        ], dtype=np.float64)

    def _rotation_matrix_y(self, angle_deg: float) -> NDArray[np.float64]:
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return np.array([
            [cos_a, 0.0, sin_a],
            [0.0, 1.0, 0.0],
            [-sin_a, 0.0, cos_a],
        ], dtype=np.float64)

    def _rotation_matrix_z(self, angle_deg: float) -> NDArray[np.float64]:
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return np.array([
            [cos_a, -sin_a, 0.0],
            [sin_a, cos_a, 0.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

    def rotate_x(self, angle: float) -> None:
        rotation = self._rotation_matrix_x(-angle)
        self.rotation_matrix = rotation @ self.rotation_matrix

    def rotate_y(self, angle: float) -> None:
        rotation = self._rotation_matrix_y(-angle)
        self.rotation_matrix = rotation @ self.rotation_matrix

    def rotate_z(self, angle: float) -> None:
        rotation = self._rotation_matrix_z(-angle)
        self.rotation_matrix = rotation @ self.rotation_matrix

    def get_euler_angles(self) -> tuple[float, float, float]:
        r = self.rotation_matrix

        # Clamp r[2][0] to [-1, 1] to avoid numerical issues with asin
        sin_theta_y = max(-1.0, min(1.0, r[2][0]))

        # Check for gimbal lock (when pitch is near ±90°)
        if abs(sin_theta_y) < GIMBAL_LOCK_THRESHOLD:
            # Normal case: no gimbal lock
            theta_y = -math.asin(sin_theta_y)

            # Use atan2 for better numerical stability
            theta_x = math.atan2(r[2][1], r[2][2])
            theta_z = math.atan2(r[1][0], r[0][0])
        else:
            # Gimbal lock case: pitch is ±90°
            # In this case, we can only determine the sum/difference of
            # roll and yaw, so we conventionally set one to zero
            theta_z = 0.0
            if sin_theta_y < 0:
                # Pitch = -90°
                theta_y = -math.pi / 2
                theta_x = -theta_z + math.atan2(-r[0][1], -r[0][2])
            else:
                # Pitch = +90°
                theta_y = math.pi / 2
                theta_x = theta_z + math.atan2(r[0][1], r[0][2])

        return (
            math.degrees(theta_x),
            math.degrees(theta_y),
            math.degrees(theta_z),
        )

    def animate_moves(self, window: Window,
                      moves: list[tuple[str, int]]) -> None:
        for (face, power) in moves:
            renderer.animate_move(window, self, face, power)
            self.move([(face, power)])

    def animate_rotations(self, window: Window, axis: str, angle: int) -> None:
        renderer.animate_rotation(window, self, axis, angle)

    def set_rotation_from_quaternion(self, q: QuaternionDict) -> None:
        """
        Set rotation from quaternion with automatic normalization.

        The first quaternion received becomes the reference orientation.
        All subsequent quaternions are normalized relative to this initial
        orientation, similar to RotationDetector.process_gyro_event().
        """
        # Convert raw quaternion dict to Quaternion object
        absolute_raw = Quaternion.from_dict_raw(q)

        # Initialize with first quaternion as neutral orientation
        if self.initial_orientation is None:
            self.initial_orientation = absolute_raw
            # Keep the base orientation instead of resetting to identity
            self.rotation_matrix = self.base_orientation_matrix.copy()
            return

        # Normalize in raw sensor frame: q_normalized = q_initial^-1 * q_current
        # This matches the logic in gyroscope.py:201-205
        current_orientation = self.initial_orientation.conjugate().multiply(
            absolute_raw,
        ).normalize()

        # Apply coordinate transformation: Y↔Z swap for display coordinates
        # This transforms from sensor frame to display frame
        qw = current_orientation.w
        qx = current_orientation.x
        qy = current_orientation.z
        qz = -current_orientation.y

        # Convert display-frame quaternion to rotation matrix
        # Pre-compute common subexpressions for efficiency
        qx2 = qx * qx
        qy2 = qy * qy
        qz2 = qz * qz
        qxy = qx * qy
        qxz = qx * qz
        qyz = qy * qz
        qwx = qw * qx
        qwy = qw * qy
        qwz = qw * qz

        gyro_rotation_matrix = np.array([
            [
                1 - 2 * (qy2 + qz2),
                2 * (qxy - qwz),
                2 * (qxz + qwy),
            ],
            [
                2 * (qxy + qwz),
                1 - 2 * (qx2 + qz2),
                2 * (qyz - qwx),
            ],
            [
                2 * (qxz - qwy),
                2 * (qyz + qwx),
                1 - 2 * (qx2 + qy2),
            ],
        ], dtype=np.float64)

        # Combine with base orientation: first apply gyro, then base
        # Matrix multiplication: base * gyro
        self.rotation_matrix = (
            self.base_orientation_matrix @ gyro_rotation_matrix
        )


def main(cube: Cube) -> None:
    window = Window(
        1024, 720,
        fps=144,
    )
    window.set_keyboard_events(cube)

    count = 0

    while True:
        window.prepare()
        renderer.render(cube)
        window.update()

        if count < 2:
            count += 1
            cube.animate_rotations(window, 'z', 90)

    window.quit()


if __name__ == '__main__':
    main(Cube())
