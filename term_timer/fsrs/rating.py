"""
Performance rating for FSRS from execution metrics.

With Bluetooth data the rating reflects muscle-memory quality through a
continuous penalty score mapped to four bands, rather than a hard cascade.
A hard cascade made the per-case distribution bimodal (AGAIN <-> EASY): the
slow tail of a *known* case crashed straight to AGAIN (an FSRS lapse) with
no GOOD/HARD cushion. The continuous score gives a slow-but-clean known case
a middle band instead.

  score = tps_pen + pause_pen + missed_pen + time_pen

  - TPS is the primary signal (penalty grows below a per-step reference).
  - One pause is a legitimate regrip; only extra pauses are penalised.
  - A missed QTM (after AUF stripping) is a real cancellation error.
  - Time is a soft guard past TIME_SOFT_S, not a cliff.

An alg far over its per-case move budget is a categorical AGAIN override
(OCLL forcing = case structurally not memorised).

Without Bluetooth data there is no execution signal to rate, so the user
declares the rating manually at the keyboard; this module is not consulted
on that path.
"""

from functools import cache
from typing import TYPE_CHECKING
from typing import NamedTuple

from cubing_algs.cases import get_collection
from cubing_algs.constants import AUF_CHAR
from cubing_algs.transform.trim import trim_moves
from fsrs import Rating

from term_timer.constants import SECOND

if TYPE_CHECKING:
    from term_timer.solve import Solve

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


# Graded score: TPS is the primary signal. At or above the per-step
# reference the case feels grooved (no penalty); below it the penalty grows
# linearly over TPS_SCALE. The reference is per-step because F2L's natural
# TPS is lower than OLL/PLL (relative calibration, no per-case storage).
TPS_REF_STEP: dict[str, float] = {
    'oll': 4.6,
    'pll': 4.9,
    'f2l': 4.2,
}
TPS_REF_DEFAULT: float = 4.6
TPS_SCALE: float = 1.5

# A single pause is a legitimate regrip; only extra pauses are penalised.
PAUSE_TOLERANCE: int = 1
PAUSE_WEIGHT: float = 0.25

# After AUF stripping, a missed QTM is a real cancellation error.
MISSED_WEIGHT: float = 0.30

# Time is a soft guard, not a cliff: it only adds penalty past TIME_SOFT_S,
# to catch genuinely-stuck executions that TPS alone might miss.
TIME_SOFT_S: float = 5.5
TIME_SCALE: float = 2.0

# Continuous score -> four bands. The middle (GOOD/HARD) is now reachable.
BAND_EASY: float = 0.5
BAND_GOOD: float = 1.0
BAND_AGAIN: float = 1.5

# A purely speed-driven Again (clean execution, no missed moves, no
# htm-forcing) is floored to Hard on high-stability cards so a known-but-slow
# rep does not wipe weeks of accumulated stability. Missed moves and
# htm-forcing still produce Again unconditionally — structural non-memorisation.
HIGH_STABILITY_FLOOR_DAYS: float = 14.0


class RatingBreakdown(NamedTuple):
    """Detailed components for a FSRS rating computation."""

    rating: Rating
    time_s: float
    htm: int
    missed_qtm: int
    pauses: int
    tps: float
    score: float


class PerformanceRater:
    """Converts solve performance into FSRS ratings."""

    @staticmethod
    def execution_metrics(
        solve: 'Solve',
    ) -> tuple[float, int, int, int, float]:
        """
        Compute execution metrics with trailing AUF stripped.

        The final AUF (alignment moves at the end of the algorithm) pollutes
        the HTM, missed-move and pause signals: a wrong AUF inflates the move
        count, registers as missed QTM, and the recognition gap before it is
        counted as a pause. Stripping it isolates the muscle-memory signal.

        The solution is first reoriented into the canonical frame (last layer
        on U) so the AUF is expressed as ``U``; without this the recorded
        moves keep the cube frame (last layer often on D) and the trim would
        match nothing. Only the trailing AUF is trimmed; the leading edge is
        kept intact. TPS uses the full HTM so hand speed is not deflated.

        Args:
            solve: Completed solve with Bluetooth move data.

        Returns:
            Tuple of (time_s, htm, missed_qtm, pauses, tps), where htm,
            missed_qtm and pauses are computed on the AUF-stripped algorithm.

        """
        time_s = solve.time / SECOND
        oriented = solve.translation(solve.solution)
        algorithm = oriented.transform(
            trim_moves(AUF_CHAR, start=False, end=True),
        )
        htm = algorithm.metrics.htm
        missed_qtm = solve.missed_moves(algorithm)
        pauses = solve.pauses(algorithm)
        full_htm = oriented.metrics.htm
        tps = full_htm / time_s if time_s > 0 and full_htm > 0 else 0.0
        return time_s, htm, missed_qtm, pauses, tps

    def rate_with_details(
        self,
        solve: 'Solve',
        step: str,
        case_name: str | None = None,
        stability: float | None = None,
    ) -> RatingBreakdown:
        """
        Rate performance and return full breakdown.

        Args:
            solve: Completed solve with optional advanced analysis.
            step: Step name (e.g. 'oll', 'pll').
            case_name: Case code for per-case HTM threshold.
            stability: Current FSRS stability in days, used to floor Again to
                Hard on high-stability cards with clean execution.

        Returns:
            RatingBreakdown with rating and all diagnostic components.

        """
        rating = self.rate(solve, step, case_name, stability)

        if not solve.advanced:
            return RatingBreakdown(
                rating, solve.time / SECOND, 0, 0, 0, 0.0, 0.0,
            )

        time_s, htm, missed_qtm, pauses, tps = self.execution_metrics(solve)
        score = self.execution_score(time_s, missed_qtm, pauses, tps, step)
        return RatingBreakdown(
            rating, time_s, htm, missed_qtm, pauses, tps, score,
        )

    def rate(
        self,
        solve: 'Solve',
        step: str,
        case_name: str | None = None,
        stability: float | None = None,
    ) -> Rating:
        """
        Rate performance from a continuous execution score.

        An alg over its per-case move budget is a categorical AGAIN (forcing);
        otherwise the penalty score maps to a band. Without Bluetooth data the
        rating is collected manually, so this is not reached on the trainer
        path; it returns Good as a defensive default.

        A purely speed-driven Again is floored to Hard when the execution was
        clean (no missed moves, pause within tolerance) and the card already
        has high stability: a known-but-slow rep should not reset weeks of
        muscle memory. htm-forcing and missed moves still produce Again
        unconditionally as they signal structural non-memorisation.

        Args:
            solve: Completed solve with optional advanced analysis.
            step: Step name (e.g. 'oll', 'pll').
            case_name: Case code (e.g. 'F', '13') for per-case HTM threshold.
            stability: Current FSRS stability in days; None disables the floor.

        Returns:
            FSRS Rating: Again (1), Hard (2), Good (3), or Easy (4).

        """
        if not solve.advanced:
            return Rating.Good

        time_s, htm, missed_qtm, pauses, tps = self.execution_metrics(solve)

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

        score = self.execution_score(
            time_s, missed_qtm, pauses, tps, step_lower,
        )
        rating = self.score_to_band(score)
        if (
            rating == Rating.Again
            and missed_qtm == 0
            and pauses <= PAUSE_TOLERANCE
            and stability is not None
            and stability >= HIGH_STABILITY_FLOOR_DAYS
        ):
            return Rating.Hard
        return rating

    @staticmethod
    def execution_score(
        time_s: float,
        missed_qtm: int,
        pauses: int,
        tps: float,
        step: str,
    ) -> float:
        """
        Compute the continuous penalty score from execution metrics.

        Higher means worse. TPS below the per-step reference is the primary
        driver; pauses beyond one regrip, missed QTM, and time past the soft
        guard add on top.

        Returns:
            Non-negative penalty score (0.0 = flawless, grooved execution).

        """
        tps_ref = TPS_REF_STEP.get(step, TPS_REF_DEFAULT)
        tps_pen = max(0.0, (tps_ref - tps) / TPS_SCALE)
        pause_pen = max(0, pauses - PAUSE_TOLERANCE) * PAUSE_WEIGHT
        missed_pen = missed_qtm * MISSED_WEIGHT
        time_pen = max(0.0, (time_s - TIME_SOFT_S) / TIME_SCALE)
        return tps_pen + pause_pen + missed_pen + time_pen

    @staticmethod
    def score_to_band(score: float) -> Rating:
        """
        Map a continuous penalty score to a FSRS band.

        Returns:
            Easy if score < 0.5, Good if < 1.0, Hard if < 1.5, else Again.

        """
        if score < BAND_EASY:
            return Rating.Easy
        if score < BAND_GOOD:
            return Rating.Good
        if score < BAND_AGAIN:
            return Rating.Hard
        return Rating.Again
