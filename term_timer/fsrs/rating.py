"""Performance rating for FSRS using a composite score."""

from typing import TYPE_CHECKING

from cubing_algs.cases import get_case
from cubing_algs.transform.auf import remove_auf_moves
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

# Target turns per second per step.
# tps_score = target_tps / actual_tps: higher = slower = worse,
# consistent with time_ratio so score_to_rating applies uniformly.
TARGET_TPS: dict[str, float] = {
    'oll': 6.0,
    'pll': 8.0,
    'f2l': 4.0,
    'af2l': 3.5,
    'cross': 5.0,
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
        step: str,
    ) -> Rating:
        """
        Rate performance using a composite score.

        Combines TPS score with execution quality signals when advanced
        Bluetooth data is available. Falls back to time-only rating otherwise.

        Args:
            solve: Completed solve with optional advanced analysis
            step: Step name (e.g. 'oll', 'pll')

        Returns:
            FSRS Rating: Again (1), Hard (2), Good (3), or Easy (4).

        """
        if not solve.advanced:
            return self.rate_without_bluetooth(solve.time, step)

        tps_score = self.compute_tps_score(solve, step)
        pauses = solve.execution_pauses
        missed_qtm = solve.all_missed_moves
        delta_htm = self.compute_delta_htm(solve, step)

        # tps_score is the base: at target TPS with no quality issues,
        # score = 1.0 → Good. Execution penalties add to the score.
        score = tps_score + pauses * 0.2 + missed_qtm * 0.2 + delta_htm * 0.1
        return self.score_to_rating(score)

    def rate_without_bluetooth(
        self,
        elapsed_time: int,
        step: str,
    ) -> Rating:
        """
        Rate performance using the fixed step target as baseline.

        Used when no Bluetooth move data is available. Always compares
        against the canonical step target time (e.g. 2.0s for PLL,
        2.5s for OLL) regardless of personal history, so that absolute
        speed goals drive the rating rather than relative improvement.

        Args:
            elapsed_time: Elapsed time in nanoseconds
            step: Step name used to look up the target in TARGET_TIMES

        Returns:
            FSRS Rating based on ratio vs step target.

        """
        target = TARGET_TIMES.get(step.lower(), 3.0)
        target_ns = int(target * SECOND)
        ratio = elapsed_time / target_ns
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
    def compute_tps_score(solve: 'Solve', step: str) -> float:
        """
        Compute TPS score: target_tps / actual_tps.

        Higher score means slower execution (consistent with time_ratio so
        score_to_rating applies uniformly). Reaching the target TPS gives
        exactly 1.0 (Good territory). Below target → score > 1.0 (Hard/Again).
        Above target → score < 1.0 (Easy).

        TPS is computed using ``solve.time`` (total solve time including
        recognition), so recognition latency penalises the score.

        Args:
            solve: Completed solve with BT move data
            step: Step name used to look up the target in TARGET_TPS

        Returns:
            tps_score clamped to [0.3, 3.0].

        """
        htm = solve.solution.metrics.htm
        if htm == 0 or solve.time == 0:
            return 1.0  # neutral: no moves recorded
        actual_tps = htm / (solve.time / SECOND)
        target = TARGET_TPS.get(step.lower(), 5.0)
        return max(0.3, min(target / actual_tps, 3.0))

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
