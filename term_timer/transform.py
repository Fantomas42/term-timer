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
