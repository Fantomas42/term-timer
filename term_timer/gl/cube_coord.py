from term_timer.gl import renderer
from term_timer.gl.data import orientations_aretes
from term_timer.gl.data import orientations_coins
from term_timer.gl.data import permutations_aretes
from term_timer.gl.data import permutations_coins


def binomial(n, k):
    """
    A fast way to calculate binomial coefficients by Andrew Dalke.
    See http://stackoverflow.com/questions/3025162/statistics-combinations-in-python
    """
    if 0 <= k <= n:
        ntok = 1
        ktok = 1
        for t in range(1, min(k, n - k) + 1):
            ntok *= n
            ktok *= t
            n -= 1
        return ntok // ktok

    return 0


class Cube:

    def __init__(self):
        self.edge_permutation = list(range(12))
        self.corner_permutation = list(range(8))

        self.edges_orientations = [0] * 12
        self.corners_orientations = [0] * 8

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

    def move_corners(self, mvt):
        p = self.corner_permutation
        mvtp = permutations_coins[mvt]
        mvto = orientations_coins[mvt]

        self.corner_permutation = [p[mvtp[i]] for i in range(8)]
        self.corners_orientations = [
            (self.corners_orientations[mvtp[i]] + mvto[i]) % 3
            for i in range(8)
        ]

    def move_edges(self, mvt):
        p = self.edge_permutation
        mvtp = permutations_aretes[mvt]
        mvto = orientations_aretes[mvt]

        self.edge_permutation = [p[mvtp[i]] for i in range(12)]
        self.edges_orientations = [
            (self.edges_orientations[mvtp[i]] + mvto[i]) % 2
            for i in range(12)
        ]

    def rotate(self, mvt):
        for (face, power) in mvt:
            for _i in range(power):
                self.move_corners(face)
                self.move_edges(face)

    def animation(self, fenetre, liste_mouvements):
        for (face, power) in liste_mouvements:
            renderer.anim_rotation(fenetre, self, face, power)
            self.rotate([(face, power)])
