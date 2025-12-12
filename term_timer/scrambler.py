"""Scramble generation and training case setup utilities."""
from random import Random

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_collection
from cubing_algs.cases.case import Case
from cubing_algs.parsing import parse_moves
from cubing_algs.scrambler import scramble
from cubing_algs.scrambler import scramble_easy_cross
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.mirror import mirror_moves
from cubing_algs.transform.rotation import compress_ending_rotations
from cubing_algs.vcube import VCube
from kociemba import solve

from term_timer.config import CUBE_RIGHT_HANDED
from term_timer.constants import CROSS_CASE
from term_timer.constants import EASY_CROSS_CASE
from term_timer.exceptions import InvalidCaseError


def state_to_scramble(state: str, facelets: str = '') -> Algorithm:
    """
    Return algorithm to reach a certain state.

    Returns:
        Algorithm that transforms cube from solved to given state.

    """
    solution: str = solve(state, facelets) if facelets else solve(state)

    return parse_moves(solution).transform(mirror_moves)


def scrambler(cube_size: int, iterations: int,
              *,
              easy_cross: bool,
              rng: Random,
              raw_scramble: str = '') -> tuple[Algorithm, VCube]:
    """
    Generate cube scramble.

    Returns:
        Tuple of (scramble algorithm, scrambled cube state).

    """
    cube = VCube(size=cube_size)

    if raw_scramble:
        scrambled = parse_moves(raw_scramble, secure=False)
    elif easy_cross:
        scrambled = scramble_easy_cross(rng)
    else:
        scrambled = scramble(
            cube_size, iterations,
            inner_layers=True,
            right_handed=CUBE_RIGHT_HANDED,
            rng=rng,
        )

    cube.rotate(scrambled)

    if cube_size != 3 or iterations or easy_cross or raw_scramble:
        return scrambled, cube

    scrambled = state_to_scramble(cube.state)

    return scrambled, cube


def trainer(step: str, cases: list[str],
            orientation_moves: Algorithm,
            rng: Random,
            bluetooth_cube: VCube | None = None) -> tuple[
                Case, Algorithm, Algorithm, VCube]:
    """
    Generate training case.

    Returns:
        Tuple of (case name, main algorithm, scramble, cube state).

    """
    cube = (bluetooth_cube and bluetooth_cube.copy()) or VCube(size=3)

    if step == 'ecross':
        case = EASY_CROSS_CASE
        main_algorithm = Algorithm()
        scramble = scramble_easy_cross(rng)
    elif step == 'cross':
        case = CROSS_CASE
        main_algorithm = Algorithm()
        scramble, _cube = scrambler(3, 12, easy_cross=False, rng=rng)
    else:
        case, scramble = random_training(
            step, cases, orientation_moves, rng,
        )
        main_algorithm = case.main_algorithm

    cube.rotate(scramble)

    return case, main_algorithm, scramble, cube


def random_training(step: str, selected_cases: list[str],
                    orientation_moves: Algorithm,
                    rng: Random) -> tuple[
                        Case, Algorithm]:
    """
    Generate random training case.

    Returns:
        Tuple of (case, scramble algorithm).

    Raises:
        InvalidCaseError: If selected case is not valid for the step.

    """
    cases = get_collection(f'CFOP/{ step }').cases
    valid_cases: dict[str, Case] = {
        v.code: v for v in cases.values() if v.setup_algorithms
    }

    case = rng.choice(selected_cases or list(valid_cases.keys()))

    if case not in valid_cases:
        error_string = f'Invalid case { case } for { step.upper() }'
        raise InvalidCaseError(error_string)

    case_info = valid_cases[case]

    algo = (
        orientation_moves
        + rng.choice(case_info.setup_algorithms)
        + mirror_moves(orientation_moves)
    )

    return (
        case_info,
        parse_moves(algo).transform(
            degrip_full_moves,
            compress_ending_rotations,
        ),
    )
