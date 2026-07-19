"""
Comprehensive solve diagnostics and issue detection.

This module analyzes solve performance at both global and step-specific levels,
identifying issues across multiple categories with severity ratings and
estimated impact. Output is formatted to generate personalized improvement
recommendations.
"""
from enum import StrEnum
from operator import itemgetter
from typing import TYPE_CHECKING
from typing import Final
from typing import TypedDict

from cubing_algs.cases import get_case

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.methods.annotations import StepSummary
    from term_timer.solve import Solve

TPS_LOW_THRESHOLD: Final = 1.5
TPS_MEDIUM_THRESHOLD: Final = 2.3
TPS_EXPECTED_MIN: Final = 2.5

PAUSE_PERCENT_TARGET: Final = 10.0
PAUSE_PERCENT_HIGH_THRESHOLD: Final = 15.0
PAUSE_PERCENT_CRITICAL_THRESHOLD: Final = 20.0

FLUENCY_LOW_THRESHOLD: Final = 55
FLUENCY_MEDIUM_THRESHOLD: Final = 60
FLUENCY_IMPACT_FACTOR: Final = 0.15

TIMING_MEDIUM_FACTOR: Final = 1.1
TIMING_HIGH_FACTOR: Final = 1.25


class DiagnosticSeverity(StrEnum):
    """Severity levels for detected issues."""

    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


class DiagnosticCategory(StrEnum):
    """Categories of solve diagnostics."""

    EFFICIENCY_MOVECOUNT = 'efficiency_movecount'
    EFFICIENCY_TRANSITIONS = 'efficiency_transitions'
    EFFICIENCY_ALGORITHMS = 'efficiency_algorithms'
    EXECUTION_SPEED = 'execution_speed'
    EXECUTION_PAUSES = 'execution_pauses'
    EXECUTION_FLUENCY = 'execution_fluency'
    RECOGNITION_SLOW = 'recognition_slow'
    PLANNING_CROSS = 'planning_cross'
    PLANNING_LOOKAHEAD = 'planning_lookahead'
    AUFS_EXCESSIVE = 'aufs_excessive'
    ROTATIONS_EXCESSIVE = 'rotations_excessive'
    TIMING_DISTRIBUTION = 'timing_distribution'


class Diagnostic(TypedDict):
    """
    Represents a detected performance diagnostic.

    Attributes:
        severity: How critical the issue is (critical/high/medium/low)
        category: Diagnostic category (efficiency, execution, recognition, etc.)
        impact_seconds: Estimated potential time improvement (seconds)
        location: Where the issue occurs ('global' or step name)
        metric_name: Name of the metric involved
        actual_value: Measured value
        expected_value: Target/norm value
        description: Human-readable issue description
        recommendation: Specific training exercise to address issue
        command: Command to practice this issue

    """

    severity: DiagnosticSeverity
    category: DiagnosticCategory
    impact_seconds: float
    location: str
    metric_name: str
    actual_value: float
    expected_value: float | tuple[float, float]
    description: str
    recommendation: str
    command: str


class DiagnosticGroup(TypedDict):
    """
    Represents diagnostics aggregated by location.

    Attributes:
        location: Where the issues occur ('global' or step name)
        command: Command to practice the issues of the group
        impact_seconds: Sum of estimated time improvements (seconds)
        diagnostics: Diagnostics detected at this location

    """

    location: str
    command: str
    impact_seconds: float
    diagnostics: list[Diagnostic]


def check_global_efficiency(solve: 'Solve') -> list[Diagnostic]:
    """
    Detect efficiency issues at the global solve level.

    Checks for:
    - Wasted moves within step execution (do-undo sequences)
    - Transition inefficiencies between steps

    Args:
        solve: Solve instance with reconstruction data

    Returns:
        List of detected efficiency issues

    """
    issues: list[Diagnostic] = []

    step_missed_moves = solve.step_missed_moves
    transition_missed_moves = solve.transition_missed_moves
    spm = solve.move_speed * 1.05 / SECOND

    if step_missed_moves > 10:
        issues.append(
            {
                'severity': DiagnosticSeverity.CRITICAL,
                'category': DiagnosticCategory.EFFICIENCY_MOVECOUNT,
                'impact_seconds': step_missed_moves * spm,
                'location': 'global',
                'metric_name': 'step_missed_moves',
                'actual_value': float(step_missed_moves),
                'expected_value': 0.0,
                'description': (
                    f'Solve contains {step_missed_moves} missed QTM '
                    'within steps (wasted moves from do-undo sequences or '
                    'inefficient execution). This significantly impacts '
                    'solve time.'
                ),
                'recommendation': (
                    'Practice slow solves focusing on move efficiency. '
                    'Review your algorithms to eliminate do-undo sequences. '
                    'Record and analyze solves to identify common '
                    'waste patterns.'
                ),
                'command': '',
            },
        )
    elif step_missed_moves > 5:
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.EFFICIENCY_MOVECOUNT,
                'impact_seconds': step_missed_moves * spm,
                'location': 'global',
                'metric_name': 'step_missed_moves',
                'actual_value': float(step_missed_moves),
                'expected_value': 0.0,
                'description': (
                    f'Solve contains {step_missed_moves} missed QTM '
                    'within steps. Some inefficiency detected in move '
                    'execution.'
                ),
                'recommendation': (
                    'Focus on executing algorithms cleanly without '
                    'unnecessary corrections. Double-check algorithm '
                    'execution for common cases.'
                ),
                'command': '',
            },
        )

    if transition_missed_moves > 5:
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.EFFICIENCY_TRANSITIONS,
                'impact_seconds': transition_missed_moves * spm,
                'location': 'global',
                'metric_name': 'transition_missed_moves',
                'actual_value': float(transition_missed_moves),
                'expected_value': 0.0,
                'description': (
                    f'{transition_missed_moves} missed moves occurred during '
                    'transitions between steps. Poor planning between stages.'
                ),
                'recommendation': (
                    'Practice lookahead drills. Plan the next step while '
                    'executing the current one. Work on smooth transitions '
                    'between Cross-F2L, F2L pairs, and F2L-OLL.'
                ),
                'command': '',
            },
        )

    return issues


def check_global_execution(solve: 'Solve') -> list[Diagnostic]:
    """
    Detect execution issues at the global solve level.

    Checks for:
    - Low TPS (turns per second)
    - Excessive pauses
    - Poor fluency

    Args:
        solve: Solve instance with reconstruction data

    Returns:
        List of detected execution issues

    """
    issues: list[Diagnostic] = []

    if solve.tps < TPS_LOW_THRESHOLD:
        estimated_impact = (
            (1 / solve.tps - 1 / TPS_EXPECTED_MIN) * len(solve.solution)
            if solve.tps > 0 else 0
        )
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.EXECUTION_SPEED,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'tps',
                'actual_value': solve.tps,
                'expected_value': TPS_EXPECTED_MIN,
                'description': (
                    f'Low TPS ({solve.tps:.2f}). Turning speed needs '
                    'improvement for competitive times.'
                ),
                'recommendation': (
                    'Practice fingertricks for all basic moves. '
                    'Focus on smooth, continuous turning. '
                    'Drill algorithms at increasing speeds while maintaining '
                    'accuracy. Consider ergonomic algorithms for better flow.'
                ),
                'command': '',
            },
        )
    elif solve.tps < TPS_MEDIUM_THRESHOLD:
        estimated_impact = (
            (1 / solve.tps - 1 / TPS_EXPECTED_MIN) * len(solve.solution)
            if solve.tps > 0 else 0
        )
        issues.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.EXECUTION_SPEED,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'tps',
                'actual_value': solve.tps,
                'expected_value': TPS_EXPECTED_MIN,
                'description': (
                    f'Moderate TPS ({solve.tps:.2f}). Room for improvement '
                    'in turning speed.'
                ),
                'recommendation': (
                    'Work on fingertrick efficiency and lookahead to '
                    'maintain continuous turning without pauses.'
                ),
                'command': '',
            },
        )

    pause_percent = (
        100 * solve.execution_pause_time / solve.time
        if solve.time else 0.0
    )
    pause_expected = (PAUSE_PERCENT_TARGET, PAUSE_PERCENT_HIGH_THRESHOLD)
    if pause_percent > PAUSE_PERCENT_CRITICAL_THRESHOLD:
        estimated_impact = solve.execution_pause_time / SECOND
        issues.append(
            {
                'severity': DiagnosticSeverity.CRITICAL,
                'category': DiagnosticCategory.EXECUTION_PAUSES,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'execution_pause_percent',
                'actual_value': pause_percent,
                'expected_value': pause_expected,
                'description': (
                    f'Pauses eat {pause_percent:.1f}% of solve time '
                    f'({solve.execution_pauses} pauses). '
                    'Significant disruption to solve flow.'
                ),
                'recommendation': (
                    'Practice slow solves at 50-70% speed while maintaining '
                    'continuous turning. Focus on seeing the next step before '
                    'finishing the current one. Gradually increase speed while '
                    'maintaining zero pauses.'
                ),
                'command': '',
            },
        )
    elif pause_percent > PAUSE_PERCENT_HIGH_THRESHOLD:
        estimated_impact = solve.execution_pause_time / SECOND
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.EXECUTION_PAUSES,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'execution_pause_percent',
                'actual_value': pause_percent,
                'expected_value': pause_expected,
                'description': (
                    f'Pauses eat {pause_percent:.1f}% of solve time '
                    f'({solve.execution_pauses} pauses). '
                    'Lookahead needs improvement.'
                ),
                'recommendation': (
                    # TODO: review
                    'Work on F2L lookahead by solving pairs slower while '
                    'tracking the next pair. Practice recognizing cases '
                    'during execution rather than after.'
                ),
                'command': '',
            },
        )

    fluency = solve.fluency
    if fluency < FLUENCY_LOW_THRESHOLD:
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.EXECUTION_FLUENCY,
                'impact_seconds': (
                    solve.execution_time / SECOND
                    * (FLUENCY_LOW_THRESHOLD - fluency)
                    / FLUENCY_LOW_THRESHOLD
                    * FLUENCY_IMPACT_FACTOR
                ),
                'location': 'global',
                'metric_name': 'fluency',
                'actual_value': float(fluency),
                'expected_value': (float(FLUENCY_LOW_THRESHOLD), 100.0),
                'description': (
                    f'Very low fluency ({fluency}/100). Highly inconsistent '
                    'timing between moves indicates lack of muscle memory.'
                ),
                'recommendation': (
                    'Practice algorithms with a metronome to build consistent '
                    'rhythm. Execute each algorithm 50-100 times daily until '
                    'it becomes automatic. Focus on smooth, even turning.'
                ),
                'command': '',
            },
        )
    elif fluency < FLUENCY_MEDIUM_THRESHOLD:
        issues.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.EXECUTION_FLUENCY,
                'impact_seconds': (
                    solve.execution_time / SECOND
                    * (FLUENCY_MEDIUM_THRESHOLD - fluency)
                    / FLUENCY_MEDIUM_THRESHOLD
                    * FLUENCY_IMPACT_FACTOR
                ),
                'location': 'global',
                'metric_name': 'fluency',
                'actual_value': float(fluency),
                'expected_value': (float(FLUENCY_MEDIUM_THRESHOLD), 100.0),
                'description': (
                    f'Moderate fluency ({fluency}/100). Some inconsistency '
                    'in turning rhythm.'
                ),
                'recommendation': (
                    'Continue practicing smooth transitions between moves. '
                    'Work on consistent fingertricks and avoid regrips '
                    'during algorithms.'
                ),
                'command': '',
            },
        )

    return issues


def check_global_rotation(solve: 'Solve') -> list[Diagnostic]:
    """
    Detect rotation-related issues at the global solve level.

    Checks for:
    - Excessive cube rotations
    - Excessive AUF moves

    Args:
        solve: Solve instance with reconstruction data

    Returns:
        List of detected rotation issues

    """
    issues: list[Diagnostic] = []

    rotations = solve.rotations
    spm = solve.move_speed * 1.2 / SECOND

    if rotations > 8:
        estimated_impact = rotations * spm
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.ROTATIONS_EXCESSIVE,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'rotations',
                'actual_value': float(rotations),
                'expected_value': (0.0, 4.0),
                'description': (
                    f'Excessive rotations ({rotations}). Too much time spent '
                    'rotating the cube instead of solving.'
                ),
                'recommendation': (
                    'Learn rotationless F2L solutions. Practice using back '
                    'slots (BR, BL) without rotating. Study wide move '
                    'alternatives (Rw, Lw) to avoid rotations.'
                ),
                'command': '',
            },
        )
    elif rotations > 4:
        estimated_impact = rotations * spm
        issues.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.ROTATIONS_EXCESSIVE,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'rotations',
                'actual_value': float(rotations),
                'expected_value': (0.0, 4.0),
                'description': (
                    f'Moderate rotations ({rotations}). Could be reduced '
                    'for better TPS.'
                ),
                'recommendation': (
                    'Identify which F2L cases cause you to rotate and learn '
                    'rotation-free alternatives. Practice back slot insertions.'
                ),
                'command': '',
            },
        )

    aufs = solve.aufs
    if aufs > 6:
        estimated_impact = aufs * solve.move_speed * 1.05 / SECOND
        issues.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.AUFS_EXCESSIVE,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'aufs',
                'actual_value': float(aufs),
                'expected_value': (0.0, 6.0),
                'description': (
                    f'Excessive AUFs ({aufs} QTM). Too many U-face adjustments '
                    'before/after algorithms.'
                ),
                'recommendation': (
                    'Learn algorithm variations with different pre-AUF and '
                    'post-AUF. Study which OLL/PLL algorithm variants minimize '
                    'total AUF count. Practice recognizing optimal angles.'
                ),
                'command': '',
            },
        )

    return issues


def check_global_recognition(solve: 'Solve') -> list[Diagnostic]:
    """
    Detect recognition-related issues at the global solve level.

    Checks for:
    - Excessive recognition time
    - Poor recognition vs execution balance

    Args:
        solve: Solve instance with reconstruction data

    Returns:
        List of detected recognition issues

    """
    issues: list[Diagnostic] = []

    if not solve.method_applied:
        return issues
    solve_norms = solve.method_applied.norms.get('solve')
    if solve_norms is None:
        return issues
    rec_norm = solve_norms['recognition']
    rec_norm_max = rec_norm.high
    # No-flag range: HIGH fires past 1.25x the norm, CRITICAL past 2x.
    rec_limit = rec_norm_max * 1.25
    rec_expected = (rec_norm.low, rec_limit)

    rec_percent = solve.recognition_percent

    if rec_percent > rec_norm_max * 2:
        estimated_impact = solve.recognition_pause_time / SECOND
        issues.append(
            {
                'severity': DiagnosticSeverity.CRITICAL,
                'category': DiagnosticCategory.RECOGNITION_SLOW,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'recognition_percent',
                'actual_value': rec_percent,
                'expected_value': rec_expected,
                'description': (
                    f'Very high recognition time ({rec_percent:.1f}%). '
                    'Spending too much time identifying cases instead of '
                    'solving.'
                ),
                'recommendation': (
                    'Drill case recognition separately from execution. '
                    'Use flashcard apps for OLL/PLL recognition. '
                    'Practice recognition during inspection for F2L pairs. '
                    'Time your recognition to track improvement.'
                ),
                'command': '',
            },
        )
    elif rec_percent > rec_limit:
        estimated_impact = solve.recognition_pause_time / SECOND
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.RECOGNITION_SLOW,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'recognition_percent',
                'actual_value': rec_percent,
                'expected_value': rec_expected,
                'description': (
                    f'High recognition time ({rec_percent:.1f}%). '
                    'Case identification is slowing down the solve.'
                ),
                'recommendation': (
                    'Increase frequency of case recognition drills. '
                    'Focus on pattern recognition for slow-to-identify cases. '
                    'Practice F2L pair tracking during cross.'
                ),
                'command': '',
            },
        )

    return issues


def check_step_cross(
    solve: 'Solve',
    step: 'StepSummary',
) -> list[Diagnostic]:
    """
    Detect issues specific to the Cross step.

    Checks for:
    - Inefficient cross (above move norm)
    - High cross time percentage

    Args:
        solve: Solve instance with reconstruction data
        step: Step summary for Cross

    Returns:
        List of detected Cross-specific diagnostics

    """
    diagnostics: list[Diagnostic] = []

    if not solve.method_applied:
        return diagnostics

    if step['type'] == 'skipped':
        return diagnostics

    norms = solve.method_applied.norms
    step_name = step['name']
    # Detection cannot distinguish a planned XCross from a fortuitous
    # merge of cross and F2L pairs, so extended crosses are compared to
    # the combined norm (cross + n pairs) instead of planned-XCross norms.
    pair_count = step_name.count('X')
    move_norm = norms['moves']['Cross']
    if pair_count:
        pair_norm = norms['moves']['F2L'] / 4
        move_norm += pair_count * pair_norm
    percent_norm = norms['percent'].get(step_name, norms['percent']['Cross'])
    # Displayed range matches the triggers below: target is the move
    # norm, with a +2 tolerance before the MEDIUM diagnostic fires.
    expected_moves: tuple[float, float] = (
        float(move_norm), float(move_norm + 2),
    )
    spm = solve.move_speed / SECOND
    htm = step['moves_prettified'].metrics.htm

    if htm > move_norm + 4:
        extra_moves = htm - move_norm
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.PLANNING_CROSS,
                'impact_seconds': extra_moves * spm,
                'location': step_name,
                'metric_name': 'htm',
                'actual_value': float(htm),
                'expected_value': expected_moves,
                'description': (
                    f'Very inefficient cross ({htm} HTM). Optimal cross '
                    f'should be {int(move_norm + 2)} moves or fewer.'
                ),
                'recommendation': (
                    'Practice cross planning during inspection. '
                    'Learn efficient cross solutions for different scrambles. '
                    'Study cross optimization techniques (tracking pieces, '
                    'planning edge insertion order). Use cross trainers online.'
                ),
                'command': 'term-timer train -s cross',
            },
        )
    elif htm > move_norm + 2:
        extra_moves = htm - move_norm
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.PLANNING_CROSS,
                'impact_seconds': extra_moves * spm,
                'location': step_name,
                'metric_name': 'htm',
                'actual_value': float(htm),
                'expected_value': expected_moves,
                'description': (
                    f'Inefficient cross ({htm} HTM). Could be optimized '
                    f'to {int(move_norm + 2)} moves or fewer.'
                ),
                'recommendation': (
                    'Work on cross planning during inspection. '
                    'Try to find fewer-move solutions before executing.'
                ),
                'command': 'term-timer train -s cross',
            },
        )

    percent_limit = percent_norm * TIMING_MEDIUM_FACTOR
    if step['total_percent'] > percent_limit:
        severity = (
            DiagnosticSeverity.HIGH
            if step['total_percent'] > percent_norm * TIMING_HIGH_FACTOR
            else DiagnosticSeverity.MEDIUM
        )
        estimated_impact = (
            (step['total_percent'] - percent_norm) / 100
            * solve.time / SECOND
        )
        diagnostics.append(
            {
                'severity': severity,
                'category': DiagnosticCategory.TIMING_DISTRIBUTION,
                'impact_seconds': estimated_impact,
                'location': step_name,
                'metric_name': 'total_percent',
                'actual_value': step['total_percent'],
                'expected_value': (percent_norm, percent_limit),
                'description': (
                    f'Cross took {step["total_percent"]:.1f}% of solve time. '
                    'Too much time spent on cross relative to total solve.'
                ),
                'recommendation': (
                    'Practice cross execution speed. Work on planning '
                    'entire cross during inspection. Consider planning '
                    'first F2L pair during cross execution.'
                ),
                'command': 'term-timer train -s cross',
            },
        )

    return diagnostics


def check_step_f2l(
    solve: 'Solve',
    step: 'StepSummary',
) -> list[Diagnostic]:
    """
    Detect issues specific to the F2L step.

    Checks for:
    - Excessive F2L time percentage
    - High recognition time in F2L

    Only called for the aggregated virtual F2L step (CF4OP) or the single
    F2L step (CFOP). Individual pair substeps are not checked here.

    Args:
        solve: Solve instance with reconstruction data
        step: Step summary for the F2L step or virtual aggregate

    Returns:
        List of detected F2L-specific diagnostics

    """
    diagnostics: list[Diagnostic] = []

    if not solve.method_applied:
        return diagnostics

    norms = solve.method_applied.norms
    recognition = norms.get('recognition', {})
    step_name = step['name']
    percent_norm = norms['percent']['F2L']
    rec_norm = recognition.get(step_name) or recognition.get('F2L')

    percent_limit = percent_norm * TIMING_MEDIUM_FACTOR
    if step['total_percent'] > percent_limit:
        severity = (
            DiagnosticSeverity.HIGH
            if step['total_percent'] > percent_norm * TIMING_HIGH_FACTOR
            else DiagnosticSeverity.MEDIUM
        )
        estimated_impact = (
            (step['total_percent'] - percent_norm) / 100
            * solve.time / SECOND
        )
        diagnostics.append(
            {
                'severity': severity,
                'category': DiagnosticCategory.TIMING_DISTRIBUTION,
                'impact_seconds': estimated_impact,
                'location': step_name,
                'metric_name': 'total_percent',
                'actual_value': step['total_percent'],
                'expected_value': (percent_norm, percent_limit),
                'description': (
                    f'{step_name} took {step["total_percent"]:.1f}% '
                    'of solve time. F2L is taking too long.'
                ),
                'recommendation': (
                    'Focus on F2L efficiency and lookahead. '
                    'Practice slow solves maintaining continuous turning. '
                    'Work on predicting pair locations during cross. '
                    'Learn efficient F2L algorithms for common cases.'
                ),
                'command': 'term-timer train -s f2l',
            },
        )

    if rec_norm is not None and (
            step['step_recognition_percent'] > rec_norm.high
    ):
        estimated_impact = (
            (step['step_recognition_percent'] - rec_norm.high) / 100
            * step['total'] / SECOND
        )
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.PLANNING_LOOKAHEAD,
                'impact_seconds': estimated_impact,
                'location': step_name,
                'metric_name': 'step_recognition_percent',
                'actual_value': step['step_recognition_percent'],
                'expected_value': rec_norm,
                'description': (
                    f'{step_name} recognition is '
                    f'{step["step_recognition_percent"]:.1f}% of step time. '
                    'Poor lookahead - spending too long finding next pair.'
                ),
                'recommendation': (
                    'Practice F2L lookahead drills. Track the next pair '
                    'while solving current one. Solve at 50% speed while '
                    'maintaining continuous turning. '
                    'Practice blind F2L (solve without looking at cube).'
                ),
                'command': 'term-timer train -s f2l',
            },
        )

    return diagnostics


def check_step_oll(
    solve: 'Solve',
    step: 'StepSummary',
) -> list[Diagnostic]:
    """
    Detect issues specific to the OLL step.

    Checks for:
    - High recognition time
    - Excessive move count

    Args:
        solve: Solve instance with reconstruction data
        step: Step summary for OLL

    Returns:
        List of detected OLL-specific diagnostics

    """
    diagnostics: list[Diagnostic] = []

    if not solve.method_applied:
        return diagnostics

    if step['type'] == 'skipped' or step['case'] == 'SKIP':
        return diagnostics

    norms = solve.method_applied.norms
    case_name = step['case']
    oll_cmd = (
        f'term-timer train -s oll -c "{case_name}"' if case_name else ''
    )
    rec_norm = norms.get('recognition', {}).get('OLL')

    if rec_norm is not None and (
            step['step_recognition_percent'] > rec_norm.high
    ):
        estimated_impact = (
            (step['step_recognition_percent'] - rec_norm.high) / 100
            * step['total'] / SECOND
        )
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.RECOGNITION_SLOW,
                'impact_seconds': estimated_impact,
                'location': 'OLL',
                'metric_name': 'step_recognition_percent',
                'actual_value': step['step_recognition_percent'],
                'expected_value': rec_norm,
                'description': (
                    f'OLL recognition is '
                    f'{step["step_recognition_percent"]:.1f}% '
                    'of step time. Case identification is too slow.'
                ),
                'recommendation': (
                    'Practice OLL recognition drills with flashcards or apps. '
                    'Focus on recognizing patterns (dot, line, L-shape, etc.) '
                    'rather than memorizing all 57 cases visually. '
                    'Learn 2-look OLL patterns first if not comfortable with '
                    'full OLL.'
                ),
                'command': oll_cmd,
            },
        )

    percent_norm = norms['percent']['OLL']
    percent_limit = percent_norm * TIMING_MEDIUM_FACTOR
    if step['total_percent'] > percent_limit:
        severity = (
            DiagnosticSeverity.HIGH
            if step['total_percent'] > percent_norm * TIMING_HIGH_FACTOR
            else DiagnosticSeverity.MEDIUM
        )
        estimated_impact = (
            (step['total_percent'] - percent_norm) / 100
            * solve.time / SECOND
        )
        diagnostics.append(
            {
                'severity': severity,
                'category': DiagnosticCategory.TIMING_DISTRIBUTION,
                'impact_seconds': estimated_impact,
                'location': 'OLL',
                'metric_name': 'total_percent',
                'actual_value': step['total_percent'],
                'expected_value': (percent_norm, percent_limit),
                'description': (
                    f'OLL took {step["total_percent"]:.1f}% of solve time. '
                    'Too much time spent on OLL relative to total solve.'
                ),
                'recommendation': (
                    'Drill OLL algorithms for speed and recognition. '
                    'Practice recognizing the case during the last '
                    'F2L pair.'
                ),
                'command': oll_cmd,
            },
        )

    if not case_name:
        return diagnostics

    htm = step['moves_prettified'].metrics.htm
    optimal_htm = float(get_case('OLL', case_name).optimal_htm)
    target_htm = optimal_htm + 2  # AUF allowance
    htm_limit = (optimal_htm * 1.33) + 2

    if htm > htm_limit:
        extra_moves = htm - target_htm
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.EFFICIENCY_ALGORITHMS,
                'impact_seconds': extra_moves * solve.move_speed / SECOND,
                'location': 'OLL',
                'metric_name': 'htm',
                'actual_value': float(htm),
                'expected_value': (optimal_htm, htm_limit),
                'description': (
                    f'OLL used {htm} HTM, while the case optimal is '
                    f'{optimal_htm:.0f} HTM plus AUF. May be using '
                    'a sub-optimal algorithm or wrong variant.'
                ),
                'recommendation': (
                    'Review your OLL algorithm choice for this case. '
                    'Consider learning faster/shorter algorithms. '
                    'Check if you used the correct algorithm or made '
                    'execution errors.'
                ),
                'command': oll_cmd,
            },
        )

    return diagnostics


def check_step_pll(
    solve: 'Solve',
    step: 'StepSummary',
) -> list[Diagnostic]:
    """
    Detect issues specific to the PLL step.

    Checks for:
    - High recognition time
    - Excessive move count
    - Excessive AUF

    Args:
        solve: Solve instance with reconstruction data
        step: Step summary for PLL

    Returns:
        List of detected PLL-specific diagnostics

    """
    diagnostics: list[Diagnostic] = []

    if not solve.method_applied:
        return diagnostics

    if step['type'] == 'skipped' or step['case'] == 'SKIP':
        return diagnostics

    norms = solve.method_applied.norms
    case_name = step['case']
    pll_cmd = (
        f'term-timer train -s pll -c "{case_name}"' if case_name else ''
    )
    rec_norm = norms.get('recognition', {}).get('PLL')

    if rec_norm is not None and (
            step['step_recognition_percent'] > rec_norm.high
    ):
        estimated_impact = (
            (step['step_recognition_percent'] - rec_norm.high) / 100
            * step['total'] / SECOND
        )
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.RECOGNITION_SLOW,
                'impact_seconds': estimated_impact,
                'location': 'PLL',
                'metric_name': 'step_recognition_percent',
                'actual_value': step['step_recognition_percent'],
                'expected_value': rec_norm,
                'description': (
                    f'PLL recognition is '
                    f'{step["step_recognition_percent"]:.1f}% '
                    'of step time. Case identification is too slow.'
                ),
                'recommendation': (
                    'Practice 2-side PLL recognition (looking at 2 adjacent '
                    'sides to identify case). Drill PLL recognition with '
                    'apps/flashcards. Focus on headlights, blocks, and bars '
                    'as recognition features. Learn to recognize PLL during '
                    'OLL execution.'
                ),
                'command': pll_cmd,
            },
        )

    percent_norm = norms['percent']['PLL']
    percent_limit = percent_norm * TIMING_MEDIUM_FACTOR
    if step['total_percent'] > percent_limit:
        severity = (
            DiagnosticSeverity.HIGH
            if step['total_percent'] > percent_norm * TIMING_HIGH_FACTOR
            else DiagnosticSeverity.MEDIUM
        )
        estimated_impact = (
            (step['total_percent'] - percent_norm) / 100
            * solve.time / SECOND
        )
        diagnostics.append(
            {
                'severity': severity,
                'category': DiagnosticCategory.TIMING_DISTRIBUTION,
                'impact_seconds': estimated_impact,
                'location': 'PLL',
                'metric_name': 'total_percent',
                'actual_value': step['total_percent'],
                'expected_value': (percent_norm, percent_limit),
                'description': (
                    f'PLL took {step["total_percent"]:.1f}% of solve time. '
                    'Too much time spent on PLL relative to total solve.'
                ),
                'recommendation': (
                    'Drill PLL algorithms for speed. Practice recognizing '
                    'the case during OLL execution to start PLL without '
                    'hesitation.'
                ),
                'command': pll_cmd,
            },
        )

    if not case_name:
        return diagnostics

    htm = step['moves_prettified'].metrics.htm
    optimal_htm = float(get_case('PLL', case_name).optimal_htm)
    target_htm = optimal_htm + 2  # AUF allowance
    htm_limit = (optimal_htm * 1.33) + 2

    if htm > htm_limit:
        extra_moves = htm - target_htm
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.EFFICIENCY_ALGORITHMS,
                'impact_seconds': extra_moves * solve.move_speed / SECOND,
                'location': 'PLL',
                'metric_name': 'htm',
                'actual_value': float(htm),
                'expected_value': (optimal_htm, htm_limit),
                'description': (
                    f'PLL used {htm} HTM, while the case optimal is '
                    f'{optimal_htm:.0f} HTM plus AUF. May be using '
                    'a sub-optimal algorithm or made execution errors.'
                ),
                'recommendation': (
                    'Review your PLL algorithm choice. '
                    'Learn faster PLL algorithms (J-perm, Y-perm variants). '
                    'Check for execution mistakes that added extra moves.'
                ),
                'command': pll_cmd,
            },
        )

    total_auf = (step['aufs'][0] or 0) + (step['aufs'][1] or 0)
    if total_auf > 4:
        estimated_impact = (total_auf - 4) * solve.move_speed / SECOND
        diagnostics.append(
            {
                'severity': DiagnosticSeverity.MEDIUM,
                'category': DiagnosticCategory.AUFS_EXCESSIVE,
                'impact_seconds': estimated_impact,
                'location': 'PLL',
                'metric_name': 'aufs',
                'actual_value': float(total_auf),
                'expected_value': (0.0, 4.0),
                'description': (
                    f'PLL used {total_auf} QTM in AUF '
                    f'(pre: {step["aufs"][0] or 0}, '
                    f'post: {step["aufs"][1] or 0}). '
                    'Excessive U-face adjustments.'
                ),
                'recommendation': (
                    'Learn PLL algorithm variants with different AUF. '
                    'Practice recognizing optimal angles to minimize total '
                    'AUF. Consider starting PLL from different angles to '
                    'reduce post-AUF.'
                ),
                'command': pll_cmd,
            },
        )

    return diagnostics


def generate_solve_diagnostics(solve: 'Solve') -> list[Diagnostic]:
    """
    Generate all diagnostics for a solve at both global and step levels.

    Args:
        solve: The solve to diagnose with reconstruction data.

    Returns:
        List of all diagnostics sorted by impact.

    """
    diagnostics: list[Diagnostic] = []

    if not solve.method_applied:
        return diagnostics

    diagnostics.extend(check_global_efficiency(solve))
    diagnostics.extend(check_global_execution(solve))
    diagnostics.extend(check_global_rotation(solve))
    diagnostics.extend(check_global_recognition(solve))

    for step in solve.method_applied.summary:
        step_name = step['name']
        if 'Cross' in step_name:
            diagnostics.extend(check_step_cross(solve, step))
        elif 'F2L' in step_name and step['type'] in {'step', 'virtual'}:
            diagnostics.extend(check_step_f2l(solve, step))
        elif step_name == 'OLL':
            diagnostics.extend(check_step_oll(solve, step))
        elif step_name == 'PLL':
            diagnostics.extend(check_step_pll(solve, step))

    diagnostics.sort(key=itemgetter('impact_seconds'), reverse=True)

    return diagnostics


def group_solve_diagnostics(
    diagnostics: list[Diagnostic],
) -> list[DiagnosticGroup]:
    """
    Aggregate diagnostics by location.

    Args:
        diagnostics: Diagnostics sorted by impact.

    Returns:
        List of groups sorted by aggregated impact.

    """
    groups: dict[str, DiagnosticGroup] = {}

    for diagnostic in diagnostics:
        location = diagnostic['location']
        group = groups.setdefault(
            location,
            {
                'location': location,
                'command': '',
                'impact_seconds': 0.0,
                'diagnostics': [],
            },
        )
        group['impact_seconds'] += diagnostic['impact_seconds']
        group['diagnostics'].append(diagnostic)
        if not group['command']:
            group['command'] = diagnostic['command']

    return sorted(
        groups.values(),
        key=itemgetter('impact_seconds'),
        reverse=True,
    )
