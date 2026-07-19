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

from term_timer.constants import FLUENCY_LOW_THRESHOLD
from term_timer.constants import FLUENCY_MEDIUM_THRESHOLD
from term_timer.constants import FLUENCY_STEP_LOW_THRESHOLD
from term_timer.constants import FLUENCY_STEP_MEDIUM_THRESHOLD
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
                    f'{step_missed_moves} QTM wasted within steps on '
                    'do-undo sequences and corrections.'
                ),
                'recommendation': (
                    'Practice slow solves with deliberate, clean turning - '
                    'no correction is acceptable. Drill the algorithms that '
                    'produce fixes until they run clean at speed.'
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
                    f'{step_missed_moves} QTM wasted within steps on '
                    'do-undo sequences and corrections.'
                ),
                'recommendation': (
                    'Focus on clean algorithm execution without '
                    'corrections, even at lower speed.'
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
                    f'{transition_missed_moves} QTM wasted in transitions '
                    'between steps.'
                ),
                'recommendation': (
                    'Fully recognize the next case before turning: a wasted '
                    'correction costs more than a slightly longer look.'
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
                    f'Low TPS ({solve.tps:.2f}), measured over the full '
                    'solve, pauses included.'
                ),
                'recommendation': (
                    'Drill fingertricks for all basic moves and run '
                    'algorithms at increasing speed. If pause diagnostics '
                    'also fired, fix those first - dead time lowers TPS as '
                    'much as slow turning.'
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
                    f'Moderate TPS ({solve.tps:.2f}), measured over the '
                    'full solve, pauses included.'
                ),
                'recommendation': (
                    'Work on fingertrick efficiency to keep turning '
                    'continuous. If pause diagnostics also fired, fix '
                    'those first.'
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
                    f'({solve.execution_pauses} pauses).'
                ),
                'recommendation': (
                    'Practice slow solves at 50-70% speed, reading the next '
                    'case while the current one runs - never stop turning. '
                    'Speed returns on its own once the pauses are gone.'
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
                    f'({solve.execution_pauses} pauses).'
                ),
                'recommendation': (
                    'Look ahead in every step: identify the next case '
                    'before finishing the current one. Slow solves with '
                    'continuous turning train this best.'
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
                    f'Very low fluency ({fluency}/100): move timing is '
                    'highly uneven.'
                ),
                'recommendation': (
                    'Drill your algorithms until they run at an even '
                    'rhythm, without regrips. Favor smooth, consistent '
                    'turning over burst speed.'
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
                    f'Moderate fluency ({fluency}/100): some unevenness in '
                    'turning rhythm.'
                ),
                'recommendation': (
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
                    f'{rotations} cube rotations during the solve.'
                ),
                'recommendation': (
                    'Learn rotationless alternatives (back-slot insertions, '
                    'wide moves) for the F2L cases that make you rotate.'
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
                    f'{rotations} cube rotations during the solve.'
                ),
                'recommendation': (
                    'Identify which F2L cases make you rotate and learn '
                    'rotation-free alternatives.'
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
                    f'{aufs} QTM spent in AUF adjustments around algorithms.'
                ),
                'recommendation': (
                    'Learn OLL/PLL variants that minimize AUF from your '
                    'usual angles.'
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
                    f'Recognition takes {rec_percent:.1f}% of solve time.'
                ),
                'recommendation': (
                    'Drill case recognition with the trainer until '
                    'identification is instant. Read the next case during '
                    'the current step - pair during cross, PLL during OLL - '
                    'to shrink every transition.'
                ),
                'command': 'term-timer train -s ll',
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
                    f'Recognition takes {rec_percent:.1f}% of solve time.'
                ),
                'recommendation': (
                    'Drill recognition for the cases that are slow to '
                    'identify. Reading the next case while executing the '
                    'current step removes this dead time.'
                ),
                'command': 'term-timer train -s ll',
            },
        )

    return issues


def check_step_fluency(
    step_name: str,
    fluency: int,
    execution: int,
    command: str,
) -> list[Diagnostic]:
    """
    Detect uneven turning rhythm within a single step.

    Step fluency is measured on execution only, without the recognition
    phase that precedes the step, so it is compared to thresholds much
    higher than the whole-solve ones.

    Args:
        step_name: Where the issue occurs, used as diagnostic location
        fluency: Fluency score of the step (0-100)
        execution: Execution duration of the step in nanoseconds
        command: Command to practice this step

    Returns:
        List of detected fluency diagnostics

    """
    diagnostics: list[Diagnostic] = []

    # A step of two moves or less has no meaningful rhythm.
    if fluency <= 0 or fluency >= FLUENCY_STEP_MEDIUM_THRESHOLD:
        return diagnostics

    severity = (
        DiagnosticSeverity.HIGH
        if fluency < FLUENCY_STEP_LOW_THRESHOLD
        else DiagnosticSeverity.MEDIUM
    )

    diagnostics.append(
        {
            'severity': severity,
            'category': DiagnosticCategory.EXECUTION_FLUENCY,
            'impact_seconds': (
                execution / SECOND
                * (FLUENCY_STEP_MEDIUM_THRESHOLD - fluency)
                / FLUENCY_STEP_MEDIUM_THRESHOLD
                * FLUENCY_IMPACT_FACTOR
            ),
            'location': step_name,
            'metric_name': 'fluency',
            'actual_value': float(fluency),
            'expected_value': (float(FLUENCY_STEP_MEDIUM_THRESHOLD), 100.0),
            'description': (
                f'{step_name} fluency is {fluency}/100 '
                f'(norm {FLUENCY_STEP_MEDIUM_THRESHOLD}): turning rhythm '
                'is uneven within the step.'
            ),
            'recommendation': (
                'Drill this step at a steady rhythm until the fingertricks '
                'chain without regrips. Raise speed only once the timing '
                'is even.'
            ),
            'command': command,
        },
    )

    return diagnostics


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
                    f'{step_name} used {htm} HTM '
                    f'({int(move_norm + 2)} or fewer expected).'
                ),
                'recommendation': (
                    'Plan the complete cross during inspection and commit '
                    'to it. Practice finding shorter solutions with the '
                    'cross trainer.'
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
                    f'{step_name} used {htm} HTM '
                    f'({int(move_norm + 2)} or fewer expected).'
                ),
                'recommendation': (
                    'Use full inspection time to find a shorter cross '
                    'before executing.'
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
                    f'{step_name} took {step["total_percent"]:.1f}% of '
                    f'solve time (norm {percent_norm:g}%).'
                ),
                'recommendation': (
                    'Bring cross execution to full speed, and plan the '
                    'first F2L pair during cross to erase the transition.'
                ),
                'command': 'term-timer train -s cross',
            },
        )

    diagnostics.extend(
        check_step_fluency(
            step_name,
            solve.compute_fluency(step['moves']),
            step['execution'],
            'term-timer train -s cross',
        ),
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
                    f'{step_name} took {step["total_percent"]:.1f}% of '
                    f'solve time (norm {percent_norm:g}%).'
                ),
                'recommendation': (
                    'Drill your slowest F2L cases for efficient solutions. '
                    'If lookahead diagnostics also fired, pair-finding time '
                    'is the first lever.'
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
                    f'{step["step_recognition_percent"]:.1f}% of step time - '
                    'mostly spent finding the next pair.'
                ),
                'recommendation': (
                    'Track the next pair while inserting the current one, '
                    'at reduced speed if needed so turning never stops. '
                    'This single habit builds lookahead.'
                ),
                'command': 'term-timer train -s f2l',
            },
        )

    # The aggregated F2L step spans the transitions between pairs, whose
    # lookahead pauses would dominate its rhythm: fluency is averaged over
    # the individual pairs instead. Methods without pair substeps expose
    # no usable measure and are left alone.
    pairs = [
        pair_fluency
        for pair in solve.method_applied.summary
        if pair['type'] == 'substep' and 'F2L' in pair['name']
        if (pair_fluency := solve.compute_fluency(pair['moves'])) > 0
    ]
    if pairs:
        diagnostics.extend(
            check_step_fluency(
                step_name,
                round(sum(pairs) / len(pairs)),
                step['execution'],
                'term-timer train -s f2l',
            ),
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
                    f'{step["step_recognition_percent"]:.1f}% of step time.'
                ),
                'recommendation': (
                    'Drill OLL recognition with the trainer, reading the '
                    'overall pattern (dot, line, shape) at a glance. Start '
                    'identifying the case during the last F2L pair.'
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
                    f'OLL took {step["total_percent"]:.1f}% of solve time '
                    f'(norm {percent_norm:g}%).'
                ),
                'recommendation': (
                    'Drill this case for execution speed with the trainer.'
                ),
                'command': oll_cmd,
            },
        )

    diagnostics.extend(
        check_step_fluency(
            'OLL',
            solve.compute_fluency(step['moves']),
            step['execution'],
            oll_cmd,
        ),
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
                    f'OLL used {htm} HTM for a case solvable in '
                    f'{optimal_htm:.0f} plus AUF.'
                ),
                'recommendation': (
                    'Compare your algorithm for this case against shorter '
                    'ones, and check the reconstruction for execution '
                    'errors.'
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
                    f'{step["step_recognition_percent"]:.1f}% of step time.'
                ),
                'recommendation': (
                    'Practice 2-side recognition (headlights, blocks, bars) '
                    'with the trainer. Read the PLL during OLL execution to '
                    'start it without hesitation.'
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
                    f'PLL took {step["total_percent"]:.1f}% of solve time '
                    f'(norm {percent_norm:g}%).'
                ),
                'recommendation': (
                    'Drill this case for execution speed with the trainer.'
                ),
                'command': pll_cmd,
            },
        )

    diagnostics.extend(
        check_step_fluency(
            'PLL',
            solve.compute_fluency(step['moves']),
            step['execution'],
            pll_cmd,
        ),
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
                    f'PLL used {htm} HTM for a case solvable in '
                    f'{optimal_htm:.0f} plus AUF.'
                ),
                'recommendation': (
                    'Compare your algorithm for this case against shorter '
                    'variants, and check the reconstruction for added '
                    'moves.'
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
                    f'post: {step["aufs"][1] or 0}).'
                ),
                'recommendation': (
                    'Learn this case from other angles with alternate '
                    'variants - a good variant choice removes most pre- '
                    'and post-AUF.'
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
