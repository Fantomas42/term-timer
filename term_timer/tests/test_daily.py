"""Tests for the daily scramble command."""
import unittest
from argparse import Namespace

from term_timer.arguments import get_parser
from term_timer.scripts.commands import daily as daily_mod
from term_timer.tests.test_ghost import make_solve


class TestSelectGhost(unittest.TestCase):
    """Tests for ghost selection over the day's solves."""

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a daily command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['daily', *args])

    def test_empty_history_has_no_ghost(self) -> None:
        """The first attempt of the day races nothing."""
        options = self.parse()
        self.assertIsNone(daily_mod.select_ghost([], options))

    def test_pb_of_the_day_is_selected(self) -> None:
        """The fastest analysable solve of the day wins."""
        options = self.parse()
        faster = make_solve(date=2, time=1_000_000_000)
        slower = make_solve(date=3, time=9_000_000_000)

        ghost_solve = daily_mod.select_ghost([slower, faster], options)

        self.assertIs(ghost_solve, faster)

    def test_ghost_follows_the_command_method(self) -> None:
        """The elected ghost is analysed with the command's method."""
        options = self.parse('-m', 'lbl')
        solve = make_solve()

        ghost_solve = daily_mod.select_ghost([solve], options)

        self.assertIsNotNone(ghost_solve)
        self.assertEqual(solve.method_name, 'lbl')

    def test_dnf_never_becomes_the_ghost(self) -> None:
        """A DNF attempt is out of the pool even if faster."""
        options = self.parse()
        slower = make_solve(date=1, time=2_608_404_439)
        dnf = make_solve(date=2, time=1, flag='DNF')

        ghost_solve = daily_mod.select_ghost([dnf, slower], options)

        self.assertIs(ghost_solve, slower)

    def test_unanalysable_history_has_no_ghost(self) -> None:
        """A day made of solves without reconstruction races nothing."""
        options = self.parse()
        manual = make_solve(moves=None)

        self.assertIsNone(daily_mod.select_ghost([manual], options))


class TestRefreshGhost(unittest.TestCase):
    """Tests for the in-session ghost re-election."""

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a daily command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['daily', *args])

    @staticmethod
    def build_instance(
            ghost_solve: object,
            done: list[object],
    ) -> Namespace:
        """
        Build a timer stand-in carrying a ghost and finished solves.

        Returns:
            The stand-in instance.

        """
        return Namespace(ghost=ghost_solve, stack_done=done)

    def test_first_attempt_becomes_the_ghost(self) -> None:
        """A day starting without a ghost gains one after a solve."""
        options = self.parse()
        attempt = make_solve()
        instance = self.build_instance(None, [attempt])

        daily_mod.refresh_ghost(instance, [], options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, attempt)

    def test_new_best_becomes_the_ghost(self) -> None:
        """Beating the ghost promotes the fresh attempt for the next race."""
        options = self.parse()
        stored = make_solve(date=1, time=2_608_404_439)
        faster = make_solve(date=2, time=1_000_000_000)
        instance = self.build_instance(stored, [faster])

        daily_mod.refresh_ghost(instance, [stored], options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, faster)

    def test_slower_attempt_keeps_the_ghost(self) -> None:
        """A slower attempt leaves the target untouched."""
        options = self.parse()
        stored = make_solve(date=1, time=2_608_404_439)
        slower = make_solve(date=2, time=9_000_000_000)
        instance = self.build_instance(stored, [slower])

        daily_mod.refresh_ghost(instance, [stored], options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, stored)


class TestDailyHeader(unittest.TestCase):
    """Tests for the daily header line."""

    def test_header_without_ghost(self) -> None:
        """Without a ghost the header only names the day."""
        header = daily_mod.daily_header('2026-07-26', None)

        self.assertEqual(
            header,
            '[routine]📅 Daily Scramble - 2026-07-26[/routine]',
        )

    def test_header_carries_the_time_to_beat(self) -> None:
        """With a ghost the header shows the time to beat."""
        header = daily_mod.daily_header('2026-07-26', make_solve())

        self.assertIn('2.60', header)
