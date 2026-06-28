"""Type definitions for methods."""
from collections.abc import Callable
from typing import Literal
from typing import NamedTuple
from typing import TypeAlias
from typing import TypedDict

from cubing_algs.algorithm import Algorithm

# Facelet pattern encoding
EncodedMask: TypeAlias = str  # noqa: UP040
# Orientation like "FR", "FL y", etc.
Configuration: TypeAlias = str  # noqa: UP040
CaseMasks: TypeAlias = dict[EncodedMask, list[Configuration]]  # noqa: UP040


class NormRange(NamedTuple):
    """Inclusive lower/upper bounds for a banded performance norm."""

    low: float
    high: float


class AufFlags(NamedTuple):
    """Per-step config: whether to detect pre-/post-AUF moves."""

    pre: bool
    post: bool


class AufCounts(NamedTuple):
    """Per-step result: detected pre-/post-AUF counts (None = not checked)."""

    pre: int | None
    post: int | None


class TrackedStep(NamedTuple):
    """One entry of a step group: a step name and its optional display label."""

    name: str
    label: str | None


class SolveNorms(TypedDict):
    """Whole-solve recognition/execution percentage bands."""

    recognition: NormRange
    execution: NormRange


class MethodNorms(TypedDict):
    """Per-step performance benchmarks for a solving method."""

    moves: dict[str, float]
    percent: dict[str, float]
    recognition: dict[str, NormRange]
    execution: dict[str, NormRange]
    solve: SolveNorms


class CaseMask(TypedDict):
    """Information about a specific case with its mask variations."""

    masks: CaseMasks


class CaseMaskInfo(TypedDict):
    """Mask configuration for a case."""

    case: str
    configurations: list[str]


class SourceCaseInfo(TypedDict):
    """Case information from source JSON file."""

    type: str
    main: str


class StepInfo(TypedDict):
    """
    Information about a single step during solve analysis.

    This is an internal type used during the solve analysis process.
    For aggregation across multiple solves, see StepAnalysis in types.py.
    """

    moves: list[int]
    increment: int
    case_infos: list[str]
    facelets: str


class StepSummary(TypedDict):
    """
    Summary information for a completed step.

    This is an internal detailed type used during solve analysis. It contains
    comprehensive information about a step including move sequences, timings,
    and percentages.

    For aggregation across multiple solves, this type is transformed into the
    simplified StepAnalysis type (see types.py) which retains only the
    essential fields needed for statistical analysis.
    """

    type: Literal['step', 'skipped', 'substep', 'virtual']
    name: str
    moves: Algorithm
    moves_reoriented: Algorithm
    moves_humanized: Algorithm
    moves_prettified: Algorithm
    times: list[float]
    index: list[int]
    qtm: int
    total: int
    execution: int
    recognition: int
    post_pause: int
    aufs: AufCounts
    total_percent: float
    execution_percent: float
    recognition_percent: float
    step_execution_percent: float
    step_recognition_percent: float
    increment: int
    case: str
    case_infos: list[str]
    facelets: str


class StepConfig(TypedDict, total=False):
    """
    Configuration for a solving step.

    This is an internal type used to configure how steps are analyzed.
    All fields are optional (total=False).
    """

    mask: str
    triggers: list[str]
    optimizers: list[Callable[[Algorithm], Algorithm]]
