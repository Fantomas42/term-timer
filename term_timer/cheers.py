"""Cheers generation for speedcube solves."""
from typing import TYPE_CHECKING
from typing import cast

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.methods.types import StepSummary
    from term_timer.solve import Solve


def get_cross_cheer(summary: list['StepSummary']) -> str:
    """
    Cheer based on Cross HTM.

    Returns:
        Cheer message

    """
    cross_step = next(
        (step for step in summary if step['name'] == 'Cross'),
        None,
    )

    if not cross_step:
        return ''

    htm = cross_step['moves_prettified'].metrics.htm
    if htm <= 6:
        return f'Cross solved efficiently in { htm } HTM.'

    return ''


def get_xcross_cheer(summary: list['StepSummary']) -> str:
    """
    Cheer based on XCross.

    Returns:
        Cheer message

    """
    xcross_step = next(
        (step for step in summary if 'XCross' in step['name']),
        None,
    )

    if xcross_step:
        return f'Solved with { xcross_step["name"] }.'

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


def get_time_cheer(solve: 'Solve') -> str:
    """
    Generate motivational time cheer.

    Returns:
        Time aimed message

    """
    target_time = solve.time * 0.95 / SECOND

    return (
        f'Keep pushing for sub-{ target_time:.1f}.'
    )


def get_fluency_cheer(solve: 'Solve') -> str:
    """
    Cheer based on solve fluency.

    Returns:
        Cheer message

    """
    if solve.fluency >= 90:
        return f'Buttery smooth! { solve.fluency }/100 fluency.'
    if solve.fluency >= 80:
        return f'Great flow - { solve.fluency }/100 fluency.'
    return ''


def get_tps_cheer(solve: 'Solve') -> str:
    """
    Cheer based on turning speed.

    Returns:
        Cheer message

    """
    if solve.tps >= 5.0:  # noqa: PLR2004
        return f'Lightning fingers! { solve.tps:.1f } TPS.'
    if solve.tps >= 4.5:  # noqa: PLR2004
        return f'Fast turning at { solve.tps:.1f } TPS.'
    return ''


def get_no_pauses_cheer(solve: 'Solve') -> str:
    """
    Cheer based on execution pauses.

    Returns:
        Cheer message

    """
    if solve.execution_pauses == 0:
        return 'Flawless lookahead - zero pauses!'
    if solve.execution_pauses <= 2:
        return 'Excellent lookahead throughout.'
    return ''


def get_skip_cheer(summary: list['StepSummary']) -> str:
    """
    Cheer based on OLL/PLL skips.

    Returns:
        Cheer message

    """
    skips = [
        step['name'] for step in summary
        if step['type'] == 'skipped'
    ]
    if 'OLL' in skips:
        return 'OLL skip!'
    if 'PLL' in skips:
        return 'PLL skip!'
    return ''


def get_recognition_cheer(solve: 'Solve') -> str:
    """
    Cheer based on fast recognition.

    Returns:
        Cheer message

    """
    if solve.time <= 0:
        return ''

    rec_percent = solve.recognition_time / solve.time * 100

    if rec_percent <= 20:
        return 'Sharp recognition throughout!'
    return ''


def get_auf_cheer(solve: 'Solve') -> str:
    """
    Cheer based on minimal AUFs.

    Returns:
        Cheer message

    """
    if solve.aufs <= 2:
        return 'Minimal AUFs - great prediction!'
    return ''


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
    if not solve.method_applied:
        return []

    summary = solve.method_applied.summary

    cheer_lines = [
        get_cross_cheer(summary),
        get_xcross_cheer(summary),
        get_skip_cheer(summary),
        get_missed_moves_cheer(solve),
        get_score_cheer(solve),
        get_fluency_cheer(solve),
        get_tps_cheer(solve),
        get_no_pauses_cheer(solve),
        get_recognition_cheer(solve),
        get_auf_cheer(solve),
        get_time_cheer(solve),
    ]

    return [cheer for cheer in cheer_lines if cheer]
