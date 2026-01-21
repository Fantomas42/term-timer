"""Cheers generation for speedcube solves."""
from typing import TYPE_CHECKING
from typing import cast

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.solve import Solve


def get_score_cheer(solve: 'Solve') -> str:
    """
    Cheer based on solve score.

    Returns:
        Cheer message

    """
    score = cast('float', solve.score)

    if score >= 16:
        return 'Excellent solve score! Keep up the great work.'

    return ''


def get_motivational_time(solve: 'Solve') -> str:
    """
    Generate motivational time cheer.

    Returns:
        Time aimed message

    """
    target_time = solve.time * 0.95 / SECOND

    return (
        f'Keep pushing for sub-{ target_time:.1f} seconds!'
    )


def generate_solve_cheers(solve: 'Solve') -> list[str]:
    """
    Generate cheers based on solve performance metrics.

    Analyzes recognition time, execution quality, efficiency, and step
    performance to highlight key successes in the solve.

    Args:
        solve: Solve instance with reconstruction data

    Returns:
        List of strings with cheers and motivation

    """
    cheer_lines = [
        get_score_cheer(
            solve,
        ),
        get_motivational_time(
            solve,
        ),
    ]

    return [cheer for cheer in cheer_lines if cheer]
