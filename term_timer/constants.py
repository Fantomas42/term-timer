from pathlib import Path

SECOND = 1_000_000_000  # In nano seconds

STEP_BAR = 17

SAVE_DIRECTORY = Path.home() / '.solves'
SAVE_DIRECTORY.mkdir(exist_ok=True)

CONFIG_FILE = Path('~/.term_timer').expanduser()

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

CUBE_SIZES = list(range(2, 8))

SECOND_BINS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
