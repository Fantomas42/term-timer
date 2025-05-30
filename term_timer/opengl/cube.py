import math

from term_timer.opengl import renderer
from term_timer.opengl.data import orientations_aretes
from term_timer.opengl.data import orientations_coins
from term_timer.opengl.data import permutations_aretes
from term_timer.opengl.data import permutations_coins
from term_timer.opengl.window import Window


class Cube:

    def __init__(self):
        self.edge_permutation = list(range(12))
        self.corner_permutation = list(range(8))

        self.edges_orientations = [0] * 12
        self.corners_orientations = [0] * 8

        self.rotation_matrix = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]

    def __repr__(self):
        return (
            'Cube('
            f'edge_permutation={ self.edge_permutation!s }, '
            f'corner_permutation={ self.corner_permutation!s }) '
        )

    def __str__(self):
        return self.__repr__()

    def move_corners(self, move):
        p = self.corner_permutation
        move_p = permutations_coins[move]
        move_o = orientations_coins[move]

        self.corner_permutation = [p[move_p[i]] for i in range(8)]
        self.corners_orientations = [
            (self.corners_orientations[move_p[i]] + move_o[i]) % 3
            for i in range(8)
        ]

    def move_edges(self, move):
        p = self.edge_permutation
        move_p = permutations_aretes[move]
        move_o = orientations_aretes[move]

        self.edge_permutation = [p[move_p[i]] for i in range(12)]
        self.edges_orientations = [
            (self.edges_orientations[move_p[i]] + move_o[i]) % 2
            for i in range(12)
        ]

    def move(self, move):
        for (face, power) in move:
            for _i in range(power):
                self.move_corners(face)
                self.move_edges(face)

    def _rotation_matrix_x(self, angle_deg):
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return [
            [1.0, 0.0, 0.0],
            [0.0, cos_a, -sin_a],
            [0.0, sin_a, cos_a],
        ]

    def _rotation_matrix_y(self, angle_deg):
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return [
            [cos_a, 0.0, sin_a],
            [0.0, 1.0, 0.0],
            [-sin_a, 0.0, cos_a],
        ]

    def _rotation_matrix_z(self, angle_deg):
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return [
            [cos_a, -sin_a, 0.0],
            [sin_a, cos_a, 0.0],
            [0.0, 0.0, 1.0],
        ]

    def _matrix_multiply(self, a, b):
        c = [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    c[i][j] += a[i][k] * b[k][j]
        return c

    def rotate_x(self, angle):
        rotation = self._rotation_matrix_x(-angle)
        self.rotation_matrix = self._matrix_multiply(
            rotation, self.rotation_matrix,
        )

    def rotate_y(self, angle):
        rotation = self._rotation_matrix_y(-angle)
        self.rotation_matrix = self._matrix_multiply(
            rotation, self.rotation_matrix,
        )

    def rotate_z(self, angle):
        rotation = self._rotation_matrix_z(-angle)
        self.rotation_matrix = self._matrix_multiply(
            rotation, self.rotation_matrix,
        )

    def get_euler_angles(self):
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
            theta_z = 0
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

    def animate_moves(self, window, moves):
        for (face, power) in moves:
            renderer.animate_move(window, self, face, power)
            self.move([(face, power)])

    def animate_rotations(self, window, axis, angle):
        renderer.animate_rotation(window, self, axis, angle)

    def set_rotation_from_quaternion(self, q):
        qw, qx, qy, qz = q['w'], q['x'], q['z'], -q['y']

        self.rotation_matrix = [
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
        ]


def main(cube):
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
