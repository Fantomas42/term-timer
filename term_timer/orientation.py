from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import ORIENTATIONS
from cubing_algs.parsing import parse_moves
from cubing_algs.vcube import VCube

from term_timer.exceptions import InvalidOrientationError

cube = VCube()

ORIENTATION_MOVES = {
    orientation: parse_moves(
        cube.compute_orientation_moves(orientation),
    )
    for orientation in ORIENTATIONS
}


def get_orientation_moves(orientation: str) -> Algorithm:
    try:
        return ORIENTATION_MOVES[orientation]
    except KeyError as error:
        raise InvalidOrientationError from error
