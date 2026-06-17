"""
Type definitions for solve analysis and statistics.

This module defines TypedDict classes used for aggregation and statistical
analysis of multiple solves. These types represent the external/aggregated
view of solve data.

Type System Architecture:
------------------------
The codebase uses a two-layer type system:

1. Internal Analysis Types:
   - StepInfo: Configuration for a solving step
   - StepSummary: Detailed analysis results for a single step
   - StepConfig: Step configuration with metadata
   These types are used during the solve analysis phase and contain detailed
   information about individual solve steps.

2. Aggregation Types:
   - StepAnalysis: Simplified step data for aggregation
   - SolveAnalysis: Complete solve analysis result
   - CaseStatsAccumulator: Accumulator for building statistics
   - CaseStats: Final statistics for a case across multiple solves
   - MethodAnalysis: Aggregated analysis across all solves
   These types are used for multi-solve aggregation and statistical reporting.

Data Flow:
----------
Analyser.summary (StepSummary list)
  → analyse_solve_worker() transforms to StepAnalysis
    → SolveAnalysis returned
      → aggregate() processes multiple SolveAnalysis
        → MethodAnalysis produced
"""
from dataclasses import dataclass
from dataclasses import field
from typing import TypedDict

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases.case import Case

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
    case: Case


class CaseStats(TypedDict):
    """Statistics for a single case (e.g., OLL case, PLL case)."""

    count: int
    frequency: float
    case: Case
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


@dataclass
class ListingFilters:
    """Filter parameters for solve listing."""

    with_comments: bool = False
    without_comments: bool = False
    connected: bool = False
    unconnected: bool = False
    dnf: bool = False
    plus_two: bool = False
    no_penalty: bool = False
    search_comment: str | None = None
    search_scramble: str | None = None
    min_time: float | None = None
    max_time: float | None = None


@dataclass
class TrainingCase:
    """Wrapper for Case with pre-computed best setup algorithms."""

    case: Case
    best_setups: list[Algorithm]
    solution: Algorithm = field(default_factory=Algorithm)
