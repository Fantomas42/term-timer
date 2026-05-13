"""
Comprehensive solve diagnostics and issue detection.

This module analyzes solve performance at both global and step-specific levels,
identifying issues across multiple categories with severity ratings and
estimated impact. Output is formatted for LLM processing to generate
personalized improvement recommendations.
"""
from enum import StrEnum
from typing import TYPE_CHECKING
from typing import TypedDict

if TYPE_CHECKING:
    from term_timer.solve import Solve


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
    RECOGNITION_BALANCE = 'recognition_balance'
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


def generate_solve_diagnostics(solve: 'Solve') -> list[Diagnostic]:  # noqa: ARG001
    """
    Generate diagnostics for a solve.

    Args:
        solve: The solve to diagnose.

    Returns:
        List of diagnostic strings.

    """
    return []
