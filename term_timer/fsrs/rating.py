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
  - Time is a soft guard past a per-step threshold, not a cliff.

An execution that needs more turns than the reference solution shown in the
trainer is a categorical AGAIN override (OCLL forcing = case structurally not
memorised). The comparison is done in QTM, the quarter-turn metric, which is
invariant to whether a double turn is recorded as ``U2`` or as two ``U`` (the
Bluetooth cube only emits quarter turns); fumbles (do-undo, triples) are
stripped from the execution first so a small slip does not read as forcing.

Without Bluetooth data there is no execution signal to rate, so the user
declares the rating manually at the keyboard; this module is not consulted
on that path.
"""

from typing import NamedTuple

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import AUF_CHAR
from cubing_algs.transform.trim import trim_moves
from fsrs import Rating

from term_timer.constants import SECOND
from term_timer.constants import STABILITY_LONG_TERM_DAYS
from term_timer.solve import Solve


# Per-step calibration references for the execution score. Both signals are
# step-relative and share the same keys, so they live in one table rather
# than two parallel dicts:
#
#   - tps_ref: TPS is the primary signal. At or above the reference the case
#     feels grooved (no penalty); below it the penalty grows linearly over
#     TPS_SCALE. It is per-step because F2L's natural TPS is lower than
#     OLL/PLL (relative calibration, no per-case storage).
#   - time_soft: a soft guard, not a cliff. Time only adds penalty past it,
#     to catch genuinely-stuck executions that TPS alone might miss (a
#     wall-clock freeze TPS averages away). It is per-step because a single
#     F2L pair finishes in less wall-clock time than a full last layer, and
#     it stays absolute rather than derived from the move count: a reference
#     of qtm / tps_ref would just restate the TPS penalty (time exceeds the
#     expected duration exactly when tps falls below tps_ref).
class StepReference(NamedTuple):
    """Per-step TPS and time references for the execution score."""

    tps_ref: float
    time_soft: float


STEP_REFERENCE: dict[str, StepReference] = {
    'oll': StepReference(tps_ref=4.6, time_soft=5.0),
    'pll': StepReference(tps_ref=4.9, time_soft=5.5),
    'f2l': StepReference(tps_ref=4.2, time_soft=4.0),
    'af2l': StepReference(tps_ref=4.5, time_soft=4.3),
}
TPS_SCALE: float = 1.5
TIME_SCALE: float = 2.0

# A single pause is a legitimate regrip; only extra pauses are penalised.
PAUSE_TOLERANCE: int = 1
PAUSE_WEIGHT: float = 0.25

# After AUF stripping, a missed QTM is a real cancellation error.
MISSED_WEIGHT: float = 0.30

# Continuous score -> four bands. The middle (GOOD/HARD) is now reachable.
BAND_EASY: float = 0.5
BAND_GOOD: float = 1.0
BAND_AGAIN: float = 1.5

# A purely speed-driven Again (clean execution, no missed moves, no
# forcing) is floored to Hard on high-stability cards so a known-but-slow
# rep does not wipe weeks of accumulated stability. Missed moves and
# forcing still produce Again unconditionally — structural non-memorisation.
# Shared with the scheduler mastery threshold — see term_timer/constants.py.
HIGH_STABILITY_FLOOR_DAYS: float = STABILITY_LONG_TERM_DAYS


class RatingBreakdown(NamedTuple):
    """Detailed components for a FSRS rating computation."""

    rating: Rating
    time_s: float
    executed_qtm: int
    missed_qtm: int
    pauses: int
    tps: float
    score: float
    tps_ref: float = 0.0
    time_soft: float = 0.0
    tps_pen: float = 0.0
    pause_pen: float = 0.0
    missed_pen: float = 0.0
    time_pen: float = 0.0
    reference_qtm: int = 0
    forced: bool = False
    floored: bool = False


class ExecutionPenalties(NamedTuple):
    """Individual penalty components of the execution score."""

    tps_ref: float
    time_soft: float
    tps_pen: float
    pause_pen: float
    missed_pen: float
    time_pen: float

    @property
    def score(self) -> float:
        """
        Total continuous penalty score, higher means worse.

        Returns:
            Sum of all penalty components (0.0 = flawless execution).

        """
        return self.tps_pen + self.pause_pen + self.missed_pen + self.time_pen


class PerformanceRater:
    """Converts solve performance into FSRS ratings."""

    @staticmethod
    def execution_metrics(
        solve: Solve,
    ) -> tuple[float, int, int, int, float]:
        """
        Compute execution metrics with trailing AUF stripped.

        The final AUF (alignment moves at the end of the algorithm) pollutes
        the move-count, missed-move and pause signals: a wrong AUF inflates
        the move count, registers as missed QTM, and the recognition gap
        before it is counted as a pause. Stripping it isolates the
        muscle-memory signal.

        The solution is first reoriented into the canonical frame (last layer
        on U) so the AUF is expressed as ``U``; without this the recorded
        moves keep the cube frame (last layer often on D) and the trim would
        match nothing. Only the trailing AUF is trimmed; the leading edge is
        kept intact. TPS is the solve's canonical ``solve.tps`` (full,
        untrimmed move count) so hand speed is not deflated.

        The executed QTM compared to the reference solution is measured after
        stripping fumbles (do-undo, triples, repeats) so a small slip does not
        read as forcing. QTM is invariant to whether a double turn is recorded
        as ``U2`` or as two ``U`` (the Bluetooth cube only emits quarter
        turns), so no double-merge is needed. Pauses and missed moves stay on
        the unmerged stream: the cancellation optimizers match on it directly.

        Args:
            solve: Completed solve with Bluetooth move data.

        Returns:
            Tuple of (time_s, executed_qtm, missed_qtm, pauses, tps), where
            executed_qtm, missed_qtm and pauses are computed on the
            AUF-stripped algorithm.

        """
        time_s = solve.time / SECOND
        oriented = solve.translation(solve.solution)
        algorithm = oriented.transform(
            trim_moves(AUF_CHAR, start=False, end=True),
        )
        executed_qtm = Solve.missed_moves_pair(algorithm)[1].metrics.qtm
        missed_qtm = solve.missed_moves(algorithm)
        pauses = solve.pauses(algorithm)

        return time_s, executed_qtm, missed_qtm, pauses, solve.tps

    @staticmethod
    def reference_qtm(reference: Algorithm) -> int:
        """
        QTM of the reference solution with its trailing AUF stripped.

        The reference (case algorithm plus the computed pre-AUF) is already in
        the canonical frame, so only the trailing AUF is trimmed — symmetric
        with the executed side, which keeps its leading pre-AUF too.

        Args:
            reference: Reference solution shown in the trainer.

        Returns:
            Reference QTM, or 0 when no reference is available.

        """
        return reference.transform(
            trim_moves(AUF_CHAR, start=False, end=True),
        ).metrics.qtm

    def rate_with_details(
        self,
        solve: Solve,
        step: str,
        reference: Algorithm,
        stability: float | None = None,
    ) -> RatingBreakdown:
        """
        Rate performance and return full breakdown.

        An execution needing more turns than the reference solution is a
        categorical AGAIN (forcing); otherwise the penalty score maps to a
        band. Without Bluetooth data the rating is collected manually, so this
        is not reached on the trainer path; it returns Good as a defensive
        default.

        A purely speed-driven Again is floored to Hard when the execution was
        clean (no missed moves, pause within tolerance) and the card already
        has high stability: a known-but-slow rep should not reset weeks of
        muscle memory. Forcing and missed moves still produce Again
        unconditionally as they signal structural non-memorisation.

        Args:
            solve: Completed solve with optional advanced analysis.
            step: Step name (e.g. 'oll', 'pll').
            reference: Reference solution shown in the trainer (case algorithm
                plus computed pre-AUF). An empty reference disables the forcing
                override (nothing to compare against).
            stability: Current FSRS stability in days, used to floor Again to
                Hard on high-stability cards with clean execution.

        Returns:
            RatingBreakdown with rating and all diagnostic components.

        """
        if not solve.advanced:
            return RatingBreakdown(
                Rating.Good, solve.time / SECOND, 0, 0, 0, 0.0, 0.0,
            )

        time_s, executed_qtm, missed_qtm, pauses, tps = (
            self.execution_metrics(solve)
        )
        reference_qtm = self.reference_qtm(reference)

        step_lower = step.lower()
        pens = self.execution_penalties(
            time_s, missed_qtm, pauses, tps, step_lower,
        )

        forced = reference_qtm > 0 and executed_qtm > reference_qtm
        rating = self.score_to_band(pens.score)
        floored = False
        if forced:
            rating = Rating.Again
        elif (
            rating == Rating.Again
            and missed_qtm == 0
            and pauses <= PAUSE_TOLERANCE
            and stability is not None
            and stability >= HIGH_STABILITY_FLOOR_DAYS
        ):
            rating = Rating.Hard
            floored = True

        return RatingBreakdown(
            rating,
            time_s,
            executed_qtm,
            missed_qtm,
            pauses,
            tps,
            pens.score,
            pens.tps_ref,
            pens.time_soft,
            pens.tps_pen,
            pens.pause_pen,
            pens.missed_pen,
            pens.time_pen,
            reference_qtm,
            forced,
            floored,
        )

    def rate(
        self,
        solve: Solve,
        step: str,
        reference: Algorithm,
        stability: float | None = None,
    ) -> Rating:
        """
        Rate performance from a continuous execution score.

        Thin wrapper over rate_with_details() for callers that only need
        the final rating; see that method for the full decision policy.

        Args:
            solve: Completed solve with optional advanced analysis.
            step: Step name (e.g. 'oll', 'pll').
            reference: Reference solution shown in the trainer; an empty
                reference disables the forcing override.
            stability: Current FSRS stability in days; None disables the floor.

        Returns:
            FSRS Rating: Again (1), Hard (2), Good (3), or Easy (4).

        """
        return self.rate_with_details(
            solve, step, reference, stability,
        ).rating

    @staticmethod
    def execution_penalties(
        time_s: float,
        missed_qtm: int,
        pauses: int,
        tps: float,
        step: str,
    ) -> ExecutionPenalties:
        """
        Compute the individual penalty components of the execution score.

        TPS below the per-step reference is the primary driver; pauses
        beyond one regrip, missed QTM, and time past the soft guard add
        on top.

        The step must be a key of STEP_REFERENCE (only steps without a
        training_case reach this path); an unknown step raises KeyError.

        Returns:
            ExecutionPenalties with each component and the per-step TPS and
            time references used; its score property sums them.

        """
        ref = STEP_REFERENCE[step]

        return ExecutionPenalties(
            tps_ref=ref.tps_ref,
            time_soft=ref.time_soft,
            tps_pen=max(0.0, (ref.tps_ref - tps) / TPS_SCALE),
            pause_pen=max(0, pauses - PAUSE_TOLERANCE) * PAUSE_WEIGHT,
            missed_pen=missed_qtm * MISSED_WEIGHT,
            time_pen=max(0.0, (time_s - ref.time_soft) / TIME_SCALE),
        )

    @staticmethod
    def score_to_band(score: float) -> Rating:
        """
        Map a continuous penalty score to a FSRS band.

        Returns:
            Easy if score <= 0.5, Good if <= 1.0, Hard if <= 1.5, else Again.

        """
        if score <= BAND_EASY:
            return Rating.Easy
        if score <= BAND_GOOD:
            return Rating.Good
        if score <= BAND_AGAIN:
            return Rating.Hard
        return Rating.Again
