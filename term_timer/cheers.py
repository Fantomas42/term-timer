"""Cheers generation for speedcube solves."""
from typing import TYPE_CHECKING
from typing import cast

from cubing_algs.cases import get_case
from cubing_algs.transform.auf import remove_auf_moves

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
    if htm <= 4:
        return f'Optimal cross in { htm } HTM!'
    if htm <= 6:
        return f'Efficient cross in { htm } HTM.'

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
        return f'Lightning fingers! { solve.tps:.1f} TPS.'
    if solve.tps >= 4.5:  # noqa: PLR2004
        return f'Fast turning at { solve.tps:.1f} TPS.'
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
    if 'OLL' in skips and 'PLL' in skips:
        return 'Full last layer skip!'
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
    if not solve.aufs:
        return 'No AUFs - great case mastery.'
    if solve.aufs <= 2:
        return 'Minimal AUFs - great prediction.'
    return ''


def is_optimal_ll_step(step: 'StepSummary') -> bool:
    """
    Check if an OLL/PLL step was executed optimally with no AUFs.

    Returns:
        True if step is optimal with no AUFs

    """
    if step['type'] in {'skipped', 'virtual'}:
        return False

    if not step['case']:
        return False

    pre_auf = step['aufs'][0] or 0
    post_auf = step['aufs'][1] or 0
    if pre_auf or post_auf:
        return False

    step_case = get_case(step['name'], step['case'])
    optimal_htm = step_case.optimal_htm
    if not optimal_htm:
        return False

    actual_htm = step['moves_prettified'].transform(
        remove_auf_moves,
    ).metrics.htm

    return actual_htm == optimal_htm


def get_optimal_ll_cheer(summary: list['StepSummary']) -> str:
    """
    Cheer for optimal OLL or PLL execution.

    Checks if OLL or PLL was executed with optimal HTM and no AUFs.

    Returns:
        Cheer message

    """
    optimal_steps = [
        step['name']
        for step in summary
        if step['name'] in {'OLL', 'PLL'} and is_optimal_ll_step(step)
    ]

    if 'OLL' in optimal_steps and 'PLL' in optimal_steps:
        return 'Perfect last layer - optimal OLL and PLL!'
    if 'PLL' in optimal_steps:
        return 'Optimal PLL execution!'
    if 'OLL' in optimal_steps:
        return 'Optimal OLL execution!'

    return ''


def get_optimal_f2l_cheer(summary: list['StepSummary']) -> str:
    """
    Cheer for optimal F2L pair execution.

    Checks if any F2L pair was executed with optimal HTM.

    Returns:
        Cheer message

    """
    optimal_count = 0

    for step in summary:
        if step['type'] in {'skipped', 'virtual'}:
            continue

        step_name = step['name']
        if not step_name.startswith('F2L '):
            continue

        if not step['case']:
            continue

        step_code = step_name.split(' ')[0]
        step_case = get_case(step_code, step['case'])
        optimal_htm = step_case.optimal_htm

        if not optimal_htm:
            continue

        actual_htm = step['moves_prettified'].metrics.htm

        if actual_htm <= optimal_htm:
            optimal_count += 1

    if optimal_count == 4:
        return 'All F2L pairs solved optimally!'
    if optimal_count >= 2:
        return f'{ optimal_count } F2L pairs solved optimally.'

    return ''


def get_step_recognition_cheer(summary: list['StepSummary']) -> str:
    """
    Cheer for exceptionally fast recognition on specific steps.

    Checks if OLL or PLL had instant recognition (under 10% of step time).

    Returns:
        Cheer message

    """
    for step in summary:
        if step['type'] in {'skipped', 'virtual'}:
            continue

        if step['name'] not in {'OLL', 'PLL'}:
            continue

        if step['step_recognition_percent'] < 10:
            return f'Instant { step["name"] } recognition!'

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
        get_optimal_f2l_cheer(summary),
        get_optimal_ll_cheer(summary),
        get_missed_moves_cheer(solve),
        get_fluency_cheer(solve),
        get_tps_cheer(solve),
        get_no_pauses_cheer(solve),
        get_recognition_cheer(solve),
        get_step_recognition_cheer(summary),
        get_auf_cheer(solve),
        get_score_cheer(solve),
        get_time_cheer(solve),
    ]

    return [cheer for cheer in cheer_lines if cheer]
