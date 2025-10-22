import math

import numpy as np
from numpy.typing import NDArray

from term_timer.bluetooth.types import QuaternionDict
from term_timer.opengl import renderer
from term_timer.opengl.data import corner_orientations
from term_timer.opengl.data import corner_permutations
from term_timer.opengl.data import edge_orientations
from term_timer.opengl.data import edge_permutations
from term_timer.opengl.window import Window


class Cube:

    def __init__(self) -> None:
        self.edge_permutation = list(range(12))
        self.corner_permutation = list(range(8))

        self.edges_orientations = [0] * 12
        self.corners_orientations = [0] * 8

        self.rotation_matrix: NDArray[np.float64] = np.eye(3, dtype=np.float64)

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

        if abs(r[2][0]) != 1:
            theta_y = -math.asin(r[2][0])
            theta_x = math.atan2(
                r[2][1] / math.cos(theta_y),
                r[2][2] / math.cos(theta_y),
            )
            theta_z = math.atan2(
                r[1][0] / math.cos(theta_y),
                r[0][0] / math.cos(theta_y),
            )
        else:
            theta_z = 0.0
            if r[2][0] == -1:
                theta_y = math.pi / 2
                theta_x = theta_z + math.atan2(r[0][1], r[0][2])
            else:
                theta_y = -math.pi / 2
                theta_x = -theta_z + math.atan2(-r[0][1], -r[0][2])

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
        qw, qx, qy, qz = q['w'], q['x'], q['z'], -q['y']

        self.rotation_matrix = np.array([
            [
                1 - 2 * qy * qy - 2 * qz * qz,
                2 * qx * qy - 2 * qz * qw,
                2 * qx * qz + 2 * qy * qw,
            ],
            [
                2 * qx * qy + 2 * qz * qw,
                1 - 2 * qx * qx - 2 * qz * qz,
                2 * qy * qz - 2 * qx * qw,
            ],
            [
                2 * qx * qz - 2 * qy * qw,
                2 * qy * qz + 2 * qx * qw,
                1 - 2 * qx * qx - 2 * qy * qy,
            ],
        ], dtype=np.float64)


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
