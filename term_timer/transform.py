from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.timing import untime_moves


def reorient_moves(orientation: Algorithm, algorithm: Algorithm) -> Algorithm:
    if orientation:
        new_algorithm = orientation + algorithm
        return new_algorithm.transform(
            degrip_full_moves,
            remove_final_rotations,
        )

    return algorithm


def pretty_moves(algorithm: Algorithm) -> Algorithm:
    return algorithm.transform(
        optimize_double_moves,
        untime_moves,
    )
