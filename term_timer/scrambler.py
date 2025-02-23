from random import choices
from random import randint

from term_timer.magic_cube import INITIAL_SCRAMBLE
from term_timer.magic_cube import Cube
from term_timer.transform import mirror_moves
from term_timer.twophases import solver

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


def random_moves(mode: str, iterations: int) -> list[str]:
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
    solution = solver.solve(state, 0, 0.1)

    if 'Error' in solution:
        return []

    solution = solution.split('(')[0]
    solution = solution.replace('1', '')
    solution = solution.replace('3', "'")

    return solution.split()


def scrambler(mode: str, iterations: int, *, show_cube: bool) -> (list[str], Cube):
    cube = Cube(3, INITIAL_SCRAMBLE)

    moves = random_moves(mode, iterations)

    cube.rotate(moves)

    solve = solve_moves(
        cube.as_twophase_facelets,
    )

    if solve:
        scramble = mirror_moves(solve)

        return scramble, cube

    return [], cube
