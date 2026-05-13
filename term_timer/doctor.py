"""Diagnostics generation for speedcube solves."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from term_timer.solve import Solve


def generate_solve_diagnostics(solve: 'Solve') -> list[str]:  # noqa: ARG001
    """
    Generate diagnostics for a solve.

    Args:
        solve: The solve to diagnose.

    Returns:
        List of diagnostic strings.

    """
    return []
