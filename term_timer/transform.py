"""Algorithm transformation utilities for humanizing and prettifying moves."""
from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import compress_ending_rotations
from cubing_algs.transform.slice import reslice_timed_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.transform.translate import translate_pov_moves
from cubing_algs.transform.wide import rewide_moves
from cubing_algs.transform.wide import rewide_timed_moves

from term_timer.constants import RESLICE_THRESHOLD
from term_timer.constants import RESLICE_THRESHOLD_GYROSCOPE
from term_timer.constants import REWIDE_THRESHOLD_GYROSCOPE


def humanize_moves_without_rotation(
        algorithm: Algorithm,
        *, allow_ending_rotations: bool = True,
) -> Algorithm:
    """
    Transform to human-readable format.

    Returns:
        Humanized algorithm with resliced and rewide moves.

    """
    humanized = algorithm.transform(
        reslice_timed_moves(RESLICE_THRESHOLD, (2,)),
        degrip_full_moves,
        rewide_moves,
        compress_ending_rotations,
        to_fixpoint=True,
    )

    if (
            not allow_ending_rotations
            and humanized
            and humanized[-1].is_rotation_move
    ):
        return algorithm

    return humanized


def humanize_moves_with_rotation(algorithm: Algorithm) -> Algorithm:
    """
    Transform to human-readable format.

    Returns:
        Humanized algorithm with POV translations and gyroscope timing.

    """
    return algorithm.transform(
        translate_pov_moves,
        reslice_timed_moves(RESLICE_THRESHOLD_GYROSCOPE, (3,)),
        rewide_timed_moves(REWIDE_THRESHOLD_GYROSCOPE),
    )


def humanize_moves(algorithm: Algorithm) -> Algorithm:
    """
    Transform to human-readable format.

    Returns:
        Humanized algorithm using rotation-specific or standard method.

    """
    if algorithm.has_rotations:
        return humanize_moves_with_rotation(algorithm)

    return humanize_moves_without_rotation(algorithm)


def humanize_moves_unsecured(algorithm: Algorithm) -> Algorithm:
    """
    Transform to human-readable format.

    But does not allow trailing rotations after transformation.
    Should be renammed or removed once things are stabilized.

    Returns:
        Humanized algorithm using rotation-specific or standard method.

    """
    if algorithm.has_rotations:
        return humanize_moves_with_rotation(algorithm)

    return humanize_moves_without_rotation(
        algorithm,
        allow_ending_rotations=False,
    )


def prettify_moves(algorithm: Algorithm) -> Algorithm:
    """
    Optimize algorithm representation.

    Returns:
        Optimized algorithm with timing removed and double moves merged.

    """
    return algorithm.transform(
        untime_moves,
        optimize_double_moves,
    )
