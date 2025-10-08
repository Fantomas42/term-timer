"""Type definitions for solve analysis and statistics."""
from typing import TypedDict

from term_timer.solve import Solve


class StepAnalysis(TypedDict):
    """Analysis of a single step from a solve."""
    case: str
    time: int
    execution: int
    recognition: int
    qtm: int
    tps: float
    etps: float


class SolveAnalysis(TypedDict):
    """Analysis result for a single solve."""
    steps: dict[str, StepAnalysis]
    score: float
    solve: Solve | None


class CaseStatsAccumulator(TypedDict):
    """Accumulator for case statistics during aggregation."""
    recognitions: list[int]
    executions: list[int]
    times: list[int]
    qtms: list[int]
    tpss: list[float]
    etpss: list[float]
    probability: float


class CaseStats(TypedDict):
    """Statistics for a single case (e.g., OLL case, PLL case)."""
    count: int
    frequency: float
    probability: float
    recognition: float
    execution: float
    time: float
    ao5: int
    ao12: int
    qtm: float
    tps: float
    etps: float


class MethodAnalysis(TypedDict):
    """Results of method analysis across multiple solves."""
    total: int
    mean: float
    resume: dict[str, dict[str, CaseStats]]
    stack: list[Solve | None]
