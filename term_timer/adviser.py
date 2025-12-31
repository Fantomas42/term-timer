"""Performance advice generation for speedcube solves."""
from typing import TYPE_CHECKING
from typing import cast

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.solve import Solve


def get_performance_feedback(score: float) -> str:
    """
    Get overall performance feedback based on solve score.

    Returns:
        Rich-formatted feedback message

    """
    if score >= 16.0:  # noqa: PLR2004
        return 'Excellent solve! Keep up the great work.'
    if score >= 12.0:  # noqa: PLR2004
        return 'Solid performance with room for optimization.'
    if score >= 8.0:  # noqa: PLR2004
        return 'Good foundation - focus on refinement.'
    return 'Lots of potential for improvement!'


def get_recognition_advice(
    recognition_time: float,
    total_time: float,
) -> list[str]:
    """
    Generate advice about recognition time performance.

    Returns:
        List of advice messages (may be empty)

    """
    if recognition_time <= 0:
        return []

    rec_percent = (
        recognition_time / total_time * 100
    ) if total_time > 0 else 0

    if rec_percent > 40:
        return [
            f'Recognition time is high ({rec_percent:.1f}%). '
            'Practice case recognition with drills.',
        ]
    if rec_percent > 25:
        return [
            'Consider drilling cases that take longer '
            'to recognize.',
        ]
    return []


def get_execution_pauses_advice(execution_pauses: int) -> list[str]:
    """
    Generate advice about execution pauses.

    Returns:
        List of advice messages (may be empty)

    """
    if execution_pauses > 8:
        return [
            f'Many pauses detected ({execution_pauses}). '
            'Practice lookahead by solving slower '
            'while maintaining continuous turning.',
        ]
    if execution_pauses > 4:
        return [
            f'Reduce pauses ({execution_pauses}) '
            'by improving lookahead. '
            'Try to spot the next pair while solving '
            'the current one.',
        ]
    if execution_pauses == 0:
        return ['Perfect flow - no pauses detected!']
    return []


def get_fluency_advice(fluency: int) -> list[str]:
    """
    Generate advice about solve fluency.

    Returns:
        List of advice messages (may be empty)

    """
    if fluency <= 0:
        return []

    if fluency >= 85:
        return [
            f'Excellent fluency ({fluency}/100) - '
            'very smooth execution!',
        ]
    if fluency >= 70:
        return [
            f'Good fluency ({fluency}/100). '
            'Keep practicing smooth transitions.',
        ]
    if fluency < 50:
        return [
            f'Low fluency ({fluency}/100). '
            'Practice slow, consistent turning to build '
            'muscle memory.',
        ]
    return []


def get_missed_moves_advice(
    all_missed_moves: int,
    transition_missed_moves: int,
    execution_missed_moves: int,
) -> list[str]:
    """
    Generate advice about move efficiency.

    Returns:
        List of advice messages (may be empty)

    """
    advice = []

    if all_missed_moves > 10:
        advice.append(
            f'Many inefficient moves '
            f'({all_missed_moves} missed QTM). '
            'Review your algorithms and avoid '
            'do-undo sequences.',
        )
    elif all_missed_moves > 5:
        advice.append(
            f'Some inefficiency '
            f'({all_missed_moves} missed QTM). '
            'Double-check your algorithm execution.',
        )
    elif all_missed_moves == 0:
        advice.append(
            'Perfect efficiency - no wasted moves!',
        )

    if transition_missed_moves > execution_missed_moves:
        advice.append(
            'Many transition inefficiencies. '
            'Plan ahead to connect steps smoothly.',
        )

    return advice


def get_rotation_advice(rotations: int) -> list[str]:
    """
    Generate advice about cube rotations.

    Returns:
        List of advice messages (may be empty)

    """
    if rotations > 8:
        return [
            f'Too many rotations ({rotations}). '
            'Practice rotationless solutions and use '
            'back slots more.',
        ]
    if rotations > 4:
        return [
            f'Consider reducing rotations ({rotations}) '
            'for better TPS.',
        ]
    if rotations == 0:
        return ['Rotationless solve - excellent!']
    return []


def get_tps_advice(tps: float) -> list[str]:
    """
    Generate advice about turning speed (TPS).

    Returns:
        List of advice messages (may be empty)

    """
    if tps > 8.0:  # noqa: PLR2004
        return [
            f'Impressive turning speed ({tps:.2f} TPS)!',
        ]
    if tps < 4.0:  # noqa: PLR2004
        return [
            f'Low TPS ({tps:.2f}). '
            'Practice fingertricks and work on '
            'lookahead to maintain flow.',
        ]
    return []


def get_auf_advice(aufs: int) -> list[str]:
    """
    Generate advice about AUF (Adjust Upper Face) moves.

    Returns:
        List of advice messages (may be empty)

    """
    if aufs > 6:
        return [
            f'Excessive AUFs ({aufs}). '
            'Learn algorithm variations with '
            'better pre-AUF/post-AUF.',
        ]
    return []


def get_step_specific_advice(solve: 'Solve') -> list[str]:
    """
    Generate advice for the slowest step in the solve.

    Returns:
        List of advice messages (may be empty)

    """
    if not solve.method_applied:
        return []

    slowest_step = None
    slowest_percent = 0.0
    for step in solve.method_applied.summary:
        if (
            step['type'] not in {'skipped', 'virtual'}
            and step['total_percent'] > slowest_percent
        ):
            slowest_percent = step['total_percent']
            slowest_step = step

    if not slowest_step or slowest_percent <= 35:
        return []

    advice = []
    step_name = slowest_step['name']
    advice.append(
        f'{step_name} took {slowest_percent:.1f}% '
        'of solve time. Focus practice on this step.',
    )

    # Specific step advice
    if 'F2L' in step_name:
        advice.append(
            'F2L tip: Practice slow solves '
            'focusing on lookahead.',
        )
    elif 'OLL' in step_name or 'PLL' in step_name:
        if slowest_step['recognition_percent'] > 15:
            advice.append(
                'Practice case recognition drills '
                'for faster identification.',
            )
        else:
            advice.append(
                'Drill this algorithm until you can '
                'execute it in under 2 seconds.',
            )
    elif (
        'Cross' in step_name
        and slowest_step['moves_prettified'].metrics.htm > 8
    ):
        advice.append(
            'Plan a more efficient cross '
            '(target 8 moves or fewer).',
        )

    return advice


def get_motivational_closing(score: float, time: float) -> str:
    """
    Generate motivational closing message.

    Returns:
        Rich-formatted motivational message

    """
    if score >= 14.0:  # noqa: PLR2004
        target = int(time / SECOND) - 2
        return (
            f'Keep pushing for sub-{target} seconds!'
        )
    return (
        'Every solve is a learning opportunity. '
        'Stay consistent!'
    )


def generate_solve_advices(solve: 'Solve') -> list[str]:
    """
    Generate constructive advices based on solve performance metrics.

    Analyzes recognition time, execution quality, efficiency, and step
    performance to provide actionable recommendations for improvement.

    Args:
        solve: Solve instance with reconstruction data

    Returns:
        List of strings with personalized advice and motivation

    """
    advice_lines = []

    score = cast('float', solve.score)
    advice_lines.append(
        get_performance_feedback(
            score,
        ),
    )

    advice_lines.extend(
        get_recognition_advice(
            solve.recognition_time,
            solve.time,
        ),
    )
    advice_lines.extend(
        get_execution_pauses_advice(
            solve.execution_pauses,
        ),
    )
    advice_lines.extend(
        get_fluency_advice(
            solve.fluency,
        ),
    )
    advice_lines.extend(
        get_missed_moves_advice(
            solve.all_missed_moves,
            solve.transition_missed_moves,
            solve.execution_missed_moves,
        ),
    )
    advice_lines.extend(
        get_rotation_advice(
            solve.rotations,
        ),
    )
    advice_lines.extend(
        get_tps_advice(
            solve.tps,
        ),
    )
    advice_lines.extend(
        get_auf_advice(
            solve.aufs,
        ),
    )
    advice_lines.extend(
        get_step_specific_advice(
            solve,
        ),
    )

    advice_lines.append(
        get_motivational_closing(
            score,
            solve.time,
        ),
    )

    return advice_lines
