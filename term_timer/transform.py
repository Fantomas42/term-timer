from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.fat import refat_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_moves
from cubing_algs.transform.timing import untime_moves


def reorient_moves(orientation: Algorithm, algorithm: Algorithm) -> Algorithm:
    if orientation:
        new_algorithm = orientation + algorithm
        return new_algorithm.transform(
            degrip_full_moves,
            remove_final_rotations,
        )

    return algorithm


def humanize_moves(algorithm: Algorithm) -> Algorithm:
    # Note this will work until orientation move are implemented
    return algorithm.transform(
        reslice_moves,
        degrip_full_moves,
        refat_moves,
        remove_final_rotations,
        to_fixpoint=True,
    )


def prettify_moves(algorithm: Algorithm) -> Algorithm:
    return algorithm.transform(
        untime_moves,
        optimize_double_moves,
    )
