"""Tests for the FSRS PerformanceRater."""
import unittest
from datetime import UTC
from datetime import datetime

from term_timer.constants import SECOND
from term_timer.fsrs.rating import TARGET_TIMES
from term_timer.fsrs.rating import PerformanceRater
from term_timer.fsrs.types import Rating
from term_timer.solve import Solve


def make_solve(elapsed_ns: int, moves: str | None = None) -> Solve:
    """
    Create a minimal Solve for rating tests.

    Returns:
        A Solve instance with the given elapsed time and optional moves.

    """
    return Solve(
        date=datetime.now(tz=UTC).timestamp(),
        time=elapsed_ns,
        scramble="R U R' U'",
        moves=moves,
    )


class TestRateWithoutBluetooth(unittest.TestCase):
    """rate_without_bluetooth() always uses TARGET_TIMES as baseline."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()

    def test_pll_under_target_is_good(self) -> None:
        """2.0s target for PLL: execution at 1.9s -> Good."""
        elapsed = int(1.9 * SECOND)
        rating = self.rater.rate_without_bluetooth(elapsed, 'pll')
        self.assertEqual(rating, Rating.Good)

    def test_pll_well_under_target_is_easy(self) -> None:
        """2.0s target for PLL: execution at 1.5s (< 0.8x2.0) -> Easy."""
        elapsed = int(1.5 * SECOND)
        rating = self.rater.rate_without_bluetooth(elapsed, 'pll')
        self.assertEqual(rating, Rating.Easy)

    def test_pll_over_hard_threshold_is_hard(self) -> None:
        """2.0s target for PLL: execution at 2.5s (> 1.2x2.0) -> Hard."""
        elapsed = int(2.5 * SECOND)
        rating = self.rater.rate_without_bluetooth(elapsed, 'pll')
        self.assertEqual(rating, Rating.Hard)

    def test_pll_over_again_threshold_is_again(self) -> None:
        """2.0s target for PLL: execution at 3.5s (> 1.5x2.0) -> Again."""
        elapsed = int(3.5 * SECOND)
        rating = self.rater.rate_without_bluetooth(elapsed, 'pll')
        self.assertEqual(rating, Rating.Again)

    def test_oll_uses_own_target(self) -> None:
        """OLL target is 2.5s: 1.9s (< 0.8x2.5=2.0s) -> Easy."""
        elapsed = int(1.9 * SECOND)
        rating = self.rater.rate_without_bluetooth(elapsed, 'oll')
        self.assertEqual(rating, Rating.Easy)

    def test_unknown_step_uses_default_3s(self) -> None:
        """Unknown step falls back to 3.0s default target."""
        elapsed = int(2.9 * SECOND)
        rating = self.rater.rate_without_bluetooth(elapsed, 'unknown')
        self.assertEqual(rating, Rating.Good)


class TestRateDispatchWithoutBluetooth(unittest.TestCase):
    """rate() uses rate_without_bluetooth() when solve has no moves."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        # Generous history so baseline would differ from target if used.
        self.fast_history = [500] * 15  # 500 ms Ao12 baseline

    def test_rate_no_moves_ignores_history(self) -> None:
        """Without Bluetooth, history is ignored: target drives the rating."""
        # PLL target = 2.0s; execution = 1.9s -> Good regardless of history.
        solve = make_solve(int(1.9 * SECOND), moves=None)
        rating = self.rater.rate(solve, self.fast_history, 'pll')
        self.assertEqual(rating, Rating.Good)

    def test_rate_no_moves_again_on_slow(self) -> None:
        """Without Bluetooth, slow execution -> Again vs the step target."""
        solve = make_solve(int(4.0 * SECOND), moves=None)
        rating = self.rater.rate(solve, [], 'pll')
        self.assertEqual(rating, Rating.Again)


class TestRateWithBluetooth(unittest.TestCase):
    """rate() uses composite score when solve has move data."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()

    def test_advanced_solve_not_dispatched_to_without_bluetooth(self) -> None:
        """
        With move data, rate() uses composite path (not the fixed target).

        PLL target = 2.0s; history Ao12 ~3.0s; elapsed = 2.9s.
        Without BT: ratio vs 2.0s = 1.45 -> Hard.
        With BT (time_ratio weight 0.5, rest 0): ratio vs 3.0s Ao12 = 0.97
          -> score ~0.48 -> Easy.
        """
        history_ms = [3000] * 15  # 3000 ms mean -> ~3.0s baseline
        solve = make_solve(int(2.9 * SECOND), moves="R U R'@100")
        rating = self.rater.rate(solve, history_ms, 'pll')
        self.assertEqual(rating, Rating.Easy)


class TestTargetTimes(unittest.TestCase):
    """Validate that TARGET_TIMES covers the expected steps."""

    def test_known_steps_present(self) -> None:
        """All standard CFOP steps should have a target time."""
        for step in ('oll', 'pll', 'f2l', 'af2l', 'cross', 'ecross'):
            self.assertIn(step, TARGET_TIMES)

    def test_pll_target_is_2s(self) -> None:
        """PLL target should be 2.0 seconds."""
        self.assertEqual(TARGET_TIMES['pll'], 2.0)

    def test_oll_target_is_2_5s(self) -> None:
        """OLL target should be 2.5 seconds."""
        self.assertEqual(TARGET_TIMES['oll'], 2.5)


if __name__ == '__main__':
    unittest.main()
