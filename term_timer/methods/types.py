"""Type definitions for methods."""
from collections.abc import Callable
from typing import Literal
from typing import TypedDict

from cubing_algs.algorithm import Algorithm


class CaseInfo(TypedDict):
    """Information about a specific case."""

    name: str
    main: str
    probability: float
    probability_label: str
    setups: list[str]
    masks: dict[str, list[str]]


class CaseMaskInfo(TypedDict):
    """Mask configuration for a case."""

    case: str
    configurations: list[str]


class SourceCaseInfo(TypedDict):
    """Case information from source JSON file."""

    type: str
    probability: str
    aliases: list[str]
    algorithms: list[str]
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
    aufs: list[int | None]
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
