"""
Comprehensive solve diagnostics and issue detection.

This module analyzes solve performance at both global and step-specific levels,
identifying issues across multiple categories with severity ratings and
estimated impact. Output is formatted for LLM processing to generate
personalized improvement recommendations.
"""
from enum import StrEnum
from operator import itemgetter
from typing import TYPE_CHECKING
from typing import Final
from typing import TypedDict

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.solve import Solve

TPS_LOW_THRESHOLD: Final = 1.5
TPS_MEDIUM_THRESHOLD: Final = 2.3
TPS_EXPECTED_MIN: Final = 2.5
TPS_EXPECTED_MAX: Final = 4.5

FLUENCY_LOW_THRESHOLD: Final = 55
FLUENCY_MEDIUM_THRESHOLD: Final = 60
FLUENCY_IMPACT_FACTOR: Final = 0.15


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


def check_global_efficiency(solve: 'Solve') -> list[Diagnostic]:
    """
    Detect efficiency issues at the global solve level.

    Checks for:
    - Excessive total movecount
    - Transition inefficiencies
    - Wasted moves (do-undo sequences)

    Args:
        solve: Solve instance with reconstruction data

    Returns:
        List of detected efficiency issues

    """
    issues: list[Diagnostic] = []

    all_missed_moves = solve.all_missed_moves
    transition_missed_moves = solve.transition_missed_moves
    tps = solve.move_speed * 1.05 / SECOND

    if all_missed_moves > 10:
        issues.append(
            {
                'severity': DiagnosticSeverity.CRITICAL,
                'category': DiagnosticCategory.EFFICIENCY_MOVECOUNT,
                'impact_seconds': all_missed_moves * tps,
                'location': 'global',
                'metric_name': 'all_missed_moves',
                'actual_value': float(all_missed_moves),
                'expected_value': 0.0,
                'description': (
                    f'Solve contains {all_missed_moves} missed QTM '
                    '(wasted moves from do-undo sequences or inefficient '
                    'execution). This significantly impacts solve time.'
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
    elif all_missed_moves > 5:
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.EFFICIENCY_MOVECOUNT,
                'impact_seconds': all_missed_moves * tps,
                'location': 'global',
                'metric_name': 'all_missed_moves',
                'actual_value': float(all_missed_moves),
                'expected_value': 0.0,
                'description': (
                    f'Solve contains {all_missed_moves} missed QTM. '
                    'Some inefficiency detected in move execution.'
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
                'impact_seconds': transition_missed_moves * tps,
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
                'expected_value': (2.5, 4.5),
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
            (1 / solve.tps - 1 / TPS_EXPECTED_MAX) * len(solve.solution)
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
                'expected_value': (2.5, 4.5),
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

    execution_pauses = solve.execution_pauses
    if execution_pauses > 8:
        estimated_impact = execution_pauses * solve.pause_threshold / SECOND
        issues.append(
            {
                'severity': DiagnosticSeverity.CRITICAL,
                'category': DiagnosticCategory.EXECUTION_PAUSES,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'execution_pauses',
                'actual_value': float(execution_pauses),
                'expected_value': 0.0,
                'description': (
                    f'Excessive pauses detected ({execution_pauses}). '
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
    elif execution_pauses > 4:
        estimated_impact = execution_pauses * solve.pause_threshold / SECOND
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.EXECUTION_PAUSES,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'execution_pauses',
                'actual_value': float(execution_pauses),
                'expected_value': 0.0,
                'description': (
                    f'Multiple pauses detected ({execution_pauses}). '
                    'Lookahead needs improvement.'
                ),
                'recommendation': (
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
    tps = solve.move_speed * 1.2 / SECOND

    if rotations > 8:
        estimated_impact = rotations * tps
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
        estimated_impact = rotations * tps
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
                'expected_value': (0.0, 4.0),
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
    solve_norms = solve.method_applied.norms['solve']
    rec_norm = solve_norms['recognition']
    rec_norm_max = float(rec_norm[1])  # type: ignore[index]

    rec_percent = solve.recognition_percent

    if rec_percent > rec_norm_max * 2:
        estimated_impact = (
            solve.recognition_time / SECOND
            * (1 - rec_norm_max / rec_percent)
        )
        issues.append(
            {
                'severity': DiagnosticSeverity.CRITICAL,
                'category': DiagnosticCategory.RECOGNITION_SLOW,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'recognition_percent',
                'actual_value': rec_percent,
                'expected_value': rec_norm,
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
    elif rec_percent > rec_norm_max * 1.25:
        estimated_impact = (
            solve.recognition_time / SECOND
            * (1 - rec_norm_max / rec_percent)
        )
        issues.append(
            {
                'severity': DiagnosticSeverity.HIGH,
                'category': DiagnosticCategory.RECOGNITION_SLOW,
                'impact_seconds': estimated_impact,
                'location': 'global',
                'metric_name': 'recognition_percent',
                'actual_value': rec_percent,
                'expected_value': rec_norm,
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

    diagnostics.sort(key=itemgetter('impact_seconds'), reverse=True)

    return diagnostics
