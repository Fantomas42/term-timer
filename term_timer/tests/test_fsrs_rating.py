"""Tests for the FSRS PerformanceRater."""
import unittest
from datetime import UTC
from datetime import datetime
from unittest.mock import PropertyMock
from unittest.mock import patch

from term_timer.constants import SECOND
from term_timer.fsrs.rating import TARGET_TIMES
from term_timer.fsrs.rating import TARGET_TPS
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


def make_bt_solve(htm: int, elapsed_s: float) -> Solve:
    """
    Create a BT solve with a controlled HTM count and elapsed time.

    Builds a moves string of exactly ``htm`` single-turn moves so that
    ``solve.solution.metrics.htm == htm`` without relying on timing data.

    Returns:
        A Solve instance with move data, the given elapsed time, and the
        requested HTM count.

    """
    # R / U / F never cancel with each other, so missed_moves stays 0.
    move_cycle = ['R', 'U', 'F']
    moves = ' '.join(move_cycle[i % len(move_cycle)] for i in range(htm))
    return make_solve(int(elapsed_s * SECOND), moves=moves)


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
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Good)

    def test_rate_no_moves_again_on_slow(self) -> None:
        """Without Bluetooth, slow execution -> Again vs the step target."""
        solve = make_solve(int(4.0 * SECOND), moves=None)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Again)


class TestRateWithBluetooth(unittest.TestCase):
    """rate() uses TPS-based composite score when solve has move data."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        # Patch method_applied to None so execution_pauses / step_pauses
        # return 0 without triggering full CFOP analysis on minimal test solves.
        patcher = patch.object(
            Solve,
            'method_applied',
            new_callable=PropertyMock,
            return_value=None,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_at_target_tps_no_penalty_is_good(self) -> None:
        """
        PLL target = 8 TPS: 8 moves in 1.0s = exactly 8.0 TPS -> Good.

        tps_score = 8.0 / 8.0 = 1.0, no quality penalties -> score = 1.0.
        """
        solve = make_bt_solve(htm=8, elapsed_s=1.0)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Good)

    def test_above_target_tps_is_easy(self) -> None:
        """
        PLL target = 8 TPS: 8 moves in 0.7s ≈ 11.4 TPS -> Easy.

        tps_score = 8.0 / 11.4 ≈ 0.70 < 0.8 -> Easy.
        """
        solve = make_bt_solve(htm=8, elapsed_s=0.7)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Easy)

    def test_below_target_tps_is_hard(self) -> None:
        """
        PLL target = 8 TPS: 8 moves in 1.6s = 5.0 TPS -> Hard.

        tps_score = 8.0 / 5.0 = 1.6 > 1.5 -> Again... let's use 1.4s.
        8 moves in 1.4s ≈ 5.7 TPS -> tps_score = 8/5.7 ≈ 1.4 -> Hard.
        """
        solve = make_bt_solve(htm=8, elapsed_s=1.4)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Hard)

    def test_well_below_target_tps_is_again(self) -> None:
        """
        PLL target = 8 TPS: 8 moves in 2.0s = 4.0 TPS -> Again.

        tps_score = 8.0 / 4.0 = 2.0 > 1.5 -> Again.
        """
        solve = make_bt_solve(htm=8, elapsed_s=2.0)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Again)

    def test_bt_path_differs_from_no_bt(self) -> None:
        """
        BT and non-BT paths give different ratings for the same elapsed time.

        PLL target time = 2.0s, PLL target TPS = 8.0.
        8 moves in 1.9s without BT -> ratio 1.9/2.0 = 0.95 -> Good.
        8 moves in 1.9s with BT -> TPS = 4.2, tps_score = 1.9 -> Again.
        """
        solve_no_bt = make_solve(int(1.9 * SECOND), moves=None)
        solve_bt = make_bt_solve(htm=8, elapsed_s=1.9)
        rating_no_bt = self.rater.rate(solve_no_bt, 'pll')
        rating_bt = self.rater.rate(solve_bt, 'pll')
        self.assertNotEqual(rating_no_bt, rating_bt)


class TestComputeTpsScore(unittest.TestCase):
    """compute_tps_score() converts HTM + time into a normalised score."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()

    def test_at_target_returns_one(self) -> None:
        """Exactly hitting target TPS gives score = 1.0."""
        # OLL target = 6.0 TPS: 12 moves in 2.0s = 6.0 TPS
        solve = make_bt_solve(htm=12, elapsed_s=2.0)
        score = self.rater.compute_tps_score(solve, 'oll')
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_twice_target_returns_half(self) -> None:
        """Double the target TPS gives score = 0.5."""
        # OLL target = 6.0: 12 moves in 1.0s = 12.0 TPS -> 6/12 = 0.5
        solve = make_bt_solve(htm=12, elapsed_s=1.0)
        score = self.rater.compute_tps_score(solve, 'oll')
        self.assertAlmostEqual(score, 0.5, places=5)

    def test_zero_htm_returns_neutral(self) -> None:
        """Empty move list returns neutral score 1.0."""
        solve = make_solve(int(1.0 * SECOND), moves='')
        score = self.rater.compute_tps_score(solve, 'oll')
        self.assertEqual(score, 1.0)

    def test_unknown_step_uses_default(self) -> None:
        """Unknown step uses 5.0 TPS default."""
        # 10 moves in 1.0s = 10 TPS -> 5.0 / 10.0 = 0.5
        solve = make_bt_solve(htm=10, elapsed_s=1.0)
        score = self.rater.compute_tps_score(solve, 'unknown_step')
        self.assertAlmostEqual(score, 0.5, places=5)

    def test_score_clamped_at_minimum(self) -> None:
        """Extremely fast TPS is clamped to 0.3 (not arbitrarily small)."""
        # 100 moves in 0.1s = 1000 TPS -> 6/1000 = 0.006, clamped to 0.3
        solve = make_bt_solve(htm=100, elapsed_s=0.1)
        score = self.rater.compute_tps_score(solve, 'oll')
        self.assertEqual(score, 0.3)

    def test_score_clamped_at_maximum(self) -> None:
        """Extremely slow TPS is clamped to 3.0 (not arbitrarily large)."""
        # 1 move in 100s = 0.01 TPS -> 6/0.01 = 600, clamped to 3.0
        solve = make_bt_solve(htm=1, elapsed_s=100.0)
        score = self.rater.compute_tps_score(solve, 'oll')
        self.assertEqual(score, 3.0)


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


class TestTargetTps(unittest.TestCase):
    """Validate that TARGET_TPS covers the expected steps."""

    def test_known_steps_present(self) -> None:
        """All standard CFOP steps should have a target TPS."""
        for step in ('oll', 'pll', 'f2l', 'af2l', 'cross', 'ecross'):
            self.assertIn(step, TARGET_TPS)

    def test_pll_faster_than_oll(self) -> None:
        """PLL target TPS should be higher than OLL (shorter algorithm)."""
        self.assertGreater(TARGET_TPS['pll'], TARGET_TPS['oll'])

    def test_f2l_slower_than_oll(self) -> None:
        """F2L target TPS is lower than OLL (more look-ahead pauses)."""
        self.assertLess(TARGET_TPS['f2l'], TARGET_TPS['oll'])
