import re
from random import choices
from random import randint

from term_timer.constants import MOVES
from term_timer.magic_cube import FACES_ORDER
from term_timer.magic_cube import Cube
from term_timer.transform import mirror_moves
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

MOVES_EC = [
    'F',
    'R',
    'B',
    'L',
]


def build_puzzle_moves(puzzle: int) -> list[str]:
    moves = []

    for face in MOVES:
        moves.extend(
            [
                face,
                f"{ face }'",
                f'{ face }2',
            ],
        )
        if puzzle > 3:
            moves.extend(
                [
                    f'{ face }w',
                    f"{ face }w'",
                    f'{ face }w2',
                ],
            )
            for i in range(2, puzzle):
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


def random_moves(puzzle: int, mode: str, iterations: int) -> list[str]:
    if mode == 'ec':
        move_set = MOVES_EC
        iterations = 10
    else:
        move_set = build_puzzle_moves(puzzle)
        if puzzle == 2:
            iterations = 10

    value = choices(move_set)[0]
    moves = [value]
    previous = value

    if not iterations:
        iterations = randint(25, 30)

    while len(moves) < iterations:
        while not is_valid_next_move(value, previous):
            value = choices(move_set)[0]

        previous = value
        moves.append(value)

    return moves


def solve_moves(state: str) -> list[str]:
    solution: str = solve(state, 0, 0.1)

    if 'Error' in solution:
        return []

    solution = solution.split('(')[0]
    solution = solution.replace('1', '')
    solution = solution.replace('3', "'")

    return solution.split()


def scrambler(puzzle: int, mode: str,
              iterations: int) -> tuple[list[str], Cube]:
    initial_state = ''
    for face in FACES_ORDER:
        initial_state += face * puzzle * puzzle

    cube = Cube(puzzle, initial_state)

    moves = random_moves(puzzle, mode, iterations)

    cube.rotate(moves)

    if puzzle != 3:
        return moves, cube

    solve = solve_moves(
        cube.as_twophase_facelets,
    )

    if solve:
        scramble = mirror_moves(solve)

        return scramble, cube

    return [], cube
