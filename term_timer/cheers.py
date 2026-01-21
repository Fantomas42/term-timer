"""Cheers generation for speedcube solves."""
from typing import TYPE_CHECKING
from typing import cast

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.solve import Solve


def get_cross_cheer(solve: 'Solve') -> str:
    """
    Cheer based on Cross HTM.

    Returns:
        Cheer message

    """
    cross_step = None
    for step in solve.method_applied.summary:
        if step['name'] == 'Cross':
            cross_step = step
            break

    if not cross_step:
        return ''

    htm = cross_step['moves_prettified'].metrics.htm
    if htm <= 6:
        return f'Cross solved efficiently in { htm } HTM.'

    return ''


def get_xcross_cheer(solve: 'Solve') -> str:
    """
    Cheer based on XCross.

    Returns:
        Cheer message

    """
    for step in solve.method_applied.summary:
        if 'XCross' in step['name']:
            return f'Solve made with an { step["name"] }.'

    return ''


def get_missed_moves_cheer(solve: 'Solve') -> str:
    """
    Cheer based on missed moves.

    Returns:
        Cheer message

    """
    if not solve.all_missed_moves:
        return 'Perfect execution - no wasted moves!'

    return ''


def get_score_cheer(solve: 'Solve') -> str:
    """
    Cheer based on solve score.

    Returns:
        Cheer message

    """
    score = cast('float', solve.score)

    if score >= 16:
        return f'Excellent solve score of { score:.2f}.'

    return ''


def get_motivational_time(solve: 'Solve') -> str:
    """
    Generate motivational time cheer.

    Returns:
        Time aimed message

    """
    target_time = solve.time * 0.95 / SECOND

    return (
        f'Keep pushing for sub-{ target_time:.1f} seconds.'
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
        get_cross_cheer(
            solve,
        ),
        get_xcross_cheer(
            solve,
        ),
        get_missed_moves_cheer(
            solve,
        ),
        get_score_cheer(
            solve,
        ),
        get_motivational_time(
            solve,
        ),
    ]

    return [cheer for cheer in cheer_lines if cheer]
