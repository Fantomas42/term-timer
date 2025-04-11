import re
from random import choices
from random import randint

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import OUTER_BASIC_MOVES
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.mirror import mirror_moves

from term_timer.constants import CUBE_SIZES
from term_timer.magic_cube import FACES_ORDER
from term_timer.magic_cube import Cube
from term_timer.twophases import USE_TWO_PHASE
from term_timer.twophases import solve

FACE_REGEXP = re.compile(r'(F|R|U|B|L|D)')

OPPOSITE_MOVES = {
    'F': 'B',
    'R': 'L',
    'U': 'D',
    'B': 'F',
    'L': 'R',
    'D': 'U',
}

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

    return OPPOSITE_MOVES[current_move] != previous_move


def random_moves(cube_size: int, iterations: int,
                 *, easy_cross: bool) -> Algorithm:
    move_set = MOVES_BY_CUBE[cube_size]

    if easy_cross:
        iterations = 10
        move_set = MOVES_EASY_CROSS

    value = choices(move_set)[0]
    moves = [value]
    previous = value

    if not iterations:
        iterations_range = ITERATIONS_BY_CUBE[cube_size]
        if cube_size == 3 and USE_TWO_PHASE:
            iterations_range = (25, 30)
        iterations = randint(*iterations_range)

    while len(moves) < iterations:
        while not is_valid_next_move(value, previous):
            value = choices(move_set)[0]

        previous = value
        moves.append(value)

    return parse_moves(moves)


def solve_moves(state: str) -> Algorithm | None:
    solution: str = solve(state, 0, 0.1)

    if 'Error' in solution:
        return None

    solution = solution.split('(')[0]
    solution = solution.replace('1', '')
    solution = solution.replace('3', "'")

    return parse_moves(solution)


def scrambler(cube_size: int, iterations: int,
              *, easy_cross: bool) -> tuple[Algorithm, Cube]:
    initial_state = ''
    for face in FACES_ORDER:
        initial_state += face * cube_size * cube_size

    cube = Cube(cube_size, initial_state)

    scramble = random_moves(
        cube_size, iterations,
        easy_cross=easy_cross,
    )

    cube.rotate(scramble)

    if cube_size != 3 or iterations or not USE_TWO_PHASE:
        return scramble, cube

    solve = solve_moves(
        cube.as_twophase_facelets,
    )

    if solve:
        scramble = solve.transform(mirror_moves)

        return scramble, cube

    return [], cube
