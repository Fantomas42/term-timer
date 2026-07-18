"""Custom exception classes for the term-timer application."""


class CubeNotFoundError(Exception):
    """Raised when no Bluetooth cube is found during scanning."""


class InvalidCaseError(Exception):
    """Raised when an invalid training case is selected."""


class InvalidAlgorithmError(Exception):
    """Raised when an invalid algorithm is given."""


class InvalidOrientationError(Exception):
    """Raised when an invalid cube orientation is specified."""


class ReplayError(Exception):
    """Raised when a Bluetooth replay file is missing or invalid."""
