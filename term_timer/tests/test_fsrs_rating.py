"""Tests for the FSRS PerformanceRater."""
import unittest
from datetime import UTC
from datetime import datetime
from unittest.mock import patch

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from fsrs import Rating

from term_timer.constants import SECOND
from term_timer.fsrs.rating import BAND_AGAIN
from term_timer.fsrs.rating import BAND_EASY
from term_timer.fsrs.rating import BAND_GOOD
from term_timer.fsrs.rating import HIGH_STABILITY_FLOOR_DAYS
from term_timer.fsrs.rating import MISSED_WEIGHT
from term_timer.fsrs.rating import PAUSE_TOLERANCE
from term_timer.fsrs.rating import PAUSE_WEIGHT
from term_timer.fsrs.rating import STEP_REFERENCE
from term_timer.fsrs.rating import TIME_SCALE
from term_timer.fsrs.rating import TPS_SCALE
from term_timer.fsrs.rating import PerformanceRater
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


def turns(count: int) -> str:
    """
    Build a string of ``count`` single quarter turns that never cancel.

    R / F / L never cancel with each other and contain no U, so the
    trailing-AUF trim leaves the move count intact and missed_moves stays 0.
    For single turns QTM equals the move count.

    Returns:
        A space-separated move string of ``count`` quarter turns.

    """
    move_cycle = ['R', 'F', 'L']
    return ' '.join(move_cycle[i % len(move_cycle)] for i in range(count))


def make_bt_solve(htm: int, elapsed_s: float) -> Solve:
    """
    Create a BT solve with a controlled move count and elapsed time.

    Builds a moves string of exactly ``htm`` single-turn moves so that
    ``solve.solution.metrics.qtm == htm`` without relying on timing data.

    Returns:
        A Solve instance with move data, the given elapsed time, and the
        requested move count.

    """
    return make_solve(int(elapsed_s * SECOND), moves=turns(htm))


def make_reference(qtm: int) -> Algorithm:
    """
    Build a reference solution of ``qtm`` quarter turns.

    Returns:
        An Algorithm whose reference QTM equals ``qtm``.

    """
    return parse_moves(turns(qtm))


# A reference long enough that the score path, not the forcing override,
# decides the rating in score-focused tests.
LONG_REFERENCE = make_reference(60)


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
        ref = make_reference(10)
        self.assertEqual(self.rater.rate(fast, 'pll', ref), Rating.Good)
        self.assertEqual(self.rater.rate(slow, 'pll', ref), Rating.Good)

    def test_rate_with_details_no_moves_is_zeroed(self) -> None:
        """Without Bluetooth, the breakdown carries no execution metrics."""
        solve = make_solve(int(2.0 * SECOND), moves=None)
        breakdown = self.rater.rate_with_details(
            solve, 'pll', make_reference(10),
        )
        self.assertEqual(breakdown.rating, Rating.Good)
        self.assertEqual(breakdown.executed_qtm, 0)
        self.assertEqual(breakdown.missed_qtm, 0)
        self.assertEqual(breakdown.pauses, 0)
        self.assertEqual(breakdown.tps, 0.0)


class TestExecutionPenalties(unittest.TestCase):
    """execution_penalties() builds the continuous penalty from metrics."""

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        self.ref = STEP_REFERENCE['pll'].tps_ref
        self.time_soft = STEP_REFERENCE['pll'].time_soft

    def test_flawless_execution_is_zero(self) -> None:
        """TPS at/above ref, no pauses/missed, fast time -> 0.0."""
        pens = self.rater.execution_penalties(2.0, 0, 0, self.ref, 'pll')
        self.assertEqual(pens.score, 0.0)

    def test_tps_above_ref_adds_no_penalty(self) -> None:
        """TPS above the per-step reference contributes nothing."""
        pens = self.rater.execution_penalties(
            2.0, 0, 0, self.ref + 1.0, 'pll',
        )
        self.assertEqual(pens.score, 0.0)

    def test_tps_below_ref_scales_linearly(self) -> None:
        """TPS one full SCALE below ref yields a 1.0 penalty."""
        tps = self.ref - TPS_SCALE
        pens = self.rater.execution_penalties(2.0, 0, 0, tps, 'pll')
        self.assertAlmostEqual(pens.score, 1.0)
        self.assertAlmostEqual(pens.tps_pen, 1.0)

    def test_one_pause_is_tolerated(self) -> None:
        """A single regrip pause adds no penalty."""
        pens = self.rater.execution_penalties(2.0, 0, 1, self.ref, 'pll')
        self.assertEqual(pens.score, 0.0)

    def test_extra_pauses_are_penalised(self) -> None:
        """Pauses beyond the tolerated one add PAUSE_WEIGHT each."""
        pens = self.rater.execution_penalties(2.0, 0, 3, self.ref, 'pll')
        self.assertAlmostEqual(pens.score, 2 * PAUSE_WEIGHT)
        self.assertAlmostEqual(pens.pause_pen, 2 * PAUSE_WEIGHT)

    def test_missed_qtm_is_penalised(self) -> None:
        """Each missed QTM adds MISSED_WEIGHT."""
        pens = self.rater.execution_penalties(2.0, 2, 0, self.ref, 'pll')
        self.assertAlmostEqual(pens.score, 2 * MISSED_WEIGHT)
        self.assertAlmostEqual(pens.missed_pen, 2 * MISSED_WEIGHT)

    def test_time_below_soft_guard_adds_nothing(self) -> None:
        """Time at the soft guard contributes nothing."""
        pens = self.rater.execution_penalties(
            self.time_soft, 0, 0, self.ref, 'pll',
        )
        self.assertEqual(pens.score, 0.0)

    def test_time_past_soft_guard_scales(self) -> None:
        """Time one full SCALE past the guard yields a 1.0 penalty."""
        pens = self.rater.execution_penalties(
            self.time_soft + TIME_SCALE, 0, 0, self.ref, 'pll',
        )
        self.assertAlmostEqual(pens.score, 1.0)
        self.assertAlmostEqual(pens.time_pen, 1.0)

    def test_components_sum(self) -> None:
        """Penalty components add together."""
        tps = self.ref - TPS_SCALE  # 1.0 from tps
        pens = self.rater.execution_penalties(2.0, 1, 3, tps, 'pll')
        self.assertAlmostEqual(
            pens.score, 1.0 + MISSED_WEIGHT + 2 * PAUSE_WEIGHT,
        )

    def test_reference_is_step_relative(self) -> None:
        """Same TPS is penalised less for F2L (lower reference)."""
        tps = 4.0
        pll_pens = self.rater.execution_penalties(2.0, 0, 0, tps, 'pll')
        f2l_pens = self.rater.execution_penalties(2.0, 0, 0, tps, 'f2l')
        self.assertGreater(pll_pens.score, f2l_pens.score)

    def test_time_guard_is_step_relative(self) -> None:
        """The same time is penalised more for F2L (lower soft guard)."""
        time_s = 4.5
        pll_pens = self.rater.execution_penalties(time_s, 0, 0, 10.0, 'pll')
        f2l_pens = self.rater.execution_penalties(time_s, 0, 0, 10.0, 'f2l')
        self.assertEqual(pll_pens.time_pen, 0.0)
        self.assertGreater(f2l_pens.time_pen, 0.0)

    def test_unknown_step_raises_key_error(self) -> None:
        """An unknown step has no reference and raises KeyError."""
        with self.assertRaises(KeyError):
            self.rater.execution_penalties(2.0, 0, 0, 10.0, 'unknown')


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
        self.assertEqual(
            self.rater.rate(solve, 'pll', LONG_REFERENCE), Rating.Easy,
        )

    def test_moderately_low_tps_is_hard(self) -> None:
        """TPS well below ref grades to HARD, not straight to AGAIN."""
        # 9 moves in 3.0s = 3.0 TPS; (4.9-3.0)/1.5 = 1.27 -> Hard.
        solve = make_bt_solve(htm=9, elapsed_s=3.0)
        self.assertEqual(
            self.rater.rate(solve, 'pll', LONG_REFERENCE), Rating.Hard,
        )

    def test_very_low_tps_is_again(self) -> None:
        """A very low TPS pushes the score past the AGAIN cut."""
        # 8 moves in 4.0s = 2.0 TPS; (4.9-2.0)/1.5 = 1.93 -> Again.
        solve = make_bt_solve(htm=8, elapsed_s=4.0)
        self.assertEqual(
            self.rater.rate(solve, 'pll', LONG_REFERENCE), Rating.Again,
        )

    def test_missed_moves_grade_down(self) -> None:
        """Missed QTM on an otherwise-clean solve -> GOOD."""
        with patch.object(Solve, 'missed_moves', return_value=2):
            # tps clean (0) + 2*0.30 missed = 0.6 -> Good.
            solve = make_bt_solve(htm=10, elapsed_s=2.0)
            self.assertEqual(
                self.rater.rate(solve, 'pll', LONG_REFERENCE), Rating.Good,
            )

    def test_extra_pauses_grade_down(self) -> None:
        """Several pauses on an otherwise-clean solve -> GOOD."""
        with patch.object(Solve, 'pauses', return_value=4):
            # (4-1)*0.25 = 0.75 -> Good.
            solve = make_bt_solve(htm=10, elapsed_s=2.0)
            self.assertEqual(
                self.rater.rate(solve, 'pll', LONG_REFERENCE), Rating.Good,
            )

    def test_single_pause_stays_easy(self) -> None:
        """One regrip pause does not move a clean solve off EASY."""
        with patch.object(Solve, 'pauses', return_value=1):
            solve = make_bt_solve(htm=10, elapsed_s=2.0)
            self.assertEqual(
                self.rater.rate(solve, 'pll', LONG_REFERENCE), Rating.Easy,
            )


class TestForcingDetection(unittest.TestCase):
    """
    Forcing is detected by comparing executed QTM to the reference solution.

    An execution that needs more turns than the reference (case algorithm plus
    pre-AUF) signals OCLL forcing: a categorical AGAIN before the score. The
    comparison is in QTM (invariant to ``U2`` vs ``U U``) and on the execution
    with fumbles stripped, so a small slip does not read as forcing.
    """

    def setUp(self) -> None:  # noqa: D102
        self.rater = PerformanceRater()
        patcher_pauses = patch.object(Solve, 'pauses', return_value=0)
        patcher_missed = patch.object(Solve, 'missed_moves', return_value=0)
        patcher_pauses.start()
        patcher_missed.start()
        self.addCleanup(patcher_pauses.stop)
        self.addCleanup(patcher_missed.stop)

    def test_over_reference_is_again(self) -> None:
        """Executed QTM above the reference is a categorical AGAIN."""
        # Fast (would be Easy by score) but longer than the reference.
        solve = make_bt_solve(htm=12, elapsed_s=1.0)
        self.assertEqual(
            self.rater.rate(solve, 'pll', make_reference(10)), Rating.Again,
        )

    def test_at_reference_is_not_forced(self) -> None:
        """Executed QTM equal to the reference does not force."""
        solve = make_bt_solve(htm=10, elapsed_s=2.0)
        self.assertNotEqual(
            self.rater.rate(solve, 'pll', make_reference(10)), Rating.Again,
        )

    def test_under_reference_is_not_forced(self) -> None:
        """A shorter-than-reference execution never forces."""
        solve = make_bt_solve(htm=8, elapsed_s=2.0)
        breakdown = self.rater.rate_with_details(
            solve, 'pll', make_reference(12),
        )
        self.assertFalse(breakdown.forced)

    def test_fumble_compressed_under_reference_is_not_forced(self) -> None:
        """
        A do-undo fumble inflates the raw stream but is stripped first.

        The raw execution ``R U R' F R R'`` is 6 QTM, above the 4 QTM
        reference, but ``R R'`` cancels: the compared execution is 4 QTM, so
        the slip does not read as forcing.
        """
        solve = make_solve(int(2.0 * SECOND), moves="R U R' F R R'")
        breakdown = self.rater.rate_with_details(
            solve, 'pll', parse_moves("R U R' F"),
        )
        self.assertEqual(breakdown.executed_qtm, 4)
        self.assertEqual(breakdown.reference_qtm, 4)
        self.assertFalse(breakdown.forced)

    def test_double_executed_as_quarters_matches_reference(self) -> None:
        """
        ``U U`` execution equals a ``U2`` reference in QTM (no forcing).

        A Bluetooth cube emits a double as two quarter turns; QTM counts both
        forms identically, so no double-merge is needed.
        """
        solve = make_solve(int(2.0 * SECOND), moves='R U U R F')
        breakdown = self.rater.rate_with_details(
            solve, 'oll', parse_moves('R U2 R F'),
        )
        self.assertEqual(breakdown.executed_qtm, 5)
        self.assertEqual(breakdown.reference_qtm, 5)
        self.assertFalse(breakdown.forced)

    def test_empty_reference_disables_forcing(self) -> None:
        """With no reference solution the forcing override is skipped."""
        # Long and fast: would force against any real reference.
        solve = make_bt_solve(htm=30, elapsed_s=1.0)
        breakdown = self.rater.rate_with_details(solve, 'pll', Algorithm())
        self.assertEqual(breakdown.reference_qtm, 0)
        self.assertFalse(breakdown.forced)

    def test_tps_keeps_unmerged_move_count(self) -> None:
        """TPS still reflects physical quarter turns (hand speed)."""
        solve = make_solve(int(2.0 * SECOND), moves='R U U R F')
        breakdown = self.rater.rate_with_details(
            solve, 'oll', parse_moves('R U2 R F'),
        )
        self.assertEqual(breakdown.tps, 5 / 2.0)


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
        self.assertEqual(
            self.rater.rate(solve, 'pll', LONG_REFERENCE), Rating.Again,
        )
        # With high stability and clean execution: floored to Hard.
        self.assertEqual(
            self.rater.rate(
                solve, 'pll', LONG_REFERENCE,
                stability=HIGH_STABILITY_FLOOR_DAYS,
            ),
            Rating.Hard,
        )

    def test_slow_clean_low_stability_stays_again(self) -> None:
        """TPS-only Again on a low-stability card is not floored."""
        solve = make_bt_solve(htm=self.SLOW_HTM, elapsed_s=self.SLOW_S)
        self.assertEqual(
            self.rater.rate(
                solve, 'pll', LONG_REFERENCE,
                stability=HIGH_STABILITY_FLOOR_DAYS - 1.0,
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
                    solve, 'pll', LONG_REFERENCE,
                    stability=HIGH_STABILITY_FLOOR_DAYS,
                ),
                Rating.Again,
            )

    def test_forcing_high_stability_stays_again(self) -> None:
        """Forcing is categorical: the floor does not apply at high stab."""
        # A fast solve that would be Easy by score but longer than reference.
        solve = make_bt_solve(htm=12, elapsed_s=1.0)
        self.assertEqual(
            self.rater.rate(
                solve, 'pll', make_reference(10),
                stability=HIGH_STABILITY_FLOOR_DAYS,
            ),
            Rating.Again,
        )
