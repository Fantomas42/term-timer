import re
from random import choice
from random import randint

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import OPPOSITE_FACES
from cubing_algs.constants import OUTER_BASIC_MOVES
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.fat import unfat_rotation_moves
from cubing_algs.transform.mirror import mirror_moves
from cubing_algs.transform.rotation import compress_final_rotations
from kociemba import solve

from term_timer.config import LL_ORIENTATION
from term_timer.constants import CUBE_SIZES
from term_timer.magic_cube import Cube
from term_timer.methods.cfop import OLL_SETUPS
from term_timer.methods.cfop import PLL_SETUPS


class InvalidCaseError(Exception):
    ...


FACE_REGEXP = re.compile(r'(F|R|U|B|L|D)')

MOVES_EASY_CROSS = [
    'F',
    'R',
    'B',
    'L',
]


def build_cube_moves(cube_size: int) -> list[str]:
    moves = []

    for face in OUTER_BASIC_MOVES:
        moves.extend(
            [
                face,
                f"{ face }'",
                f'{ face }2',
            ],
        )
        if cube_size > 3:
            moves.extend(
                [
                    f'{ face }w',
                    f"{ face }w'",
                    f'{ face }w2',
                ],
            )
            if cube_size > 5:
                for i in range(2, 4):
                    moves.extend(
                        [
                            f'{ i }{ face }',
                            f"{ i }{ face }'",
                            f'{ i }{ face }2',
                            f'{ i }{ face }w',
                            f"{ i }{ face }w'",
                            f'{ i }{ face }w2',
                        ],
                    )

    return moves


MOVES_BY_CUBE = {
    i: build_cube_moves(i)
    for i in CUBE_SIZES
}

ITERATIONS_BY_CUBE = {
    2: (9, 11),
    3: (19, 22),
    4: (45, 50),
    5: (60, 60),
    6: (80, 80),
    7: (100, 100),
}


def is_valid_next_move(current: str, previous: str) -> bool:
    current_move_search = FACE_REGEXP.search(current)
    previous_move_search = FACE_REGEXP.search(previous)

    if not current_move_search or not previous_move_search:
        return False

    current_move = current_move_search[0]
    previous_move = previous_move_search[0]

    if current_move == previous_move:
        return False

    return OPPOSITE_FACES[current_move] != previous_move


def random_moves(cube_size: int, iterations: int,
                 *, easy_cross: bool) -> tuple[Algorithm, int]:
    move_set = MOVES_BY_CUBE[cube_size]

    if easy_cross:
        iterations = 10
        move_set = MOVES_EASY_CROSS

    value = choice(move_set)
    moves = [value]
    previous = value

    if not iterations:
        iterations_range = ITERATIONS_BY_CUBE[cube_size]
        if cube_size == 3:
            iterations_range = (25, 30)
        iterations = randint(*iterations_range)

    while len(moves) < iterations:
        while not is_valid_next_move(value, previous):
            value = choice(move_set)

        previous = value
        moves.append(value)

    return parse_moves(moves)


def scramble_moves(state: str, facelets: str = '') -> Algorithm:
    solution: str = solve(state, facelets) if facelets else solve(state)

    return parse_moves(solution).transform(mirror_moves)


def scrambler(cube_size: int, iterations: int,
              *,
              easy_cross: bool,
              raw_scramble: str = '') -> tuple[Algorithm, Cube]:
    cube = Cube(cube_size)

    if raw_scramble:
        scramble = parse_moves(raw_scramble, secure=False)
    else:
        scramble = random_moves(
            cube_size, iterations,
            easy_cross=easy_cross,
        )

    cube.rotate(scramble)

    if cube_size != 3 or iterations or easy_cross or scramble:
        return scramble, cube

    scramble = scramble_moves(
        cube.get_kociemba_facelet_positions(),
    )

    return scramble, cube


def trainer(step, cases):
    cube = Cube(3)

    case_name, scramble = random_training(step, cases)

    cube.rotate(scramble)

    return case_name, scramble, cube


def random_training(step, selected_cases):
    cases = OLL_SETUPS
    if step == 'pll':
        cases = PLL_SETUPS

    case = choice(selected_cases or list(cases.keys()))

    if case not in cases:
        error_string = f'Invalid case { case } for { step.upper() }'
        raise InvalidCaseError(error_string)

    algo = LL_ORIENTATION + choice(cases[case]['setups'])
    case_name = cases[case]['name']

    return case_name, parse_moves(algo).transform(
        unfat_rotation_moves,
        degrip_full_moves,
        compress_final_rotations,
    )
