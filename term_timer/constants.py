from pathlib import Path

SECOND = 1_000_000_000

STEP_BAR = 17

SAVE_DIRECTORY = Path.home() / '.solves'
SAVE_DIRECTORY.mkdir(exist_ok=True)

INVERT_CHAR = "'"

JAPANESE_CHAR = 'w'

MOVES = [
    'F', 'R', 'U',
    'B', 'L', 'D',
]

ROTATIONS = (
    'x', 'y', 'z',
)

DNF = 'DNF'

PLUS_TWO = '+2'
