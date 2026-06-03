"""Tests for the FSRS PerformanceRater."""
import unittest
from datetime import UTC
from datetime import datetime
from unittest.mock import PropertyMock
from unittest.mock import patch

from fsrs import Rating

from term_timer.constants import SECOND
from term_timer.fsrs.rating import MAX_MOVES
from term_timer.fsrs.rating import MAX_PAUSES
from term_timer.fsrs.rating import MAX_TIME_S
from term_timer.fsrs.rating import TARGET_TIMES
from term_timer.fsrs.rating import PerformanceRater
from term_timer.fsrs.rating import build_case_max_moves
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

    def test_rate_no_moves_uses_target(self) -> None:
        """Without Bluetooth, target time drives the rating."""
        # PLL target = 2.0s; execution = 1.9s -> Good.
        solve = make_solve(int(1.9 * SECOND), moves=None)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Good)

    def test_rate_no_moves_again_on_slow(self) -> None:
        """Without Bluetooth, slow execution -> Again vs the step target."""
        solve = make_solve(int(4.0 * SECOND), moves=None)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Again)


class TestRateWithBluetooth(unittest.TestCase):
    """rate() uses rule-based decision tree when solve has move data."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        # Default: no pauses, no missed moves, no CFOP step analysis.
        patcher_method = patch.object(
            Solve,
            'method_applied',
            new_callable=PropertyMock,
            return_value=None,
        )
        patcher_pauses = patch.object(
            Solve,
            'execution_pauses',
            new_callable=PropertyMock,
            return_value=0,
        )
        patcher_missed = patch.object(
            Solve,
            'all_missed_moves',
            new_callable=PropertyMock,
            return_value=0,
        )
        patcher_method.start()
        patcher_pauses.start()
        patcher_missed.start()
        self.addCleanup(patcher_method.stop)
        self.addCleanup(patcher_pauses.stop)
        self.addCleanup(patcher_missed.stop)

    def test_over_time_limit_is_again(self) -> None:
        """Execution time > MAX_TIME_S -> AGAIN."""
        solve = make_bt_solve(htm=8, elapsed_s=MAX_TIME_S + 0.1)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Again)

    def test_within_time_limit_is_not_again_by_time(self) -> None:
        """Execution time <= MAX_TIME_S doesn't trigger AGAIN by time."""
        # Use enough moves for TPS >= MIN_TPS: 8 moves in 1.9s = 4.2 TPS.
        solve = make_bt_solve(htm=8, elapsed_s=MAX_TIME_S - 0.1)
        rating = self.rater.rate(solve, 'pll')
        self.assertNotEqual(rating, Rating.Again)

    def test_over_move_limit_is_again(self) -> None:
        """HTM > MAX_MOVES for step -> AGAIN."""
        limit = MAX_MOVES.get('pll', 15)
        solve = make_bt_solve(htm=limit + 1, elapsed_s=2.0)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Again)

    def test_at_move_limit_is_not_again_by_moves(self) -> None:
        """HTM == MAX_MOVES does not trigger AGAIN."""
        limit = MAX_MOVES.get('pll', 15)
        # limit moves in 2.0s: TPS = limit / 2.0; if < 4.0 → GOOD, not AGAIN.
        solve = make_bt_solve(htm=limit, elapsed_s=2.0)
        rating = self.rater.rate(solve, 'pll')
        self.assertNotEqual(rating, Rating.Again)

    def test_time_beats_missed_for_again(self) -> None:
        """AGAIN from time takes priority over HARD from missed moves."""
        with patch.object(
            Solve,
            'all_missed_moves',
            new_callable=PropertyMock,
            return_value=2,
        ):
            solve = make_bt_solve(htm=8, elapsed_s=MAX_TIME_S + 1.0)
            rating = self.rater.rate(solve, 'pll')
            self.assertEqual(rating, Rating.Again)

    def test_missed_moves_is_hard(self) -> None:
        """Cancelled moves -> HARD when time and HTM are within limits."""
        with patch.object(
            Solve,
            'all_missed_moves',
            new_callable=PropertyMock,
            return_value=1,
        ):
            # 8 moves in 1.5s = 5.3 TPS, well within all limits.
            solve = make_bt_solve(htm=8, elapsed_s=1.5)
            rating = self.rater.rate(solve, 'pll')
            self.assertEqual(rating, Rating.Hard)

    def test_too_many_pauses_is_good(self) -> None:
        """More than MAX_PAUSES pauses -> GOOD."""
        with patch.object(
            Solve,
            'execution_pauses',
            new_callable=PropertyMock,
            return_value=MAX_PAUSES + 1,
        ):
            solve = make_bt_solve(htm=8, elapsed_s=1.5)
            rating = self.rater.rate(solve, 'pll')
            self.assertEqual(rating, Rating.Good)

    def test_exactly_max_pauses_is_not_good(self) -> None:
        """Exactly MAX_PAUSES pauses doesn't trigger GOOD by pauses alone."""
        with patch.object(
            Solve,
            'execution_pauses',
            new_callable=PropertyMock,
            return_value=MAX_PAUSES,
        ):
            # 8 moves in 1.5s = 5.3 TPS >= MIN_TPS → EASY.
            solve = make_bt_solve(htm=8, elapsed_s=1.5)
            rating = self.rater.rate(solve, 'pll')
            self.assertEqual(rating, Rating.Easy)

    def test_low_tps_is_good(self) -> None:
        """TPS < MIN_TPS -> GOOD."""
        # 8 moves in 3.0s = 2.67 TPS < 4.0, within time and move limits.
        solve = make_bt_solve(htm=8, elapsed_s=3.0)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Good)

    def test_tps_at_minimum_is_easy(self) -> None:
        """TPS == MIN_TPS does not trigger GOOD (boundary is strict <)."""
        # 8 moves in 2.0s = exactly 4.0 TPS.
        solve = make_bt_solve(htm=8, elapsed_s=2.0)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Easy)

    def test_clean_execution_is_easy(self) -> None:
        """No errors, no hesitation, fast execution -> EASY."""
        # 8 moves in 1.5s = 5.3 TPS, within all limits.
        solve = make_bt_solve(htm=8, elapsed_s=1.5)
        rating = self.rater.rate(solve, 'pll')
        self.assertEqual(rating, Rating.Easy)

    def test_unknown_step_uses_default_max_moves(self) -> None:
        """Unknown step uses 15 as default MAX_MOVES."""
        solve = make_bt_solve(htm=16, elapsed_s=2.0)
        rating = self.rater.rate(solve, 'unknown_step')
        self.assertEqual(rating, Rating.Again)


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


class TestMaxMoves(unittest.TestCase):
    """Validate that MAX_MOVES covers the expected steps."""

    def test_known_steps_present(self) -> None:
        """All standard CFOP steps should have a max moves entry."""
        for step in ('oll', 'pll', 'f2l', 'af2l', 'cross', 'ecross'):
            self.assertIn(step, MAX_MOVES)

    def test_all_values_are_positive(self) -> None:
        """Every MAX_MOVES value must be a positive integer."""
        for step, limit in MAX_MOVES.items():
            self.assertGreater(limit, 0, msg=f'{step} has non-positive limit')

    def test_pll_is_twenty(self) -> None:
        """PLL limit is 20 (algos commonly reach 16-20 HTM)."""
        self.assertEqual(MAX_MOVES['pll'], 20)

    def test_oll_is_seventeen(self) -> None:
        """OLL limit is 17 (algos commonly reach 14-17 HTM)."""
        self.assertEqual(MAX_MOVES['oll'], 17)


class TestCaseMaxMoves(unittest.TestCase):
    """Validate the per-case HTM thresholds built from cubing_algs."""

    def test_known_cases_present(self) -> None:
        """Key OLL and PLL cases must have a threshold entry."""
        cases = [
            ('pll', 'T'), ('pll', 'F'), ('pll', 'Aa'),
            ('oll', '26'), ('oll', '07'),
        ]
        for step, code in cases:
            self.assertIn(code, build_case_max_moves(step))

    def test_all_values_are_positive(self) -> None:
        """Every build_case_max_moves value must be a positive integer."""
        for step in ('oll', 'pll', 'f2l', 'af2l'):
            for code, limit in build_case_max_moves(step).items():
                self.assertGreater(
                    limit, 0, msg=f'{step}:{code} has non-positive limit',
                )

    def test_case_name_overrides_step_fallback(self) -> None:
        """rate() uses build_case_max_moves when case_name is provided."""
        rater = PerformanceRater()
        # PLL Gd: P90 HTM in DB is 22, threshold = 24 > step PLL limit (20).
        # An HTM between the two should pass with case_name='Gd' but trigger
        # AGAIN with the step-level fallback (no case_name).
        case_threshold = build_case_max_moves('pll')['Gd']
        step_limit = MAX_MOVES['pll']
        self.assertGreater(case_threshold, step_limit)
        htm_between = step_limit + 2  # above step limit, below case threshold
        self.assertLess(htm_between, case_threshold)
        with (
            patch.object(
                Solve,
                'execution_pauses',
                new_callable=PropertyMock,
                return_value=0,
            ),
            patch.object(
                Solve,
                'all_missed_moves',
                new_callable=PropertyMock,
                return_value=0,
            ),
            patch.object(
                Solve,
                'method_applied',
                new_callable=PropertyMock,
                return_value=None,
            ),
        ):
            solve = make_bt_solve(htm=htm_between, elapsed_s=1.0)
            self.assertNotEqual(rater.rate(solve, 'pll', 'Gd'), Rating.Again)
            self.assertEqual(rater.rate(solve, 'pll'), Rating.Again)

    def test_unknown_case_falls_back_to_step(self) -> None:
        """rate() with an unknown case_name falls back to step-level limit."""
        rater = PerformanceRater()
        limit = MAX_MOVES.get('pll', 15)
        with (
            patch.object(
                Solve,
                'execution_pauses',
                new_callable=PropertyMock,
                return_value=0,
            ),
            patch.object(
                Solve,
                'all_missed_moves',
                new_callable=PropertyMock,
                return_value=0,
            ),
            patch.object(
                Solve,
                'method_applied',
                new_callable=PropertyMock,
                return_value=None,
            ),
        ):
            solve = make_bt_solve(htm=limit + 1, elapsed_s=1.0)
            self.assertEqual(
                rater.rate(solve, 'pll', 'UNKNOWN_CASE'), Rating.Again,
            )
