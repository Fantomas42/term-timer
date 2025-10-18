from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.slice import reslice_timed_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.transform.translate import translate_pov_moves
from cubing_algs.transform.wide import rewide_timed_moves

from term_timer.constants import RESLICE_THRESHOLD
from term_timer.constants import REWIDE_THRESHOLD


def humanize_moves(algorithm: Algorithm) -> Algorithm:
    return algorithm.transform(
        translate_pov_moves,
        reslice_timed_moves(RESLICE_THRESHOLD, (3,)),
        rewide_timed_moves(REWIDE_THRESHOLD),
    )


def prettify_moves(algorithm: Algorithm) -> Algorithm:
    return algorithm.transform(
        untime_moves,
        optimize_double_moves,
    )
