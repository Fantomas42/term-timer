"""Cube orientation calculation and management for optimal viewing angles."""
import operator
from functools import lru_cache

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.constants import ADJACENT_FACES
from cubing_algs.constants import FACE_ORDER
from cubing_algs.constants import OPPOSITE_FACES
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.transform.translate import translate_moves
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_RIGHT_HANDED
from term_timer.exceptions import InvalidOrientationError

PREFERRED_FACES: dict[str, int] = (
    {'U': 3, 'R': 2, 'F': 1, 'M': 1}
    if CUBE_RIGHT_HANDED else
    {'U': 3, 'L': 2, 'F': 1, 'M': 1}
)


def is_face_complete(cube: VCube, face: str) -> bool:
    """
    Check if all facelets on a face are the same color.

    Args:
        cube: Virtual cube to check
        face: Face to check (U, R, F, D, L, or B)

    Returns:
        True if all facelets match the center color

    """
    facelets = cube.get_face_by_center(face)
    return facelets == facelets[cube.center_index] * cube.face_size


def is_face_truly_completed(cube: VCube, face: str) -> bool:
    """
    Check if the first two layers are completed relative to a face.

    A face is considered "truly completed" when:
    1. All 9 facelets on the face are the same color (oriented)
    2. The first two layers relative to that face are solved (the top 6
       facelets of each adjacent face match their center color)

    This validates that not only is one face oriented, but the first
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
    f2l_size = cube.face_size - cube.size

    for adjacent_face in ADJACENT_FACES[face]:
        # Get first 6 facelets (indices 0-5): top two rows of the face
        # These facelets capture the first two layers for this face
        adjacent_facelets = cube_orientated.get_face_by_center(
            adjacent_face,
        )[:f2l_size]

        # All facelets must match to confirm first two layers are aligned
        if adjacent_facelets != adjacent_face * f2l_size:
            return False

    return True


def detect_top_face(
        scramble: Algorithm,
        untimed_solution: Algorithm,
) -> tuple[str | None, int]:
    """
    Replay the solve to find the top face and the index where F2L ends.

    Returns:
        Tuple of (top_face, f2l_end_index) where f2l_end_index is the
        number of moves after which the first two layers are complete.
        Returns (None, 0) if no face completion is detected.

    """
    cube = VCube(size=3)
    cube.rotate(scramble)

    for i, move in enumerate(untimed_solution):
        cube.rotate(move)

        # First filter: find faces where all 9 facelets are monochrome
        complete_faces = [
            face for face in FACE_ORDER
            if is_face_complete(cube, face)
        ]

        if not complete_faces:
            continue

        # Second filter: among monochrome faces, find those with first
        # two layers completed
        face_completed = [
            face for face in complete_faces
            if is_face_truly_completed(cube, face)
        ]

        # Exactly one completed face unambiguously identifies the cross face.
        # If 0: keep searching. If 2+: ambiguous state, keep searching.
        if len(face_completed) == 1:
            # The completed face is on the bottom (solver's perspective),
            # so we use its opposite as the top face for viewing
            return OPPOSITE_FACES[face_completed[0]], i + 1

    return None, 0


def score_gen_quality(
        top_face: str,
        front_face: str,
        moves: Algorithm,
) -> float:
    """
    Score a candidate orientation using generator quality.

    Translates moves into the given orientation and scores by how well
    the generator frequency matches PREFERRED_FACES, weighting each
    face by ergonomic importance and discounting by position in the
    frequency list.

    Returns:
        Weighted quality score; higher is better.

    """
    orientation_moves = parse_moves(
        ORIENTATION_FACE_MOVES[top_face + front_face],
    )
    algorithm = translate_moves(orientation_moves)(moves)
    generators = algorithm.metrics.generators
    return sum(
        weight / (generators.index(face) + 1)
        for face, weight in PREFERRED_FACES.items()
        if face in generators
    )


def get_orientation_faces(
        scramble: Algorithm,
        solution: Algorithm,
) -> CubeOrientation:
    """
    Calculate optimal cube orientation for solve analysis.

    Scores each candidate front face using generator quality on last-layer
    moves (OLL+PLL), which are free of hidden regrip rotations and provide a
    reliable ergonomic signal. Falls back to full-solve scoring when the
    last-layer is degenerate (all scores equal).

    Returns:
        Best CubeOrientation string (top_face + front_face).

    """
    untimed_solution = untime_moves(solution)
    top_face, f2l_end = detect_top_face(scramble, untimed_solution)

    if not top_face:
        return CUBE_ORIENTATION

    # Score each of the 4 candidate front faces using last-layer moves only.
    # OLL/PLL algorithms use genuine RUF moves without hidden regrip rotations,
    # making them a cleaner ergonomic signal than the full solve.
    score_moves = untimed_solution[f2l_end:] or untimed_solution

    scores = [
        (
            front_face,
            score_gen_quality(top_face, front_face, score_moves),
        )
        for front_face in ADJACENT_FACES[top_face]
    ]

    # Degenerate last-layer (e.g. single U move): all orientations score
    # identically, so fall back to full-solve scoring.
    if len({s for _, s in scores}) == 1:
        scores = [
            (
                front_face,
                score_gen_quality(top_face, front_face, untimed_solution),
            )
            for front_face in ADJACENT_FACES[top_face]
        ]

    return top_face + max(scores, key=operator.itemgetter(1))[0]


@lru_cache
def get_orientation_moves(orientation: CubeOrientation) -> Algorithm:
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
        return parse_moves(ORIENTATION_FACE_MOVES[orientation])
    except KeyError as error:
        msg = f'Invalid orientation "{ orientation }"'
        raise InvalidOrientationError(msg) from error
