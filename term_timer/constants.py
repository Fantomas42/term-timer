"""Application-wide constants and type definitions."""
from pathlib import Path
from typing import Final
from typing import Literal

from cubing_algs.cases.case import Case
from cubing_algs.cases.case import CaseData

SECOND: Final = 1_000_000_000  # In nano seconds

MS_TO_NS_FACTOR: Final = 1_000_000

PAUSE_FACTOR: Final = 2

STEP_BAR: Final = 17

SOLVES_DIRECTORY: Final = Path.home() / '.solves'

TRAININGS_DIRECTORY: Final = Path.home() / '.trainings'

CONFIG_FILE: Final = Path('~/.term_timer').expanduser()

TEMPLATES_DIRECTORY: Final = Path(__file__).parent / 'server' / 'templates'

STATIC_DIRECTORY: Final = Path(__file__).parent / 'server' / 'static'

DNF: Final = 'DNF'

PLUS_TWO: Final = '+2'

CUBE_SIZES: Final = list(range(2, 8))

SECOND_BINS: Final = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]

REFRESH: Final = 0.01

RESLICE_THRESHOLD: Final = 70

RESLICE_THRESHOLD_GYROSCOPE: Final = 120

REWIDE_THRESHOLD_GYROSCOPE: Final = 180

ESCAPE_CHAR: Final = '\x1b'

FLUENCY_EXPONENTIAL_DECAY: Final = -0.00111571775657105

Face = Literal['U', 'D', 'R', 'L', 'F', 'B']

SolveFlag = Literal['', 'DNF', '+2']

SolveFlagInput = Literal['OK', 'DNF', '+2']

CROSS_CASE = Case(
    '', 'Cross',
    CaseData(
        name='Cross',
        code='cross',
    ),
)

EASY_CROSS_CASE = Case(
    '', 'Easy Cross',
    CaseData(
        name='Easy Cross',
        code='ecross',
    ),
)

X_CROSS_CASE = Case(
    '', 'X-Cross',
    CaseData(
        name='X-Cross',
        code='xcross',
    ),
)
