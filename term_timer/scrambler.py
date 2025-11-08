"""Scramble generation and training case setup utilities."""

from random import choice
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.scrambler import scramble
from cubing_algs.scrambler import scramble_easy_cross
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.mirror import mirror_moves
from cubing_algs.transform.rotation import compress_ending_rotations
from cubing_algs.vcube import VCube
from kociemba import solve

from term_timer.config import CUBE_RIGHT_HANDED
from term_timer.exceptions import InvalidCaseError
from term_timer.magic_cube import Cube
from term_timer.methods.cases import CASES

if TYPE_CHECKING:
    from term_timer.methods.types import CaseInfo


def state_to_scramble(state: str, facelets: str = '') -> Algorithm:
    """
    Return algorithm to reach a certain state
    """
    solution: str = solve(state, facelets) if facelets else solve(state)

    return parse_moves(solution).transform(mirror_moves)


def scrambler(cube_size: int, iterations: int,
              *,
              easy_cross: bool,
              raw_scramble: str = '') -> tuple[Algorithm, Cube]:
    """Generate cube scramble."""
    cube = Cube(cube_size)

    if raw_scramble:
        scrambled = parse_moves(raw_scramble, secure=False)
    elif easy_cross:
        scrambled = scramble_easy_cross()
    else:
        scrambled = scramble(
            cube_size, iterations,
            inner_layers=True,
            right_handed=CUBE_RIGHT_HANDED,
        )

    cube.rotate(scrambled)

    if cube_size != 3 or iterations or easy_cross or raw_scramble:
        return scrambled, cube

    scrambled = state_to_scramble(cube.state)

    return scrambled, cube


def trainer(step: str, cases: list[str],
            orientation_moves: Algorithm,
            bluetooth_cube: VCube | None = None) -> tuple[
                str, Algorithm, Algorithm, VCube]:
    """Generate training case."""
    cube = (bluetooth_cube and bluetooth_cube.copy()) or VCube()

    if step == 'ecross':
        case_name = 'Easy Cross'
        main_algorithm = Algorithm()
        scramble = scramble_easy_cross()
    elif step == 'cross':
        case_name = 'Cross'
        main_algorithm = Algorithm()
        scramble, _cube = scrambler(3, 12, easy_cross=False)
    else:
        case_name, main_algorithm, scramble = random_training(
            step, cases, orientation_moves,
        )

    cube.rotate(scramble)

    return case_name, main_algorithm, scramble, cube


def random_training(step: str, selected_cases: list[str],
                    orientation_moves: Algorithm) -> tuple[
                        str, Algorithm, Algorithm]:
    """Generate random training case."""
    cases: dict[str, CaseInfo] = CASES[step.upper()]
    valid_cases: dict[str, CaseInfo] = {
        k: v for k, v in cases.items() if v.get('setups')
    }

    case = choice(selected_cases or list(valid_cases.keys()))  # noqa: S311

    if case not in valid_cases:
        error_string = f'Invalid case { case } for { step.upper() }'
        raise InvalidCaseError(error_string)

    case_info = cases[case]

    algo = (
        orientation_moves
        + choice(case_info['setups'])  # noqa: S311
        + mirror_moves(orientation_moves)
    )

    case_name = case_info['name']
    main_algorithm = case_info['main']

    return case_name, parse_moves(main_algorithm), parse_moves(algo).transform(
        degrip_full_moves,
        compress_ending_rotations,
    )
