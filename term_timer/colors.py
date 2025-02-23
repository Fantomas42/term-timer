from enum import Enum


class Color(Enum):
    RESET = '\x1b[0;0m'
    STATS = '\x1b[38;5;75m'
    RESULT = '\x1b[38;5;231m'

    RECORD = '\x1b[48;5;85m\x1b[38;5;232m'
    SCRAMBLE = '\x1b[48;5;40m\x1b[38;5;232m'
    DURATION = '\x1b[48;5;208m\x1b[38;5;232m'

    GO_BASE = '\x1b[48;5;150m\x1b[38;5;232m'
    GO_TEN = '\x1b[48;5;112m\x1b[38;5;232m'
    GO_FIF = '\x1b[48;5;80m\x1b[38;5;232m'
    GO_TWE = '\x1b[48;5;220m\x1b[38;5;232m'
    GO_TWF = '\x1b[48;5;208m\x1b[38;5;232m'
    GO_THR = '\x1b[48;5;160m\x1b[38;5;230m'
    GO_THF = '\x1b[48;5;89m\x1b[38;5;230m'

    RED = '\x1b[38;5;196m'
    GREEN = '\x1b[38;5;82m'

    MO3 = '\x1b[38;5;172m'
    AO5 = '\x1b[38;5;86m'
    AO12 = '\x1b[38;5;99m'
    AO100 = '\x1b[38;5;208m'
