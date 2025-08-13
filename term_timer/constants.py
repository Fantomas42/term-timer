from pathlib import Path

SECOND = 1_000_000_000  # In nano seconds

MS_TO_NS_FACTOR = 1_000_000

PAUSE_FACTOR = 2

STEP_BAR = 17

SAVE_DIRECTORY = Path.home() / '.solves'

CONFIG_FILE = Path('~/.term_timer').expanduser()

TEMPLATES_DIRECTORY = Path(__file__).parent / 'server' / 'templates'

STATIC_DIRECTORY = Path(__file__).parent / 'server' / 'static'

DNF = 'DNF'

PLUS_TWO = '+2'

CUBE_SIZES = list(range(2, 8))

SECOND_BINS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]

REFRESH = 0.01

RESLICE_THRESHOLD = 50

ESCAPE_CHAR = '\x1b'
