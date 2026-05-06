"""Scramble generation and training case setup utilities."""
from random import Random
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases.case import Case
from cubing_algs.parsing import parse_moves
from cubing_algs.scrambler.nxn import scramble
from cubing_algs.scrambler.steps import scramble_easy_cross
from cubing_algs.scrambler.steps import scramble_edges_oriented
from cubing_algs.scrambler.steps import scramble_x_cross
from cubing_algs.solved_state import SOLVED_FACELETS_3x3x3
from cubing_algs.solver import facelets_to_facelets_algorithm
from cubing_algs.transform.degrip import degrip_moves
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_RIGHT_HANDED
from term_timer.config import TRAINER_ECROSS_DIFFICULTY
from term_timer.config import TRAINER_XCROSS_DIFFICULTY
from term_timer.config import TRAINER_XCROSS_SLOTS

if TYPE_CHECKING:
    from term_timer.annotations import TrainingCase


def scrambler(  # noqa: PLR0913
        cube_size: int,
        iterations: int,
        *,
        easy_cross: bool = False,
        x_cross: bool = False,
        edges_oriented: bool = False,
        rng: Random,
        raw_scramble: str = '',
        orientation_moves: Algorithm | None = None,
) -> tuple[Algorithm, VCube]:
    """
    Generate cube scramble.

    Returns:
        Tuple of (scramble algorithm, scrambled cube on canonical orientation).

    """
    cube = VCube(size=cube_size)

    if raw_scramble:
        scrambled = parse_moves(raw_scramble, trust_input=False)
    elif easy_cross:
        scrambled, _solution = scramble_easy_cross(
            TRAINER_ECROSS_DIFFICULTY,
            rng=rng,
        )
        if orientation_moves:
            scrambled = degrip_moves(orientation_moves + scrambled)
    elif x_cross:
        scrambled, _solution = scramble_x_cross(
            TRAINER_XCROSS_DIFFICULTY,
            TRAINER_XCROSS_SLOTS,
            rng=rng,
        )
        if orientation_moves:
            scrambled = degrip_moves(orientation_moves + scrambled)
    elif edges_oriented:
        scrambled = scramble_edges_oriented(
            iterations or None,
            rng=rng,
        )
    else:
        scrambled = scramble(
            cube_size,
            iterations or None,
            inner_layers=True,
            right_handed=CUBE_RIGHT_HANDED,
            rng=rng,
        )

    cube.rotate(scrambled)

    if cube_size != 3 or iterations or easy_cross or x_cross or raw_scramble:
        return scrambled, cube

    scrambled = facelets_to_facelets_algorithm(
        SOLVED_FACELETS_3x3x3,
        cube.state,
    )

    return scrambled, cube


def trainer(
        step: str,
        cases: list['TrainingCase'],
        rng: Random,
        orientation_moves: Algorithm | None = None,
) -> tuple[
    Case, Algorithm, Algorithm,
]:
    """
    Generate training case.

    Returns:
        Tuple of (case, scramble, solution).

    """
    case = cases[0].case
    solution = Algorithm()

    if step == 'ecross':
        scramble, solution = scramble_easy_cross(
            TRAINER_ECROSS_DIFFICULTY,
            rng=rng,
        )
    elif step == 'xcross':
        scramble, solution = scramble_x_cross(
            TRAINER_XCROSS_DIFFICULTY,
            TRAINER_XCROSS_SLOTS,
            rng=rng,
        )
    elif step == 'cross':
        scramble, _cube = scrambler(3, 12, rng=rng)
    else:
        case, scramble, solution = random_training(
            cases, rng,
        )

    if orientation_moves:
        scramble = degrip_moves(orientation_moves + scramble)

    return case, scramble, solution


def random_training(
        cases: list['TrainingCase'],
        rng: Random,
) -> tuple[
    Case, Algorithm, Algorithm,
]:
    """
    Generate random training case.

    Returns:
        Tuple of (case, scramble algorithm).

    """
    selected_case = rng.choices(
        cases,
        weights=[c.case.probability for c in cases],
        k=1,
    )

    return (
        selected_case.case,
        rng.choice(selected_case.best_setups),
        selected_case.case.main_algorithm,
    )
