"""Type definitions for web server views and templates."""
from datetime import date
from datetime import datetime
from typing import NotRequired
from typing import TypedDict

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases.case import Case
from cubing_algs.ergonomics import ErgonomicsData
from cubing_algs.impacts import ImpactData
from cubing_algs.memory import MemoryData
from cubing_algs.metrics import MetricsData
from cubing_algs.structure import StructureData

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.doctor import Diagnostic
from term_timer.server.filters import AlgToken
from term_timer.server.share import ShareCode
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

    message: str
    path: str
    scramble: str


class TracebackFrame(TypedDict):
    """One frame of a traceback, as the 500 page shows it."""

    file: str
    line: int
    function: str
    code: str
    own: bool


class Error500Context(TypedDict):
    """Template context for 500 error page."""

    message: str
    exception: Exception
    exception_name: str
    traceback: str | None
    frames: list[TracebackFrame]
    path: str


class ActivityCell(TypedDict):
    """
    A day of the activity calendar, heated by its number of solves.

    A day of the daily links to its session.
    """

    day: date
    count: int
    level: int
    url: NotRequired[str]


class ActivityMonth(TypedDict):
    """A month label of the activity calendar, on its first week."""

    week: int
    label: str


class ActivityCalendarData(TypedDict):
    """Weeks of the activity calendar and the totals of the shown days."""

    weeks: list[list[ActivityCell]]
    months: list[ActivityMonth]
    total: int
    active: int
    recent: int


class FormChart(TypedDict):
    """The last solves and their Ao12, in seconds, and the best Ao12."""

    points: list[float | None]
    ao12: list[float | None]
    best: float


class DashboardForm(TypedDict):
    """Current and best averages over every session and the daily."""

    ao5: int
    ao12: int
    ao100: int
    best_ao5: int
    best_ao12: int
    best_ao100: int
    best: int
    total: int
    month: int
    chart: FormChart


class SessionRow(TypedDict):
    """A session in the table of the dashboard."""

    label: str
    url: str
    count: int
    best: int
    ao12: int
    best_ao12: int
    last: datetime
    spark: list[float | None]
    total: bool


class SessionTable(TypedDict):
    """The sessions of a puzzle, the whole of them last."""

    cube: int
    name: str
    count: int
    rows: list[SessionRow]


class RecentSolve(TypedDict):
    """One of the last solves, linked to its page."""

    label: str
    detail: str
    url: str
    time: int
    moment: datetime
    grade: str
    fluency: int


class CareerKind(TypedDict):
    """A series of the career chart and the colour role drawing it."""

    key: str
    label: str
    role: str


class CareerPoint(TypedDict):
    """A solve of the career chart: its day, its time, its series."""

    x: int
    y: float
    k: str


class CareerLinePoint(TypedDict):
    """A point of the rolling average of the career chart."""

    x: int
    y: float


class CareerChart(TypedDict):
    """Every solve on the calendar, with the rolling Ao100."""

    start: str
    days: int
    points: list[CareerPoint]
    line: list[CareerLinePoint]
    floor: int
    ceiling: float
    kinds: list[CareerKind]
    labels: dict[str, str]


class ForecastDay(TypedDict):
    """The reviews of every step on one day of the forecast."""

    label: str
    short: str
    total: int


class ForecastSummary(TypedDict):
    """The forecast of the dashboard, overdue first, and its peak."""

    days: list[ForecastDay]
    peak: int


class DashboardContext(TypedDict):
    """What the dashboard shows beyond the sessions and the banners."""

    today: date
    form: DashboardForm | None
    session_tables: list[SessionTable]
    recent: list[RecentSolve]
    career: CareerChart | None
    activity: ActivityCalendarData
    forecast: ForecastSummary | None
    daily_command: str
    training_command: str


class SessionListContext(DashboardContext):
    """Template context for session list view."""

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
    punchcard: dict[str, dict[str, int]]
    step: str
    case_uid: str
    method_aggregation: SolvesMethodAggregator
    today: date
    label: str
    breadcrumb: list['BreadcrumbItem']
    board: list['BoardRow']
    switch: list['SessionSwitchItem']
    activity: ActivityCalendarData
    trend_chart: 'TrendChart'
    distribution_chart: 'DistributionChart'
    solve_rows: list[Solve]
    case_tables: list['CaseTable']
    solve_tabs: list[tuple[str, str]]
    available_methods: list[str]
    method_name: str


class BreadcrumbItem(TypedDict):
    """One level of the breadcrumb, the current page without a link."""

    label: str
    href: str


class BoardRow(TypedDict):
    """A line of the averages board: current value against the best."""

    label: str
    value: int
    best: int


class SessionSwitchItem(TypedDict):
    """A session of the same puzzle, reachable from the session page."""

    label: str
    url: str
    count: int
    current: bool


class TrendLine(TypedDict):
    """A rolling average of the progress chart, in seconds."""

    label: str
    data: list[float | None]


class TrendChart(TypedDict):
    """The progress chart: every time, its averages, its scale."""

    indices: list[str]
    times: list[float | None]
    series: list[TrendLine]
    ceiling: float
    legend: list[tuple[str, str]]


class DistributionChart(TypedDict):
    """Solves per time bucket, the most frequent bucket named."""

    labels: list[str]
    counts: list[int]
    mode: str


class CaseRow(TypedDict):
    """A case met in the session, with its timings and its frequency."""

    case: Case
    name: str
    setup: str
    count: int
    frequency: float
    probability: float
    seen: float
    expected: float
    overrepresented: bool
    recognition: float
    execution: float
    time: float
    recognition_share: float
    qtm: float
    tps: float
    etps: float
    filter_url: str


class CaseTable(TypedDict):
    """The cases of a step, the most met first."""

    step: str
    rows: list[CaseRow]


class StepMetric(TypedDict):
    """One metric of a reconstruction step, toned against its norm."""

    label: str
    value: str
    tone: str
    strong: bool


class StepPanel(TypedDict):
    """What a reconstruction tab shows of a step: moves and metrics."""

    tokens: list[AlgToken]
    metrics: list[StepMetric]


class StepCase(TypedDict):
    """The case recognised at a step, rendered as a thumbnail."""

    code: str
    label: str
    href: str
    algorithm: str
    mode: str
    arrows: str


class SolveStepRow(TypedDict):
    """One step of the reconstruction, with a panel per tab."""

    name: str
    slug: str
    type: str
    share: float
    case: StepCase | None
    skip: bool
    panels: dict[str, StepPanel]


class PlayerData(TypedDict):
    """
    What the player module plays: the moves and their setup.

    The setup is applied before the moves, or after them with the end
    anchor, for moves ending on a solved cube. Timings, when measured,
    give the start and end of every move; index, the move starting each
    step.
    """

    alg: str
    setup: str
    anchor: str
    puzzle: str
    timing: list[tuple[int, int]]
    index: dict[str, int]


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
    rank: int | None
    ranked: int
    available_orientations: dict[str, str]
    available_methods: list[str]
    breadcrumb: list[BreadcrumbItem]
    previous_url: str
    next_url: str
    step_rows: list[SolveStepRow]
    replay: PlayerData


class AlgorithmCase(TypedDict):
    """The CFOP last layer case an algorithm solves."""

    step: str
    code: str
    label: str
    aliases: list[str]
    href: str
    mode: str
    arrows: str
    yours: bool
    main: bool


class AlgorithmMoveStep(TypedDict):
    """
    One move of an algorithm as the hands execute it.

    load is the discomfort of the move, 0 for the most comfortable, 1
    for the least; transition names the kind of hand change from the
    previous move, and part the member of the structure (A, B, A', B')
    the move belongs to.
    """

    move: str
    hand: str
    finger: str
    time: float
    load: float
    transition: str
    regrip: bool
    part: str
    structure: int


class AlgorithmStructureRow(TypedDict):
    """A conjugate or commutator detected in an algorithm."""

    number: int
    kind: str
    classification: str
    notation: str
    setup: str
    action: str
    first: int
    last: int
    moves: int
    pure: bool
    cancels: bool
    score: float


class AlgorithmVariationRow(TypedDict):
    """A variation of an algorithm, its scores against the original."""

    label: str
    text: str
    tokens: list[AlgToken]
    htm: int
    htm_delta: int
    ergonomics: float
    ergonomics_delta: float
    memory: float
    memory_delta: float
    case: str
    href: str
    original: bool
    best: bool


class CubieCycle(TypedDict):
    """Pieces an algorithm cycles, by their home position."""

    kind: str
    pieces: list[str]


class AlgorithmPatternGroup(TypedDict):
    """The cube patterns an algorithm leaves, for one category."""

    label: str
    patterns: list[str]


class AlgorithmChart(TypedDict):
    """
    Data of the generic algorithm charts: one value per label, each
    drawn with its colour role, on a scale capped at max when given.
    """

    labels: list[str]
    values: list[float]
    roles: list[str]
    max: NotRequired[float]


class AlgorithmCharts(TypedDict):
    """The charts of the algorithm page."""

    metrics: AlgorithmChart
    move_types: AlgorithmChart
    ergonomics: AlgorithmChart
    hands: AlgorithmChart
    fingers: AlgorithmChart
    memory: AlgorithmChart
    faces: AlgorithmChart
    pieces: AlgorithmChart


class AlgorithmDetailContext(TypedDict):
    """Template context for algorithm detail view."""

    algorithm: Algorithm
    orientation_faces: CubeOrientation
    available_orientations: dict[str, str]
    text: str
    tokens: list[AlgToken]
    cube_size: int
    solved_case: AlgorithmCase | None
    breadcrumb: list[BreadcrumbItem]
    metrics: MetricsData
    ergonomics: ErgonomicsData
    memory: MemoryData
    structure: StructureData
    impacts: ImpactData
    effect_mask: str
    cycles: int
    tones: dict[str, str]
    track: list[AlgorithmMoveStep]
    structures: list[AlgorithmStructureRow]
    cubie_cycles: list[CubieCycle]
    twisted: list[str]
    patterns: list[AlgorithmPatternGroup]
    variations: list[AlgorithmVariationRow]
    charts: AlgorithmCharts
    player: PlayerData


class StepCounts(TypedDict):
    """How far the training of a set of cases went."""

    cases: int
    trained: int
    mastered: int
    due: int


class AcademyStepCard(TypedDict):
    """A step of a method on the academy overview, with its training."""

    step: str
    title: str
    description: str
    href: str
    mode: str
    cases: int
    image: str
    arrows: str
    counts: 'StepCounts | None'
    states: list['TrainingStateRow']
    review_url: str


class AcademyMethodCard(TypedDict):
    """A method of the academy overview and its steps."""

    name: str
    slug: str
    cube_size: int
    title: str
    description: str
    steps: list[AcademyStepCard]


class AcademyOverviewContext(TypedDict):
    """Template context for academy overview."""

    methods: dict[str, MethodInfo]
    method_cards: list[AcademyMethodCard]
    orientation_faces: CubeOrientation
    available_orientations: dict[str, str]
    mode: str
    cube_size: int
    palette: str


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


class CaseTile(TypedDict):
    """
    A case of a grid: its image, the algorithm to execute, its training.

    The algorithm is the solution saved in the training file when there
    is one (custom), the main algorithm of the case otherwise.
    """

    code: str
    label: str
    href: str
    family: str
    image: str
    arrows: str
    mode: str
    cube_size: int
    tokens: list[AlgToken]
    custom: bool
    probability: str
    algorithms: int
    note: str
    training: CaseTrainingTile | None


class CaseFamily(TypedDict):
    """The cases of one family of a step, as a filter and a grid."""

    name: str
    slug: str
    href: str
    active: bool
    tiles: list[CaseTile]


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
    orientation_faces: CubeOrientation
    available_orientations: dict[str, str]
    mode: str
    palette: str
    training_summary: StepTrainingSummary | None
    training_unavailable: bool
    breadcrumb: list[BreadcrumbItem]
    families: list[CaseFamily]
    counts: StepCounts | None
    all_url: str
    review_url: str
    command: str


class CubeRenderContext(TypedDict):
    """Template context for cube rendering view."""

    algorithm: str
    orientation_faces: CubeOrientation
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


class AlgorithmRow(TypedDict):
    """An algorithm of a case, with its scores, in a sortable table."""

    rank: int
    text: str
    tokens: list[AlgToken]
    htm: int
    ergonomics: float
    memory: float
    href: str


class AlgorithmSource(TypedDict):
    """The algorithms of a case from one source of the database."""

    slug: str
    label: str
    note: str
    image: str
    rows: list[AlgorithmRow]


class RecognitionAngle(TypedDict):
    """One angle to recognise a case from, with its explanation."""

    feature: str
    feature_notes: list[str]
    description: list[str]
    observation: str
    notes: str
    rotation: str


class CaseAlgorithmFocus(TypedDict):
    """The algorithm to learn for a case and its scores."""

    text: str
    tokens: list[AlgToken]
    custom: bool
    htm: int
    stm: int
    ergonomics: float
    memory: float
    href: str


class AcademyCaseContext(TypedDict):
    """Template context for academy case view."""

    method: str
    step: str
    cube_size: int
    case: Case
    orientation_faces: CubeOrientation
    available_orientations: dict[str, str]
    mode: str
    palette: str
    training: CaseTrainingPanel | None
    training_unavailable: bool
    breadcrumb: list[BreadcrumbItem]
    previous_url: str
    next_url: str
    focus: CaseAlgorithmFocus
    sources: list[AlgorithmSource]
    source_tabs: list[tuple[str, str]]
    step_url: str
    recognition: list[RecognitionAngle]
    recognition_setup: str
    description: list[str]
    player: 'PlayerData'
    command: str


class AlgorithmImpactGroup(TypedDict):
    """Algorithms sharing the same permutation impact on the cube."""

    group_id: str
    state: str
    algorithms: list[Algorithm]


class AcademyCaseAlgorithmsDebugContext(AcademyCaseContext):
    """Template context for academy case algorithms debug view."""

    impact_groups: list[AlgorithmImpactGroup]


class StyleguideToken(TypedDict):
    """A single value of the theme, as the styleguide shows it."""

    name: str
    value: str
    note: str


class StyleguideGroup(TypedDict):
    """A titled family of theme values for the styleguide."""

    title: str
    tokens: list[StyleguideToken]


class ContrastCheckData(TypedDict):
    """A measured contrast pair of the theme."""

    text: str
    background: str
    level: str
    ratio: float
    minimum: float
    passed: bool


class ChartPoint(TypedDict):
    """One point of a chart series."""

    x: int
    y: float


class ChartMarker(TypedDict):
    """A labelled vertical marker on a chart."""

    x: int
    label: str


class MovesTimingChart(TypedDict):
    """Data of the moves-timing chart: cumulative time per move."""

    points: list[ChartPoint]
    steps: list[ChartMarker]


class StepTps(TypedDict):
    """TPS and eTPS of one step."""

    label: str
    tps: float
    etps: float


class StepsTpsChart(TypedDict):
    """Data of the steps-tps chart."""

    steps: list[StepTps]


class StyleguideAlgorithm(TypedDict):
    """An algorithm fixture of the component catalogue."""

    title: str
    tokens: list[AlgToken]
    size: str
    copy_label: str
    key: str
    htm: int | None


class StyleguideSolveRow(TypedDict):
    """A row of the table fixture of the component catalogue."""

    number: int
    time: str
    seconds: float
    tps: float
    grade: str


class DesignStyleguideContext(TypedDict):
    """Template context for the design system styleguide."""

    token_groups: list[StyleguideGroup]
    contrast_checks: list[ContrastCheckData]
    algorithms: list[StyleguideAlgorithm]
    moves_timing: MovesTimingChart
    steps_tps: StepsTpsChart
    steps_recognition: list[RecognitionData]
    steps_fluency: list[FluencyData]
    breadcrumb: list[BreadcrumbItem]
    solves: list[StyleguideSolveRow]
    activity: ActivityCalendarData
    times: list[float | None]
    form_chart: FormChart
    trend_chart: 'TrendChart'
    distribution_chart: 'DistributionChart'
    career_chart: CareerChart
    case_tiles: list[CaseTile]
    state_rows: list[TrainingStateRow]
    player_data: PlayerData
    attempts_chart: AttemptsCurve | None
    forgetting_chart: ForgettingCurve
    forecast_chart: 'ForecastChart'
    move_track_steps: list[AlgorithmMoveStep]
    algorithm_charts: AlgorithmCharts
    share_code: ShareCode


class NavigationItem(TypedDict):
    """One entry of the main navigation, as rendered."""

    label: str
    icon: str
    url: str
    active: bool


class ScrambleHomeContext(TypedDict):
    """Template context for the scramble series home view."""

    cube_size: int
    seed: str
    available_cube_sizes: list[int]
    error: str
    alphabet: str
    seed_length: int
    max_index: int


class ScrambleDetailContext(TypedDict):
    """Template context for a single scramble of a seeded series."""

    cube_size: int
    seed: str
    index: int
    max_index: int
    scramble: Algorithm
    htm: int
    breadcrumb: list[BreadcrumbItem]
    previous_url: str
    next_url: str
    series_urls: list[str]
    share: ShareCode
    cli_command: str


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


class DailyToday(TypedDict):
    """The daily of the day on the logbook: to play, or played."""

    day: date
    number: int
    scramble: Algorithm
    url: str


class DailyTimesChart(TypedDict):
    """Best and first attempt of each played day, in seconds."""

    labels: list[str]
    best: list[float | None]
    first: list[float | None]
    edges: tuple[int, ...]
    floor: int
    ceiling: int
    clipped: int


class DailyListContext(TypedDict):
    """Template context for the daily hub, the logbook of every day."""

    cube: int
    summary: DailySummaryReporter
    rows: list[DailyDayRow]
    records: list[DailyRecord]
    zone_edges: tuple[int, ...]
    breadcrumb: list[BreadcrumbItem]
    today: DailyToday
    activity: ActivityCalendarData | None
    times_chart: DailyTimesChart | None
    record_days: list[str]


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


class DailyAttemptsChart(TypedDict):
    """The attempts of a day in order, in seconds, with their zones."""

    labels: list[str]
    times: list[float | None]
    zones: list[int | None]
    best: int | None
    edges: tuple[int, ...]
    ceiling: int


class DailyStepsChart(TypedDict):
    """The time of each step, attempt by attempt."""

    labels: list[str]
    steps: list[DailyStepSeries]


class DailyDayContext(TypedDict):
    """Template context for the card of one daily session."""

    cube: int
    day: str
    number: int | None
    previous_day: str | None
    next_day: str | None
    scramble: Algorithm
    solves: list[Solve]
    stats: Statistics
    zones: list[int | None]
    times: list[float | None]
    steps: list[DailyStepSeries]
    doctor_total: int
    doctor: list[DailyDoctorGroup]
    share: str
    zone_edges: tuple[int, ...]
    breadcrumb: list[BreadcrumbItem]
    previous_url: str
    next_url: str
    record: bool
    attempt_urls: list[str]
    attempts_chart: DailyAttemptsChart
    steps_chart: DailyStepsChart
    steps_legend: list[tuple[str, str]]


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


class TrainingStepRow(TypedDict):
    """A trained step on the training page: its status and its states."""

    status: TrainingStepStatus
    states: list[TrainingStateRow]
    command: str
    academy_url: str
    review_url: str


class ForecastChartSeries(TypedDict):
    """Reviews of one step, with the colour role of its chart series."""

    label: str
    role: str
    data: list[int]


class ForecastChart(TypedDict):
    """Data of the training-forecast chart."""

    labels: list[str]
    series: list[ForecastChartSeries]


class TrainingForecastContext(TypedDict):
    """Template context for the training forecast view."""

    banner: TrainingBannerInfo | None
    forecast: TrainingForecast
    forecast_chart: ForecastChart
    forecast_legend: list[tuple[int, str]]
    steps: list[TrainingStepRow]
    weak: list[CaseTile]
    orientation_faces: CubeOrientation
    palette: str


class ReviewPool(TypedDict):
    """A choice of cases for the review sheet."""

    slug: str
    label: str
    href: str
    count: int
    active: bool


class TrainingReviewContext(TypedDict):
    """Template context for the review sheet view."""

    method: str
    step: str
    orientation_faces: CubeOrientation
    palette: str
    breadcrumb: list[BreadcrumbItem]
    pool: str
    pools: list[ReviewPool]
    family: str
    families: list[CaseFamily]
    families_url: str
    tiles: list[CaseTile]
    command: str
