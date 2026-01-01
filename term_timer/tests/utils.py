"""Utils for tests."""
from typing import cast

from term_timer.methods.base import Analyser
from term_timer.solve import Solve


def get_method_applied(solve: Solve) -> Analyser:
    """
    Get method_applied, asserting it's not None in tests.

    Returns:
        The method_applied Analyser instance.

    """
    return cast('Analyser', solve.method_applied)
