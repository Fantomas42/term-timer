from random import choices
from random import randint

from term_timer.magic_cube import FACES_ORDER
from term_timer.magic_cube import Cube
from term_timer.transform import mirror_moves
from term_timer.twophases import solve

MOVES_DEFAULT = [
    'F', "F'", 'F2',
    'R', "R'", 'R2',
    'U', "U'", 'U2',
    'B', "B'", 'B2',
    'L', "L'", 'L2',
    'D', "D'", 'D2',
]

MOVES_EC = [
    'F',
    'R',
    'B',
    'L',
]


def random_moves(puzzle: str, mode: str, iterations: int) -> list[str]:
    move_set = MOVES_DEFAULT
    if mode == 'ec':
        move_set = MOVES_EC
        iterations = 10

    value = choices(move_set)[0]
    moves = [value]
    previous = value

    if not iterations:
        iterations = randint(25, 30)

    while len(moves) < iterations:
        while value[0] == previous[0]:
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


def scrambler(puzzle: str, mode: str,
              iterations: int) -> tuple[list[str], Cube]:
    puzzle_int = int(puzzle)

    initial_state = ''
    for face in FACES_ORDER:
        initial_state += face * puzzle_int * puzzle_int

    cube = Cube(puzzle_int, initial_state)

    moves = random_moves(puzzle, mode, iterations)

    cube.rotate(moves)

    if puzzle != '3':
        return moves, cube

    solve = solve_moves(
        cube.as_twophase_facelets,
    )

    if solve:
        scramble = mirror_moves(solve)

        return scramble, cube

    return [], cube
