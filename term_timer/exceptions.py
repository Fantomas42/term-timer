"""Custom exception classes for the term-timer application."""
from typing import Final

from cubing_algs.exceptions import CubingAlgsError


class CubeNotFoundError(Exception):
    """Raised when no Bluetooth cube is found during scanning."""


class CubeDisconnectedError(Exception):
    """Raised when the cube announces its own disconnection."""


class InvalidCaseError(Exception):
    """Raised when an invalid training case is selected."""


class InvalidAlgorithmError(Exception):
    """Raised when an invalid algorithm is given."""


class InvalidOrientationError(Exception):
    """Raised when an invalid cube orientation is specified."""


class ReplayError(Exception):
    """Raised when a Bluetooth replay file is missing or invalid."""


SESSION_ERRORS: Final[tuple[type[Exception], ...]] = (
    CubingAlgsError,
    CubeDisconnectedError,
    InvalidAlgorithmError,
    InvalidCaseError,
)
