import math

from term_timer.gl import renderer
from term_timer.gl.data import orientations_aretes
from term_timer.gl.data import orientations_coins
from term_timer.gl.data import permutations_aretes
from term_timer.gl.data import permutations_coins


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
            f'corner_permutation={ self.corner_permutation!s }, '
            f'twist={ self.get_twist() }, '
            f'flip={ self.get_flip() })'
        )

    def __str__(self):
        return self.__repr__()

    def get_twist(self):
        twist = 0
        for i in range(7):
            twist *= 3
            twist += self.corners_orientations[i]

        return twist

    def get_flip(self):
        flip = 0
        for i in range(11):
            flip *= 2
            flip += self.edges_orientations[i]

        return flip

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
        c = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
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
