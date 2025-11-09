"""Cube orientation calculation and management for optimal viewing angles."""

import operator
from typing import Final

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import ADJACENT_FACES
from cubing_algs.constants import FACE_ORDER
from cubing_algs.constants import OPPOSITE_FACES
from cubing_algs.constants import ORIENTATIONS
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import remove_ending_rotations
from cubing_algs.transform.timing import untime_moves
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_RIGHT_HANDED
from term_timer.exceptions import InvalidOrientationError

cube = VCube()

ORIENTATION_MOVES: Final = {
    orientation: parse_moves(
        cube.compute_orientation_moves(orientation),
    )
    for orientation in ORIENTATIONS
}


def get_orientation_faces(scramble: Algorithm, solution: Algorithm) -> str:  # noqa: C901
    """
    Calculate optimal cube orientation for solve analysis.

    Returns:
        Two-character orientation string (e.g., 'UF' for white top,
        green front).

    """
    top_face = None

    cube = VCube()
    cube.rotate(scramble)

    solution = solution.transform(untime_moves)

    for move in solution:
        cube.rotate(move)

        faces_done = []

        for face in FACE_ORDER:
            facelets = cube.get_face(face)
            if facelets == facelets[4] * 9:
                faces_done.append(face)

        face_completed = []
        for face in faces_done:
            cube_orientated = cube.oriented_copy(face)

            for adjacent_face in ADJACENT_FACES[face]:
                adjacent_facelets = cube_orientated.get_face(adjacent_face)[:3]
                if adjacent_facelets != adjacent_face * 3:
                    break
            face_completed.append(face)

            if len(face_completed) == 1:
                top_face = OPPOSITE_FACES[face_completed[0]]

        if top_face:
            break

    if not top_face:
        return CUBE_ORIENTATION

    scores = []
    for front_face in ADJACENT_FACES[top_face]:
        algorithm = (
            ORIENTATION_MOVES[top_face + front_face]
            + solution
        ).transform(
            degrip_full_moves,
            remove_ending_rotations,
        )
        ergonomics = algorithm.ergonomics
        score = ergonomics.right_hand_moves
        if not CUBE_RIGHT_HANDED:
            score = ergonomics.left_hand_moves

        scores.append((front_face, score))

    best_front_face = max(scores, key=operator.itemgetter(1))[0]

    return top_face + best_front_face


def get_orientation_moves(orientation: str) -> Algorithm:
    """
    Get pre-computed orientation moves for given orientation.

    Returns:
        Algorithm containing rotation moves to achieve the orientation.

    Raises:
        InvalidOrientationError: If the orientation string is invalid.

    """
    if orientation == 'auto':
        orientation = CUBE_ORIENTATION

    try:
        return ORIENTATION_MOVES[orientation]
    except KeyError as error:
        msg = f'Invalid orientation "{ orientation }"'
        raise InvalidOrientationError(msg) from error
