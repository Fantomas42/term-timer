"""
Performance rating for FSRS using a rule-based decision tree.

With Bluetooth data, the rating reflects memorisation quality:

  AGAIN  — case not known: time > MAX_TIME_S or too many moves
  HARD   — execution error: cancelled/missed moves detected
  GOOD   — hesitation: more than MAX_PAUSES pauses, or TPS below MIN_TPS
  EASY   — clean execution: fast, few moves, no errors, no hesitation

Without Bluetooth data, falls back to a time-ratio comparison against
fixed step targets (TARGET_TIMES). This fallback will be refined later.
"""

from functools import cache
from typing import TYPE_CHECKING
from typing import NamedTuple

from cubing_algs.cases import get_collection
from fsrs import Rating

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.solve import Solve

TARGET_TIMES: dict[str, float] = {
    'oll': 2.5,
    'pll': 2.0,
    'f2l': 5.0,
    'af2l': 6.0,
    'cross': 3.0,
    'ecross': 4.0,
}

MAX_MOVES: dict[str, int] = {
    'oll': 17,
    'pll': 20,
    'f2l': 15,
    'af2l': 15,
    'cross': 15,
    'ecross': 15,
}


COLLECTION_STEP: dict[str, str] = {
    'CFOP/OLL': 'oll',
    'CFOP/PLL': 'pll',
    'CFOP/F2L': 'f2l',
    'CFOP/AF2L': 'af2l',
}

STEP_COLLECTION: dict[str, str] = {v: k for k, v in COLLECTION_STEP.items()}


@cache
def build_case_max_moves(step: str) -> dict[str, int]:
    """
    Build per-case HTM threshold for a single step, lazily on first use.

    P90 rather than max makes the threshold robust to outlier algorithms in
    the DB (e.g. OLL 04 has a 28 HTM algorithm despite a P90 of 15).
    Result is cached so subsequent calls for the same step are free.

    Args:
        step: Step name (e.g. 'oll', 'pll').

    Returns:
        Dict mapping case_code to HTM threshold (e.g. {'T': 16, 'F': 18}).
        Empty dict if the step has no known collection.

    """
    collection_name = STEP_COLLECTION.get(step)
    if collection_name is None:
        return {}
    collection = get_collection(collection_name)
    result: dict[str, int] = {}
    for case in collection.cases.values():
        if not case.algorithms:
            continue
        htms = sorted(a.metrics.htm for a in case.algorithms)
        p90 = htms[int(len(htms) * 0.9)]
        result[case.code] = p90 + 2
    return result


MIN_TPS: float = 4.0
MAX_TIME_S: float = 5.0
MAX_PAUSES: int = 2

SCORE_AGAIN: float = 1.5
SCORE_HARD: float = 1.2
SCORE_EASY: float = 0.8


class RatingBreakdown(NamedTuple):
    """Detailed components for a FSRS rating computation."""

    rating: Rating
    time_s: float
    htm: int
    missed_qtm: int
    pauses: int
    tps: float


class PerformanceRater:
    """Converts solve performance into FSRS ratings."""

    def rate_with_details(
        self,
        solve: 'Solve',
        step: str,
        case_name: str | None = None,
    ) -> RatingBreakdown:
        """
        Rate performance and return full breakdown.

        Returns:
            RatingBreakdown with rating and all diagnostic components.

        """
        rating = self.rate(solve, step, case_name)
        time_s = solve.time / SECOND

        if not solve.advanced:
            return RatingBreakdown(rating, time_s, 0, 0, 0, 0.0)

        htm = solve.solution.metrics.htm
        missed_qtm = solve.all_missed_moves
        pauses = solve.execution_pauses
        tps = htm / time_s if time_s > 0 and htm > 0 else 0.0
        return RatingBreakdown(rating, time_s, htm, missed_qtm, pauses, tps)

    def rate(
        self,
        solve: 'Solve',
        step: str,
        case_name: str | None = None,
    ) -> Rating:
        """
        Rate performance using a rule-based decision tree.

        Uses execution errors and hesitation signals to assess memorisation
        quality. Falls back to time-ratio comparison without Bluetooth data.

        Args:
            solve: Completed solve with optional advanced analysis
            step: Step name (e.g. 'oll', 'pll')
            case_name: Case code (e.g. 'F', '13') for per-case HTM threshold

        Returns:
            FSRS Rating: Again (1), Hard (2), Good (3), or Easy (4).

        """
        if not solve.advanced:
            return self.rate_without_bluetooth(solve.time, step)

        time_s = solve.time / SECOND
        htm = solve.solution.metrics.htm

        if time_s > MAX_TIME_S:
            return Rating.Again
        step_lower = step.lower()
        max_moves = (
            build_case_max_moves(step_lower).get(
                case_name,
                MAX_MOVES.get(step_lower, 15),
            )
            if case_name is not None
            else MAX_MOVES.get(step_lower, 15)
        )
        if htm > max_moves:
            return Rating.Again

        if solve.all_missed_moves > 0:
            return Rating.Hard

        tps = htm / time_s if time_s > 0 else 0.0
        if solve.execution_pauses > MAX_PAUSES or tps < MIN_TPS:
            return Rating.Good

        return Rating.Easy

    def rate_without_bluetooth(
        self,
        elapsed_time: int,
        step: str,
    ) -> Rating:
        """
        Rate performance using the fixed step target as baseline.

        Used when no Bluetooth move data is available. Always compares
        against the canonical step target time (e.g. 2.0s for PLL,
        2.5s for OLL) regardless of personal history.

        Args:
            elapsed_time: Elapsed time in nanoseconds
            step: Step name used to look up the target in TARGET_TIMES

        Returns:
            FSRS Rating based on ratio vs step target.

        """
        return self.score_to_rating(self.compute_time_ratio(elapsed_time, step))

    @staticmethod
    def compute_time_ratio(elapsed_time: int, step: str) -> float:
        """
        Compute elapsed time / target time ratio for the given step.

        Args:
            elapsed_time: Elapsed time in nanoseconds
            step: Step name used to look up the target in TARGET_TIMES

        Returns:
            Ratio of elapsed time to target time (1.0 = exactly on target).

        """
        target = TARGET_TIMES.get(step.lower(), 3.0)
        target_ns = int(target * SECOND)
        return elapsed_time / target_ns

    @staticmethod
    def score_to_rating(score: float) -> Rating:
        """
        Map composite score to FSRS Rating.

        Returns:
            Again if score > 1.5, Hard if > 1.2, Easy if < 0.8, Good otherwise.

        """
        if score > SCORE_AGAIN:
            return Rating.Again
        if score > SCORE_HARD:
            return Rating.Hard
        if score < SCORE_EASY:
            return Rating.Easy
        return Rating.Good
