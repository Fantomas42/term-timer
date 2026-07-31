"""Tests for Driller.validate_drill_move()."""
import unittest
from argparse import Namespace
from unittest import mock

from cubing_algs.move import Move

from term_timer.driller import Driller
from term_timer.scripts.commands.driller import driller


def make_driller(algorithm: str, *, duration: int = 0) -> Driller:
    """
    Create a Driller ready to validate moves.

    Uses standard UF orientation and no countdown.

    Returns:
        Driller instance with init_solve and reset_drill_state applied.

    """
    driller = Driller(
        algorithm=algorithm,
        times=1,
        duration=duration,
        orientation='UF',
        countdown=0,
        metronome=0,
    )
    driller.init_solve()
    driller.reset_drill_state()
    return driller


class TestDrillerInit(unittest.TestCase):
    """Validate Driller initialisation with duration."""

    def test_duration_zero_by_default(self) -> None:
        """Duration defaults to 0 (infinite session)."""
        driller = make_driller('U R')
        self.assertEqual(driller.duration, 0)

    def test_duration_stored(self) -> None:
        """Supplied duration is stored on the instance."""
        driller = make_driller('U R', duration=120)
        self.assertEqual(driller.duration, 120)


class TestDrillerCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for the algorithms the drill command refuses."""

    @staticmethod
    def drill_options(algorithm: str) -> Namespace:
        """
        Build the options of a drill run on an algorithm.

        Returns:
            The options the command parses its run from.

        """
        return Namespace(
            algorithm=algorithm,
            times=1,
            duration=0,
            orientation='UF',
            countdown=0,
            metronome=0,
        )

    async def test_invalid_move_reports_a_failure(self) -> None:
        """An algorithm holding an impossible move is reported."""
        with mock.patch(
                'term_timer.scripts.commands.driller.console',
        ) as printer:
            code = await driller(self.drill_options('R Q U'))

        self.assertEqual(code, 1)
        self.assertIn('invalid move', str(printer.print.call_args.args))

    async def test_too_short_algorithm_reports_a_failure(self) -> None:
        """An algorithm too short to be drilled is reported."""
        with mock.patch(
                'term_timer.scripts.commands.driller.console',
        ) as printer:
            code = await driller(self.drill_options('R'))

        self.assertEqual(code, 1)
        self.assertIn('too short', str(printer.print.call_args.args))


class TestValidateSingleMoves(unittest.TestCase):
    """Validate behaviour for single (quarter-turn) moves."""

    def test_clockwise_move_advances_index(self) -> None:
        """Correct CW move advances move_index and leaves no bad move."""
        driller = make_driller('U R')
        driller.validate_drill_move(Move('U'), 100)
        self.assertEqual(driller.move_index, 1)
        self.assertFalse(driller.bad_move)

    def test_counter_clockwise_move_advances_index(self) -> None:
        """Correct CCW move advances move_index and leaves no bad move."""
        driller = make_driller("U' R")
        driller.validate_drill_move(Move("U'"), 100)
        self.assertEqual(driller.move_index, 1)
        self.assertFalse(driller.bad_move)

    def test_clockwise_when_counter_clockwise_expected_is_bad(self) -> None:
        """U when U' expected is a bad move (wrong direction)."""
        driller = make_driller("U' R")
        driller.validate_drill_move(Move('U'), 100)
        self.assertEqual(str(driller.bad_move), 'U')
        self.assertTrue(driller.solve_completed_event.is_set())

    def test_counter_clockwise_when_clockwise_expected_is_bad(self) -> None:
        """U' when U expected is a bad move (wrong direction)."""
        driller = make_driller('U R')
        driller.validate_drill_move(Move("U'"), 100)
        self.assertEqual(str(driller.bad_move), "U'")
        self.assertTrue(driller.solve_completed_event.is_set())

    def test_wrong_base_move_is_bad(self) -> None:
        """R when U expected is a bad move (wrong face)."""
        driller = make_driller('U R')
        driller.validate_drill_move(Move('R'), 100)
        self.assertEqual(str(driller.bad_move), 'R')
        self.assertTrue(driller.solve_completed_event.is_set())


class TestValidateDoubleMoves(unittest.TestCase):
    """Validate behaviour for double (half-turn) moves."""

    def test_double_first_sub_move_does_not_advance(self) -> None:
        """First CW sub-move for U2 does not advance index yet."""
        driller = make_driller('U2')
        driller.validate_drill_move(Move('U'), 100)
        self.assertEqual(driller.move_index, 0)
        self.assertFalse(driller.bad_move)

    def test_double_move_completes_with_clockwise(self) -> None:
        """U U when U2 expected advances index: both CW is valid."""
        driller = make_driller('U2')
        driller.validate_drill_move(Move('U'), 100)
        driller.validate_drill_move(Move('U'), 200)
        self.assertEqual(driller.move_index, 1)
        self.assertFalse(driller.bad_move)

    def test_double_move_completes_with_counter_clockwise(self) -> None:
        """U' U' when U2 expected advances index: both CCW is also valid."""
        driller = make_driller('U2')
        driller.validate_drill_move(Move("U'"), 100)
        driller.validate_drill_move(Move("U'"), 200)
        self.assertEqual(driller.move_index, 1)
        self.assertFalse(driller.bad_move)

    def test_double_move_direction_reversal_is_bad(self) -> None:
        """U then U' when U2 expected is bad: net rotation is zero."""
        driller = make_driller('U2')
        driller.validate_drill_move(Move('U'), 100)
        driller.validate_drill_move(Move("U'"), 200)
        self.assertEqual(str(driller.bad_move), "U'")
        self.assertTrue(driller.solve_completed_event.is_set())

    def test_wrong_base_move_during_double_is_bad(self) -> None:
        """Wrong face during a double-move sequence is bad."""
        driller = make_driller('U2')
        driller.validate_drill_move(Move('R'), 100)
        self.assertEqual(str(driller.bad_move), 'R')
        self.assertTrue(driller.solve_completed_event.is_set())


class TestValidateSequenceCompletion(unittest.TestCase):
    """Validate solve completion signalling."""

    def test_completing_all_moves_sets_end_time(self) -> None:
        """Last move of the sequence sets end_time to that clock value."""
        driller = make_driller('U R')
        driller.validate_drill_move(Move('U'), 100)
        driller.validate_drill_move(Move('R'), 999)
        self.assertEqual(driller.end_time, 999)

    def test_completing_all_moves_sets_solve_completed_event(self) -> None:
        """Last move of the sequence sets solve_completed_event."""
        driller = make_driller('U R')
        driller.validate_drill_move(Move('U'), 100)
        driller.validate_drill_move(Move('R'), 999)
        self.assertTrue(driller.solve_completed_event.is_set())

    def test_completing_double_sets_end_time(self) -> None:
        """Second sub-move of a double-move-only algorithm sets end_time."""
        driller = make_driller('U2')
        driller.validate_drill_move(Move('U'), 100)
        driller.validate_drill_move(Move('U'), 777)
        self.assertEqual(driller.end_time, 777)

    def test_after_bad_move_subsequent_calls_are_ignored(self) -> None:
        """Once bad_move is set, further calls leave move_index unchanged."""
        driller = make_driller('U R')
        driller.validate_drill_move(Move("U'"), 100)   # bad
        driller.validate_drill_move(Move('R'), 200)    # should be no-op
        self.assertEqual(driller.move_index, 0)

    def test_mixed_algorithm_full_sequence(self) -> None:
        """Full sequence U R' U2 completes correctly."""
        driller = make_driller("U R' U2")
        driller.validate_drill_move(Move('U'), 100)
        driller.validate_drill_move(Move("R'"), 200)
        driller.validate_drill_move(Move('U'), 300)    # first half of U2
        self.assertFalse(driller.bad_move)
        driller.validate_drill_move(Move('U'), 400)    # completes U2
        self.assertEqual(driller.move_index, 3)
        self.assertEqual(driller.end_time, 400)
        self.assertFalse(driller.bad_move)
