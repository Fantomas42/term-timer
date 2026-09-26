"""Type definitions for web server views and templates."""
from typing import TypedDict

from bottle import HTTPError
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases.case import Case
from cubing_algs.move import Move

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.doctor import Diagnostic
from term_timer.solve import Solve
from term_timer.stats import DailySummaryReporter
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


class TrendSeries(TypedDict):
    """A single configurable rolling-average curve of the trend graph."""

    token: str
    label: str
    size: int
    data: list[float | None]


class TrendData(TypedDict):
    """Trend data for solve time visualization."""

    indices: list[str]
    times: list[float]
    series: list[TrendSeries]


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
    mode: str


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
    daily: 'DailyBannerInfo'
    training: 'TrainingBannerInfo | None'


class SessionSeriesEntry(TypedDict):
    """A single configurable rolling average shown in the session table."""

    token: str
    label: str
    size: int
    value: int
    best: int


class SessionDetailContext(TypedDict):
    """Template context for session detail view."""

    cube: int
    session: str
    stats: SolveStatisticsReporter
    sessions: dict[str, int]
    session_series: list[SessionSeriesEntry]
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
    session_url: str
    solve: Solve
    solve_id: int
    solves: list[Solve]
    scatter: list[ScatterPoint]
    steps: list[StepMarker]
    highlights: list[str]
    diagnostics: list[Diagnostic]
    tps: list[TPSData]
    fluencies: list[FluencyData]
    recognitions: list[RecognitionData]
    reconstruction_text: str
    reconstruction_timing: list[tuple[int, int, Move]]
    reconstruction_index: dict[str, int]
    rank: int
    available_orientations: dict[str, str]
    available_methods: list[str]


class AlgorithmDetailContext(TypedDict):
    """Template context for algorithm detail view."""

    algorithm: Algorithm
    y_variations: list[AlgorithmVariation]
    symmetry_variations: list[AlgorithmVariation]
    inverse_variation: Algorithm
    orientation_moves: Algorithm
    orientation_faces: CubeOrientation
    available_orientations: dict[str, str]


class AcademyOverviewContext(TypedDict):
    """Template context for academy overview."""

    methods: dict[str, MethodInfo]
    orientation_faces: CubeOrientation
    orientation_moves: Algorithm
    available_orientations: dict[str, str]
    mode: str
    available_modes: list[tuple[str, list[str]]]
    cube_size: int
    available_cube_sizes: list[int]
    palette: str
    available_palettes: list[str]


class CaseTrainingTile(TypedDict):
    """Training of a case, tinting its tile on the academy step page."""

    state_label: str
    state_class: str
    overdue: bool
    attempts: int
    ao5: int
    trend: str
    speed: str
    memory: str
    retention: float | None


class TrainingStateRow(TypedDict):
    """Cases of a step sitting in one card state, or all of them."""

    label: str
    klass: str
    count: int
    overdue: int
    share: float
    offset: float
    best: int
    average: int
    worst: int


class StepTrainingSummary(TypedDict):
    """Recap of the training of a step by card state."""

    rows: list[TrainingStateRow]
    total: TrainingStateRow


class AcademyStepContext(TypedDict):
    """Template context for academy step view."""

    method: str
    step: str
    step_info: StepDescriptionInfo
    cube_size: int
    cases: dict[str, Case]
    group: str
    family: str
    orientation_moves: Algorithm
    orientation_faces: CubeOrientation
    available_orientations: dict[str, str]
    mode: str
    available_modes: list[tuple[str, list[str]]]
    available_cube_sizes: list[int]
    palette: str
    available_palettes: list[str]
    training: dict[str, CaseTrainingTile]
    training_summary: StepTrainingSummary | None
    training_unavailable: bool


class CubeRenderContext(TypedDict):
    """Template context for cube rendering view."""

    algorithm: str
    orientation_faces: CubeOrientation
    orientation_moves: Algorithm
    available_orientations: dict[str, str]
    mode: str
    available_modes: list[tuple[str, list[str]]]
    cube_size: int
    available_cube_sizes: list[int]
    palette: str
    available_palettes: list[str]


class CurvePoint(TypedDict):
    """A point of a chart drawn on a numeric horizontal axis."""

    x: float
    y: float


class AttemptsCurve(TypedDict):
    """Timings of a trained case in attempt order, with rolling averages."""

    labels: list[str]
    times: list[float]
    ao5: list[float | None]
    ao12: list[float | None]
    best: float
    peak: float | None


class ForgettingCurve(TypedDict):
    """Recall probability of a case from its last review onward."""

    points: list[CurvePoint]
    today: float
    due: float
    retention: float


class CaseTrainingPanel(TypedDict):
    """Personal training data of a case, shown on its academy page."""

    attempts: int
    best: int
    ao5: int
    ao12: int
    best_ao12: int
    trend: str
    trend_percent: int
    last_date: str
    state_label: str
    state_class: str
    stability: float | None
    difficulty: float | None
    last_review: str
    due: str
    due_relative: str
    overdue: bool
    curve: AttemptsCurve | None
    forgetting: ForgettingCurve | None


class AcademyCaseContext(TypedDict):
    """Template context for academy case view."""

    method: str
    step: str
    step_info: StepDescriptionInfo
    cube_size: int
    case: Case
    orientation_moves: Algorithm
    orientation_faces: CubeOrientation
    available_orientations: dict[str, str]
    mode: str
    available_modes: list[tuple[str, list[str]]]
    available_cube_sizes: list[int]
    palette: str
    available_palettes: list[str]
    training: CaseTrainingPanel | None
    training_unavailable: bool


class AlgorithmImpactGroup(TypedDict):
    """Algorithms sharing the same permutation impact on the cube."""

    group_id: str
    state: str
    algorithms: list[Algorithm]


class AcademyCaseAlgorithmsDebugContext(AcademyCaseContext):
    """Template context for academy case algorithms debug view."""

    impact_groups: list[AlgorithmImpactGroup]


class StyleguideToken(TypedDict):
    """A single design token parsed from the stylesheet :root block."""

    name: str
    value: str
    note: str


class StyleguideGroup(TypedDict):
    """A titled family of design tokens for the styleguide."""

    title: str
    tokens: list[StyleguideToken]


class StyleguideContext(TypedDict):
    """Template context for the styleguide view."""

    token_groups: list[StyleguideGroup]


class ScrambleHomeContext(TypedDict):
    """Template context for the scramble series home view."""

    cube_size: int
    seed: str
    available_cube_sizes: list[int]
    error: str


class ScrambleDetailContext(TypedDict):
    """Template context for a single scramble of a seeded series."""

    cube_size: int
    seed: str
    index: int
    max_index: int
    scramble: Algorithm
    htm: int


class DailySeries(TypedDict):
    """Values drawn per day on a daily graph, one label per point."""

    labels: list[str]
    best: list[float | None]
    first: list[float | None]
    attempts: list[int]


class DailyBannerInfo(TypedDict):
    """The daily of the day, as teased on the dashboard."""

    cube: int
    day: str
    number: int | None
    done: bool
    streak: int
    record: int
    best: int
    attempts: int
    scramble: Algorithm
    url: str
    series: DailySeries
    zone_edges: tuple[int, ...]


class DailyCalendarCell(TypedDict):
    """A day of the calendar, colored on its number of attempts."""

    day: str
    level: int
    attempts: int
    url: str


class DailyCalendarYear(TypedDict):
    """A year of the calendar, one column per week."""

    year: int
    months: list[str]
    cells: list[DailyCalendarCell]


class DailyDayRow(TypedDict):
    """A daily session summed up on a single row of the hub."""

    day: str
    weekday: str
    number: int | None
    attempts: int
    first: int
    best: int
    gain: int | None
    times: list[int]
    zones: list[int | None]


class DailyRecord(TypedDict):
    """A step of the staircase of the daily personal best."""

    day: str
    best: int
    gain: int


class DailyListContext(TypedDict):
    """Template context for the daily hub, the logbook of every day."""

    cube: int
    summary: DailySummaryReporter
    rows: list[DailyDayRow]
    calendar: list[DailyCalendarYear]
    series: DailySeries
    records: list[DailyRecord]
    zone_edges: tuple[int, ...]


class DailyStepSeries(TypedDict):
    """Time spent on one step, attempt by attempt."""

    label: str
    data: list[float | None]


class DailyDoctorFinding(TypedDict):
    """A doctor finding of the scramble, worded for display."""

    title: str
    severity: str
    impact: float
    frequency: float
    recommendation: str


class DailyDoctorGroup(TypedDict):
    """Doctor findings of the scramble gathered by location."""

    location: str
    command: str
    impact: float
    findings: list[DailyDoctorFinding]


class DailyDayContext(TypedDict):
    """Template context for the card of one daily session."""

    cube: int
    day: str
    number: int | None
    previous_day: str | None
    next_day: str | None
    scramble: Algorithm
    session_url: str
    solves: list[Solve]
    stats: Statistics
    zones: list[int | None]
    times: list[float | None]
    steps: list[DailyStepSeries]
    doctor_total: int
    doctor: list[DailyDoctorGroup]
    share: str
    zone_edges: tuple[int, ...]


class TrainingStepStatus(TypedDict):
    """Where the training of one step stands today."""

    step: str
    due: int
    new: int
    mastered: int
    total: int
    mastery: float
    academy: bool


class TrainingBannerInfo(TypedDict):
    """Training teaser of the dashboard, one status per trained step."""

    steps: list[TrainingStepStatus]
    due: int
    unavailable: list[str]


class ForecastSeries(TypedDict):
    """Reviews of one step over the forecast days."""

    label: str
    token: str
    data: list[int]


class TrainingForecast(TypedDict):
    """Reviews to come, overdue first then day by day, by step."""

    labels: list[str]
    series: list[ForecastSeries]
    later: int


class TrainingForecastContext(TypedDict):
    """Template context for the training forecast view."""

    banner: TrainingBannerInfo | None
    forecast: TrainingForecast


class ReviewCard(TypedDict):
    """A due case shown as a flashcard, its algorithm hidden."""

    code: str
    name: str
    main_algorithm: str
    arrows: str
    algorithm: str
    overdue: str
    state_label: str
    state_class: str


class TrainingReviewContext(TypedDict):
    """Template context for the flashcard review view."""

    method: str
    step: str
    cards: list[ReviewCard]
    orientation_faces: CubeOrientation
    mode: str
    cube_size: int
    palette: str
