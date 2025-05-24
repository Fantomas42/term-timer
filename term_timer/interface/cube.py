from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import remove_final_rotations

from term_timer.config import CUBE_ORIENTATION


class Orienter:
    cube_orientation = CUBE_ORIENTATION

    def reorient(self, algorithm: Algorithm) -> Algorithm:
        if self.cube_orientation:
            new_algorithm = self.cube_orientation + algorithm
            return new_algorithm.transform(
                degrip_full_moves,
                remove_final_rotations,
            )

        return algorithm
