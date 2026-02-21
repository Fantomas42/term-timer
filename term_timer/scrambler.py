"""Scramble generation and training case setup utilities."""
from random import Random
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases.case import Case
from cubing_algs.parsing import parse_moves
from cubing_algs.scrambler.nxn import scramble
from cubing_algs.scrambler.steps import scramble_easy_cross
from cubing_algs.scrambler.steps import scramble_x_cross
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.invert import invert_moves
from cubing_algs.transform.rotation import compress_ending_rotations
from cubing_algs.vcube import VCube
from kociemba import solve

from term_timer.config import CUBE_RIGHT_HANDED

if TYPE_CHECKING:
    from term_timer.annotations import TrainingCase


def state_to_scramble(state: str, facelets: str = '') -> Algorithm:
    """
    Return algorithm to reach a certain state.

    Returns:
        Algorithm that transforms cube from solved to given state.

    """
    solution: str = solve(state, facelets) if facelets else solve(state)

    return parse_moves(solution).transform(invert_moves)


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
        scrambled, _solution = scramble_easy_cross('normal', rng=rng)
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


def trainer(step: str, cases: list['TrainingCase'],
            orientation_moves: Algorithm,
            rng: Random,
            bluetooth_cube: VCube | None = None) -> tuple[
                Case, Algorithm, VCube]:
    """
    Generate training case.

    Returns:
        Tuple of (case, scramble, cube state).

    """
    cube = (bluetooth_cube and bluetooth_cube.copy()) or VCube(size=3)

    if step == 'ecross':
        case = cases[0].case
        scramble, _solution = scramble_easy_cross('normal', rng=rng)
    elif step == 'xcross':
        case = cases[0].case
        scramble, _solution = scramble_x_cross('normal', rng=rng)
    elif step == 'cross':
        case = cases[0].case
        scramble, _cube = scrambler(3, 12, easy_cross=False, rng=rng)
    else:
        case, scramble = random_training(
            cases, orientation_moves, rng,
        )

    cube.rotate(scramble)

    return case, scramble, cube


def random_training(cases: list['TrainingCase'],
                    orientation_moves: Algorithm,
                    rng: Random) -> tuple[
                        Case, Algorithm]:
    """
    Generate random training case.

    Returns:
        Tuple of (case, scramble algorithm).

    """
    selected_case = rng.choice(cases)

    algo = (
        orientation_moves
        + rng.choice(selected_case.best_setups)
        + invert_moves(orientation_moves)
    )

    return (
        selected_case.case,
        parse_moves(algo).transform(
            degrip_full_moves,
            compress_ending_rotations,
        ),
    )
