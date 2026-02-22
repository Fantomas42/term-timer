"""Type definitions for web server views and templates."""
from typing import TypedDict

from bottle import HTTPError
from cubing_algs.algorithm import Algorithm
from cubing_algs.cases.case import Case
from cubing_algs.move import Move

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.stats import Statistics


class SessionInfo(TypedDict):
    """Information about a session with solves and statistics."""

    solves: list[Solve]
    stats: Statistics


class AlgorithmVariation(TypedDict):
    """Algorithm variation with label and transformed algorithm."""

    label: str
    algorithm: Algorithm


class TrendData(TypedDict):
    """Trend data for solve time visualization."""

    indices: list[str]
    times: list[float]
    ao5s: list[float | None]
    ao12s: list[float | None]
    ao100s: list[float | None]
    ao1000s: list[float | None]


class DistributionData(TypedDict):
    """Distribution data for histogram visualization."""

    labels: list[str]
    counts: list[int]


class ScatterPoint(TypedDict):
    """Scatter plot point with x and y coordinates."""

    x: int
    y: float


class StepMarker(TypedDict):
    """Step marker for visualization with position and label."""

    x: int
    y: float
    label: str


class TPSData(TypedDict):
    """TPS (Turns Per Second) data for a step."""

    tps: float
    etps: float
    label: str


class FluencyData(TypedDict):
    """Fluency score data for a step."""

    fluency: float
    label: str


class RecognitionData(TypedDict):
    """Recognition and execution time data for a step."""

    recognition: float
    execution: float
    label: str


class StepDescriptionInfo(TypedDict):
    """Step description information for academy."""

    description: str


class MethodInfo(TypedDict):
    """Method information for academy overview."""

    cube_size: int
    description: str
    steps: dict[str, StepDescriptionInfo]


class Error404Context(TypedDict):
    """Template context for 404 error page."""

    error: HTTPError
    message: str


class Error500Context(TypedDict):
    """Template context for 500 error page."""

    error: HTTPError
    message: str
    exception: Exception
    traceback: str | None


class SessionListContext(TypedDict):
    """Template context for session list view."""

    sessions: dict[int, dict[str, SessionInfo]]


class SessionDetailContext(TypedDict):
    """Template context for session detail view."""

    cube: int
    session: str
    stats: SolveStatisticsReporter
    sessions: dict[str, int]
    trend: TrendData
    distribution: DistributionData
    punchcard: dict[str, dict[str, int]]
    step: str
    case_uid: str
    method_aggregation: SolvesMethodAggregator


class SolveDetailContext(TypedDict):
    """Template context for solve detail view."""

    cube: int
    session: str
    solve: Solve
    solve_id: int
    solves: list[Solve]
    scatter: list[ScatterPoint]
    steps: list[StepMarker]
    cheers: list[str]
    tps: list[TPSData]
    fluencies: list[FluencyData]
    recognitions: list[RecognitionData]
    reconstruction_text: str
    reconstruction_timing: list[tuple[int, int, Move]]
    reconstruction_index: dict[str, int]
    rank: int
    available_orientations: dict[str, Algorithm]
    available_methods: list[str]


class AlgorithmDetailContext(TypedDict):
    """Template context for algorithm detail view."""

    algorithm: Algorithm
    y_variations: list[AlgorithmVariation]
    symmetry_variations: list[AlgorithmVariation]
    inverse_variation: Algorithm
    orientation_moves: Algorithm
    orientation_faces: str
    available_orientations: dict[str, Algorithm]


class AcademyOverviewContext(TypedDict):
    """Template context for academy overview."""

    methods: dict[str, MethodInfo]


class AcademyStepContext(TypedDict):
    """Template context for academy step view."""

    method: str
    step: str
    step_info: StepDescriptionInfo
    cube_size: int
    cases: dict[str, Case]
    group: str
    family: str


class AcademyCaseContext(TypedDict):
    """Template context for academy case view."""

    method: str
    step: str
    step_info: StepDescriptionInfo
    cube_size: int
    case: Case
    orientation_moves: Algorithm
    orientation_faces: str
    available_orientations: dict[str, Algorithm]
