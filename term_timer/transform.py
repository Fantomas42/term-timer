from term_timer.constants import INVERT_CHAR
from term_timer.constants import JAPANESE_CHAR
from term_timer.constants import ROTATIONS


def invert(move: str) -> str:
    if move.endswith(INVERT_CHAR):
        return move[:1]
    return f'{ move }{ INVERT_CHAR }'


def mirror_moves(old_moves: list[str]) -> list[str]:
    moves = []
    for move in reversed(old_moves):
        if move.endswith('2'):
            moves.append(move)
        else:
            moves.append(invert(move))

    return moves


def is_japanese_move(move: str) -> bool:
    return JAPANESE_CHAR in move.lower()


def japanese_move(move: str) -> str:
    return f'{ move[0].upper() }{ JAPANESE_CHAR }{ move[1:] }'


def is_japanesable_move(move: str) -> bool:
    return (
        move[0].islower()
        and move[0] not in ROTATIONS
        and not is_japanese_move(move)
    )


def japanese_moves(old_moves: list[str]) -> list[str]:
    moves = []
    for _move in old_moves:
        move = str(_move)
        if is_japanesable_move(move):
            move = japanese_move(move)
        moves.append(move)

    return moves


def optimize_repeat_three_moves(old_moves: list[str]) -> list[str]:
    """ R, R, R --> R' """
    i = 0
    changed = False
    moves = list(old_moves)

    while i < len(moves) - 2:
        if moves[i] == moves[i + 1] == moves[i + 2]:
            moves[i:i + 3] = [invert(moves[i])]
            changed = True
        else:
            i += 1

    if changed:
        return optimize_repeat_three_moves(moves)

    return moves


def optimize_do_undo_moves(old_moves: list[str]) -> list[str]:
    """ R R' --> <nothing>, R R R' R' --> <nothing> """
    i = 0
    changed = False
    moves = list(old_moves)

    while i < len(moves) - 1:
        if invert(moves[i]) == moves[i + 1] or (
                moves[i] == moves[i + 1]
                and moves[i][-1] == '2'
                and moves[i + 1][-1] == '2'
        ):
            moves[i:i + 2] = []
            changed = True
        else:
            i += 1

    if changed:
        return optimize_do_undo_moves(moves)

    return moves


def optimize_double_moves(old_moves: list[str]) -> list[str]:
    """ R, R --> R2 """
    i = 0
    changed = False
    moves = list(old_moves)

    while i < len(moves) - 1:
        if moves[i] == moves[i + 1]:
            moves[i:i + 2] = [f'{ moves[i][0] }2']
            changed = True
        else:
            i += 1

    if changed:
        return optimize_double_moves(moves)

    return moves


def optimize_triple_moves(old_moves: list[str]) -> list[str]:
    """ R, R2 --> R' """
    i = 0
    changed = False
    moves = list(old_moves)

    while i < len(moves) - 1:
        if moves[i][0] == moves[i + 1][0]:
            if moves[i][-1] == '2' and moves[i + 1][-1] != '2':
                moves[i:i + 2] = [invert(moves[i + 1])]
                changed = True
            elif moves[i][-1] != '2' and moves[i + 1][-1] == '2':
                moves[i:i + 2] = [invert(moves[i])]
                changed = True
            else:
                i += 1
        else:
            i += 1

    if changed:
        return optimize_triple_moves(moves)

    return moves


def compress_moves(old_moves: list[str]) -> list[str]:
    moves = list(old_moves)

    compressing = True
    while compressing:
        changed = False
        for optimizer in (
                optimize_do_undo_moves,
                optimize_repeat_three_moves,
                optimize_double_moves,
                optimize_triple_moves,
        ):
            new_moves = optimizer(moves)
            if new_moves != moves:
                moves = new_moves
                changed = True

        if not changed:
            compressing = False

    return moves
