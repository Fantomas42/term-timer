"""Cube orientation calculation and management for optimal viewing angles."""
import operator
from typing import Final

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import ADJACENT_FACES
from cubing_algs.constants import FACE_ORDER
from cubing_algs.constants import OPPOSITE_FACES
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.rotation import remove_ending_rotations
from cubing_algs.transform.timing import untime_moves
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_RIGHT_HANDED
from term_timer.exceptions import InvalidOrientationError


def is_face_complete(cube: VCube, face: str) -> bool:
    """
    Check if all facelets on a face are the same color.

    Args:
        cube: Virtual cube to check
        face: Face to check (U, R, F, D, L, or B)

    Returns:
        True if all 9 facelets match the center color

    """
    facelets = cube.get_face_by_center(face)
    return facelets == facelets[4] * 9


def is_face_truly_completed(cube: VCube, face: str) -> bool:
    """
    Check if the first two layers are completed relative to a face.

    A face is considered "truly completed" when:
    1. All 9 facelets on the face are the same color (monochrome)
    2. The first two layers relative to that face are solved (the top 6
       facelets of each adjacent face match their center color)

    This validates that not only is one face monochrome, but the first
    two layers are properly solved. This ensures we detect genuine solve
    progress rather than accidental monochrome faces.

    When the face is oriented to the top, checking the top 6 facelets
    (indices 0-5) of each adjacent face validates:
    - 4 edge pieces connecting the two layers
    - 2 corner pieces of the first layer
    - The center (always correct)

    Args:
        cube: Virtual cube to check
        face: Face to check (U, R, F, D, L, or B)

    Returns:
        True if the face is monochrome with first two layers completed

    """
    # Orient cube so the completed face is on top for easier checking
    cube_orientated = cube.oriented_copy(face)

    # Check each adjacent face (4 faces surrounding the completed one)
    for adjacent_face in ADJACENT_FACES[face]:
        # Get first 6 facelets (indices 0-5): top two rows of the face
        # These 6 facelets capture the first two layers for this face
        adjacent_facelets = cube_orientated.get_face_by_center(
            adjacent_face,
        )[:6]

        # All 6 facelets must match the adjacent face's center color
        # This confirms the first two layers are properly aligned
        if adjacent_facelets != adjacent_face * 6:
            return False

    return True


def get_orientation_faces(
        scramble: Algorithm,
        solution: Algorithm,
) -> str:
    """
    Calculate optimal cube orientation for solve analysis.

    This function implements a two-phase algorithm:

    Phase 1 - Detect Bottom Face:
        Replay the solve move-by-move until exactly one face is "truly
        completed" (monochrome with first two layers completed). This face
        becomes the bottom, and its opposite becomes the top.

    Phase 2 - Select Front Face:
        Among the 4 possible front faces (adjacent to top), choose the one
        that maximizes ergonomic moves (left-hand or right-hand based on
        user configuration).

    Args:
        scramble: Scrambling algorithm applied before solution
        solution: Solution reconstruction with moves (may include timing)

    Returns:
        Two-character orientation string (e.g., 'UF' for white top,
        green front). Falls back to CUBE_ORIENTATION if no face
        completion is detected during the solve.

    """
    top_face = None

    cube = VCube(size=3)
    cube.rotate(scramble)

    untimed_solution = solution.transform(untime_moves)

    # Phase 1: Detect when the first face is truly completed
    # We replay the solve move-by-move to find the critical moment
    for move in untimed_solution:
        cube.rotate(move)

        # First filter: Find faces where all 9 facelets are monochrome
        complete_faces = [
            face for face in FACE_ORDER
            if is_face_complete(cube, face)
        ]

        if not complete_faces:
            continue

        # Second filter: Among monochrome faces, find those with first
        # two layers completed
        face_completed = [
            face for face in complete_faces
            if is_face_truly_completed(cube, face)
        ]

        # We need exactly one face to be completed to determine orientation
        # If 0 faces: keep searching
        # If 2+ faces: ambiguous state, keep searching for clearer moment
        if len(face_completed) == 1:
            # The completed face is on the bottom (solver's perspective)
            # so we use its opposite as the top face for viewing
            top_face = OPPOSITE_FACES[face_completed[0]]
            break

    if not top_face:
        return CUBE_ORIENTATION

    # Phase 2: Select the front face with best ergonomics
    # We test each of the 4 possible front faces (adjacent to top face)
    # and score them based on the number of comfortable moves
    scores = []
    for front_face in ADJACENT_FACES[top_face]:
        # Build the full algorithm with orientation moves prepended
        # Then apply transforms to normalize it for ergonomic analysis
        algorithm = (
            ORIENTATION_FACE_MOVES[top_face + front_face]
            + untimed_solution
        ).transform(
            degrip_full_moves,
            remove_ending_rotations,
        )
        ergonomics = algorithm.ergonomics

        # Score based on configured handedness preference
        # Higher score = more moves with preferred hand
        score = (
            ergonomics.left_hand_moves if not CUBE_RIGHT_HANDED
            else ergonomics.right_hand_moves
        )

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
        return ORIENTATION_FACE_MOVES[orientation]
    except KeyError as error:
        msg = f'Invalid orientation "{ orientation }"'
        raise InvalidOrientationError(msg) from error
