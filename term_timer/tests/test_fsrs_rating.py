"""Tests for the FSRS PerformanceRater."""
import unittest
from datetime import UTC
from datetime import datetime
from unittest.mock import patch

from fsrs import Rating

from term_timer.constants import SECOND
from term_timer.fsrs.rating import BAND_AGAIN
from term_timer.fsrs.rating import BAND_EASY
from term_timer.fsrs.rating import BAND_GOOD
from term_timer.fsrs.rating import HIGH_STABILITY_FLOOR_DAYS
from term_timer.fsrs.rating import MAX_MOVES
from term_timer.fsrs.rating import MISSED_WEIGHT
from term_timer.fsrs.rating import PAUSE_TOLERANCE
from term_timer.fsrs.rating import PAUSE_WEIGHT
from term_timer.fsrs.rating import TIME_SCALE
from term_timer.fsrs.rating import TIME_SOFT_S
from term_timer.fsrs.rating import TPS_REF_STEP
from term_timer.fsrs.rating import TPS_SCALE
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
    # R / F / L never cancel with each other and contain no U, so the
    # trailing-AUF trim leaves the move count intact and missed_moves stays 0.
    move_cycle = ['R', 'F', 'L']
    moves = ' '.join(move_cycle[i % len(move_cycle)] for i in range(htm))
    return make_solve(int(elapsed_s * SECOND), moves=moves)


class TestRateWithoutBluetooth(unittest.TestCase):
    """Without execution data the rater is not consulted (manual rating)."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()

    def test_rate_no_moves_returns_good_default(self) -> None:
        """
        Without Bluetooth, rate() returns Good regardless of time.

        The no-Bluetooth path collects a manual 1-4 rating from the user, so
        this defensive default is never reached on the trainer path.
        """
        fast = make_solve(int(1.0 * SECOND), moves=None)
        slow = make_solve(int(8.0 * SECOND), moves=None)
        self.assertEqual(self.rater.rate(fast, 'pll'), Rating.Good)
        self.assertEqual(self.rater.rate(slow, 'pll'), Rating.Good)

    def test_rate_with_details_no_moves_is_zeroed(self) -> None:
        """Without Bluetooth, the breakdown carries no execution metrics."""
        solve = make_solve(int(2.0 * SECOND), moves=None)
        breakdown = self.rater.rate_with_details(solve, 'pll')
        self.assertEqual(breakdown.rating, Rating.Good)
        self.assertEqual(breakdown.htm, 0)
        self.assertEqual(breakdown.missed_qtm, 0)
        self.assertEqual(breakdown.pauses, 0)
        self.assertEqual(breakdown.tps, 0.0)


class TestExecutionScore(unittest.TestCase):
    """execution_score() builds the continuous penalty from metrics."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        self.ref = TPS_REF_STEP['pll']

    def test_flawless_execution_is_zero(self) -> None:
        """TPS at/above ref, no pauses/missed, fast time -> 0.0."""
        score = self.rater.execution_score(2.0, 0, 0, self.ref, 'pll')
        self.assertEqual(score, 0.0)

    def test_tps_above_ref_adds_no_penalty(self) -> None:
        """TPS above the per-step reference contributes nothing."""
        score = self.rater.execution_score(2.0, 0, 0, self.ref + 1.0, 'pll')
        self.assertEqual(score, 0.0)

    def test_tps_below_ref_scales_linearly(self) -> None:
        """TPS one full SCALE below ref yields a 1.0 penalty."""
        tps = self.ref - TPS_SCALE
        score = self.rater.execution_score(2.0, 0, 0, tps, 'pll')
        self.assertAlmostEqual(score, 1.0)

    def test_one_pause_is_tolerated(self) -> None:
        """A single regrip pause adds no penalty."""
        score = self.rater.execution_score(2.0, 0, 1, self.ref, 'pll')
        self.assertEqual(score, 0.0)

    def test_extra_pauses_are_penalised(self) -> None:
        """Pauses beyond the tolerated one add PAUSE_WEIGHT each."""
        score = self.rater.execution_score(2.0, 0, 3, self.ref, 'pll')
        self.assertAlmostEqual(score, 2 * PAUSE_WEIGHT)

    def test_missed_qtm_is_penalised(self) -> None:
        """Each missed QTM adds MISSED_WEIGHT."""
        score = self.rater.execution_score(2.0, 2, 0, self.ref, 'pll')
        self.assertAlmostEqual(score, 2 * MISSED_WEIGHT)

    def test_time_below_soft_guard_adds_nothing(self) -> None:
        """Time at the soft guard contributes nothing."""
        score = self.rater.execution_score(TIME_SOFT_S, 0, 0, self.ref, 'pll')
        self.assertEqual(score, 0.0)

    def test_time_past_soft_guard_scales(self) -> None:
        """Time one full SCALE past the guard yields a 1.0 penalty."""
        score = self.rater.execution_score(
            TIME_SOFT_S + TIME_SCALE, 0, 0, self.ref, 'pll',
        )
        self.assertAlmostEqual(score, 1.0)

    def test_components_sum(self) -> None:
        """Penalty components add together."""
        tps = self.ref - TPS_SCALE  # 1.0 from tps
        score = self.rater.execution_score(2.0, 1, 3, tps, 'pll')
        self.assertAlmostEqual(score, 1.0 + MISSED_WEIGHT + 2 * PAUSE_WEIGHT)

    def test_reference_is_step_relative(self) -> None:
        """Same TPS is penalised less for F2L (lower reference)."""
        tps = 4.0
        pll_score = self.rater.execution_score(2.0, 0, 0, tps, 'pll')
        f2l_score = self.rater.execution_score(2.0, 0, 0, tps, 'f2l')
        self.assertGreater(pll_score, f2l_score)

    def test_unknown_step_uses_default_reference(self) -> None:
        """An unknown step falls back to TPS_REF_DEFAULT."""
        score = self.rater.execution_score(2.0, 0, 0, 10.0, 'unknown')
        self.assertEqual(score, 0.0)


class TestScoreToBand(unittest.TestCase):
    """score_to_band() maps a continuous score to one of four bands."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()

    def test_below_easy_cut_is_easy(self) -> None:
        """Score under BAND_EASY -> Easy."""
        self.assertEqual(self.rater.score_to_band(0.0), Rating.Easy)
        self.assertEqual(
            self.rater.score_to_band(BAND_EASY - 0.01), Rating.Easy,
        )

    def test_easy_cut_is_easy(self) -> None:
        """Score exactly at BAND_EASY -> Easy (inclusive <=)."""
        self.assertEqual(self.rater.score_to_band(BAND_EASY), Rating.Easy)

    def test_good_band_is_good(self) -> None:
        """Score in (BAND_EASY, BAND_GOOD] -> Good."""
        self.assertEqual(
            self.rater.score_to_band(BAND_GOOD - 0.01), Rating.Good,
        )

    def test_good_cut_is_good(self) -> None:
        """Score exactly at BAND_GOOD -> Good (inclusive <=)."""
        self.assertEqual(self.rater.score_to_band(BAND_GOOD), Rating.Good)

    def test_hard_band_is_hard(self) -> None:
        """Score in (BAND_GOOD, BAND_AGAIN] -> Hard."""
        self.assertEqual(
            self.rater.score_to_band(BAND_AGAIN - 0.01), Rating.Hard,
        )

    def test_again_cut_is_hard(self) -> None:
        """Score exactly at BAND_AGAIN -> Hard (inclusive <=)."""
        self.assertEqual(self.rater.score_to_band(BAND_AGAIN), Rating.Hard)

    def test_above_again_is_again(self) -> None:
        """Score strictly above BAND_AGAIN -> Again."""
        self.assertEqual(
            self.rater.score_to_band(BAND_AGAIN + 0.01), Rating.Again,
        )
        self.assertEqual(self.rater.score_to_band(3.0), Rating.Again)


class TestRateWithBluetooth(unittest.TestCase):
    """rate() maps the execution score to a band with move data."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        # rate() calls solve.pauses(algorithm) / solve.missed_moves(algorithm)
        # on the AUF-stripped algorithm; patch the methods to isolate signals.
        patcher_pauses = patch.object(Solve, 'pauses', return_value=0)
        patcher_missed = patch.object(Solve, 'missed_moves', return_value=0)
        patcher_pauses.start()
        patcher_missed.start()
        self.addCleanup(patcher_pauses.stop)
        self.addCleanup(patcher_missed.stop)

    def test_clean_fast_is_easy(self) -> None:
        """TPS above ref, no pauses/missed -> EASY."""
        # 10 moves in 2.0s = 5.0 TPS > PLL ref 4.9.
        solve = make_bt_solve(htm=10, elapsed_s=2.0)
        self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Easy)

    def test_moderately_low_tps_is_hard(self) -> None:
        """TPS well below ref grades to HARD, not straight to AGAIN."""
        # 9 moves in 3.0s = 3.0 TPS; (4.9-3.0)/1.5 = 1.27 -> Hard.
        solve = make_bt_solve(htm=9, elapsed_s=3.0)
        self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Hard)

    def test_very_low_tps_is_again(self) -> None:
        """A very low TPS pushes the score past the AGAIN cut."""
        # 8 moves in 4.0s = 2.0 TPS; (4.9-2.0)/1.5 = 1.93 -> Again.
        solve = make_bt_solve(htm=8, elapsed_s=4.0)
        self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Again)

    def test_missed_moves_grade_down(self) -> None:
        """Missed QTM on an otherwise-clean solve -> GOOD."""
        with patch.object(Solve, 'missed_moves', return_value=2):
            # tps clean (0) + 2*0.30 missed = 0.6 -> Good.
            solve = make_bt_solve(htm=10, elapsed_s=2.0)
            self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Good)

    def test_extra_pauses_grade_down(self) -> None:
        """Several pauses on an otherwise-clean solve -> GOOD."""
        with patch.object(Solve, 'pauses', return_value=4):
            # (4-1)*0.25 = 0.75 -> Good.
            solve = make_bt_solve(htm=10, elapsed_s=2.0)
            self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Good)

    def test_single_pause_stays_easy(self) -> None:
        """One regrip pause does not move a clean solve off EASY."""
        with patch.object(Solve, 'pauses', return_value=1):
            solve = make_bt_solve(htm=10, elapsed_s=2.0)
            self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Easy)

    def test_over_move_limit_is_again(self) -> None:
        """HTM > per-case limit is a categorical AGAIN, before scoring."""
        limit = MAX_MOVES.get('pll', 15)
        # Fast (would be Easy by score) but over the move budget -> Again.
        solve = make_bt_solve(htm=limit + 1, elapsed_s=1.0)
        self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Again)

    def test_at_move_limit_is_not_again_by_moves(self) -> None:
        """HTM == limit does not trigger the categorical AGAIN."""
        limit = MAX_MOVES.get('pll', 15)
        solve = make_bt_solve(htm=limit, elapsed_s=2.0)
        self.assertNotEqual(self.rater.rate(solve, 'pll'), Rating.Again)

    def test_unknown_step_uses_default_max_moves(self) -> None:
        """Unknown step uses 15 as default move limit."""
        solve = make_bt_solve(htm=16, elapsed_s=2.0)
        self.assertEqual(self.rater.rate(solve, 'unknown_step'), Rating.Again)


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
            patch.object(Solve, 'pauses', return_value=0),
            patch.object(Solve, 'missed_moves', return_value=0),
        ):
            solve = make_bt_solve(htm=htm_between, elapsed_s=1.0)
            self.assertNotEqual(rater.rate(solve, 'pll', 'Gd'), Rating.Again)
            self.assertEqual(rater.rate(solve, 'pll'), Rating.Again)

    def test_unknown_case_falls_back_to_step(self) -> None:
        """rate() with an unknown case_name falls back to step-level limit."""
        rater = PerformanceRater()
        limit = MAX_MOVES.get('pll', 15)
        with (
            patch.object(Solve, 'pauses', return_value=0),
            patch.object(Solve, 'missed_moves', return_value=0),
        ):
            solve = make_bt_solve(htm=limit + 1, elapsed_s=1.0)
            self.assertEqual(
                rater.rate(solve, 'pll', 'UNKNOWN_CASE'), Rating.Again,
            )


class TestHighStabilityFloor(unittest.TestCase):
    """
    High-stability cards are protected from purely speed-driven lapses.

    A score-path Again (TPS too low) is floored to Hard when execution was
    clean (no missed moves, pauses within tolerance) and the card already has
    stability >= HIGH_STABILITY_FLOOR_DAYS. htm-forcing and missed moves still
    produce Again unconditionally.
    """

    # PLL ref 4.9 TPS; 8 moves / 4.0s = 2.0 TPS -> score 1.93 -> Again.
    SLOW_HTM = 8
    SLOW_S = 4.0

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        patcher_pauses = patch.object(Solve, 'pauses', return_value=0)
        patcher_missed = patch.object(Solve, 'missed_moves', return_value=0)
        patcher_pauses.start()
        patcher_missed.start()
        self.addCleanup(patcher_pauses.stop)
        self.addCleanup(patcher_missed.stop)

    def test_slow_clean_high_stability_floors_to_hard(self) -> None:
        """TPS-only Again on a high-stability card is floored to Hard."""
        solve = make_bt_solve(htm=self.SLOW_HTM, elapsed_s=self.SLOW_S)
        # Sanity: without stability the score produces Again.
        self.assertEqual(self.rater.rate(solve, 'pll'), Rating.Again)
        # With high stability and clean execution: floored to Hard.
        self.assertEqual(
            self.rater.rate(
                solve, 'pll', stability=HIGH_STABILITY_FLOOR_DAYS,
            ),
            Rating.Hard,
        )

    def test_slow_clean_low_stability_stays_again(self) -> None:
        """TPS-only Again on a low-stability card is not floored."""
        solve = make_bt_solve(htm=self.SLOW_HTM, elapsed_s=self.SLOW_S)
        self.assertEqual(
            self.rater.rate(
                solve, 'pll', stability=HIGH_STABILITY_FLOOR_DAYS - 1.0,
            ),
            Rating.Again,
        )

    def test_missed_moves_high_stability_stays_again(self) -> None:
        """Missed moves are a structural signal: floor does not apply."""
        with patch.object(
            Solve, 'missed_moves', return_value=PAUSE_TOLERANCE + 1,
        ):
            solve = make_bt_solve(htm=self.SLOW_HTM, elapsed_s=self.SLOW_S)
            self.assertEqual(
                self.rater.rate(
                    solve, 'pll', stability=HIGH_STABILITY_FLOOR_DAYS,
                ),
                Rating.Again,
            )

    def test_htm_forcing_high_stability_stays_again(self) -> None:
        """htm-forcing is categorical: floor does not apply at high stab."""
        limit = MAX_MOVES.get('pll', 15)
        # A fast solve that would be Easy by score but is over the move budget.
        solve = make_bt_solve(htm=limit + 1, elapsed_s=1.0)
        self.assertEqual(
            self.rater.rate(
                solve, 'pll', stability=HIGH_STABILITY_FLOOR_DAYS,
            ),
            Rating.Again,
        )
