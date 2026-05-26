"""Performance rating for FSRS using a composite score."""

from typing import TYPE_CHECKING

from cubing_algs.cases import get_case
from cubing_algs.transform.auf import remove_auf_moves

from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND
from term_timer.fsrs.types import Rating
from term_timer.stats import Statistics

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

SCORE_AGAIN: float = 1.5
SCORE_HARD: float = 1.2
SCORE_EASY: float = 0.8


class PerformanceRater:
    """Converts solve performance into FSRS ratings."""

    def rate(
        self,
        solve: 'Solve',
        timings: list[int],
        step: str,
    ) -> Rating:
        """
        Rate performance using a composite score.

        Combines time ratio with execution quality signals when advanced
        Bluetooth data is available. Falls back to time-only rating otherwise.

        Args:
            solve: Completed solve with optional advanced analysis
            timings: Historical timings for this case (milliseconds)
            step: Step name (e.g. 'oll', 'pll')

        Returns:
            FSRS Rating: Again (1), Hard (2), Good (3), or Easy (4).

        """
        baseline = self.compute_baseline(timings, step)
        time_ratio = (solve.time / SECOND) / (baseline / SECOND)

        if not solve.advanced:
            return self.score_to_rating(time_ratio)

        pauses = solve.execution_pauses
        missed_qtm = solve.all_missed_moves
        delta_htm = self.compute_delta_htm(solve, step)

        score = (
            time_ratio * 0.5
            + pauses * 0.2
            + missed_qtm * 0.2
            + delta_htm * 0.1
        )
        return self.score_to_rating(score)

    def rate_performance(
        self,
        elapsed_time: int,
        timings: list[int],
        step: str,
    ) -> Rating:
        """
        Rate performance from raw elapsed time (time-only fallback).

        Args:
            elapsed_time: Elapsed time in nanoseconds
            timings: Historical timings for this case (milliseconds)
            step: Step name

        Returns:
            FSRS Rating based on time ratio vs baseline.

        """
        baseline = self.compute_baseline(timings, step)
        ratio = (elapsed_time / SECOND) / (baseline / SECOND)
        return self.score_to_rating(ratio)

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

    @staticmethod
    def compute_baseline(timings: list[int], step: str) -> int:
        """
        Compute baseline time in nanoseconds.

        Uses Ao12 if available, mean if some data exists, or step target.

        Args:
            timings: Historical timings in milliseconds
            step: Step name for target lookup

        Returns:
            Baseline in nanoseconds.

        """
        if len(timings) >= 12:
            stats = Statistics([t * MS_TO_NS_FACTOR for t in timings])
            ao12 = stats.ao12
            if ao12 > 0:
                return ao12

        if timings:
            return int(sum(timings) / len(timings) * MS_TO_NS_FACTOR)

        target = TARGET_TIMES.get(step.lower(), 3.0)
        return int(target * SECOND)

    @staticmethod
    def compute_delta_htm(solve: 'Solve', step: str) -> int:
        """
        Compute extra HTM moves vs optimal for the first matching step.

        Args:
            solve: Completed solve with method analysis
            step: Step name used to look up optimal HTM

        Returns:
            Number of extra moves above optimal (0 if unavailable).

        """
        if not solve.method_applied:
            return 0

        step_code = step.upper()
        for step_summary in solve.method_applied.summary:
            if not step_summary['moves'] or not step_summary['case']:
                continue
            name_prefix = step_summary['name'].split(' ')[0]
            if name_prefix.upper() != step_code:
                continue
            try:
                case = get_case(name_prefix, step_summary['case'])
            except Exception:  # noqa: BLE001
                return 0
            optimal = case.optimal_htm
            if not optimal:
                return 0
            executed = step_summary['moves_prettified'].transform(
                remove_auf_moves,
            ).metrics.htm
            return max(0, executed - optimal)

        return 0
