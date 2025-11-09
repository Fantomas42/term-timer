"""Custom exception classes for the term-timer application."""


class CubeNotFoundError(Exception):
    """Raised when no Bluetooth cube is found during scanning."""


class InvalidCaseError(Exception):
    """Raised when an invalid training case is selected."""


class InvalidOrientationError(Exception):
    """Raised when an invalid cube orientation is specified."""
