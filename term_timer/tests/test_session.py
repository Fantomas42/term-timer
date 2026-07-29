"""Tests for the shared plumbing of the imposed scramble commands."""
import unittest
from argparse import Namespace
from pathlib import Path
from random import Random

from term_timer.arguments import get_parser
from term_timer.scripts.commands.session import build_race_timer
from term_timer.scripts.commands.session import race_header
from term_timer.solve import Solve
from term_timer.tests.test_ghost import SHORT_SCRAMBLE
from term_timer.tests.test_ghost import make_solve
from term_timer.timer import Timer

SAVE_DIRECTORY = Path('/nowhere')


class TestRaceHeader(unittest.TestCase):
    """Tests for the header line of a raced session."""

    def test_header_carries_the_time_to_beat(self) -> None:
        """The elected ghost puts its official time in the header."""
        header = race_header(
            '[daily]📅 Daily Scramble - 2026-07-26[/daily]',
            make_solve(time=2_608_404_439),
        )

        self.assertIn('Daily Scramble - 2026-07-26', header)
        self.assertIn('2.60', header)

    def test_header_without_ghost_omits_the_time(self) -> None:
        """A ghostless session still announces what it runs."""
        header = race_header('[ghost]Ghost Race - Scramble #3[/ghost]', None)

        self.assertEqual(header, '[ghost]Ghost Race - Scramble #3[/ghost]')


class TestBuildRaceTimer(unittest.TestCase):
    """Tests for the timer built by an imposed scramble command."""

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a ghost command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['ghost', '1', *args])

    @staticmethod
    def build(
            options: Namespace,
            stack: list[Solve],
    ) -> Timer | None:
        """
        Build a race timer writing to a directory tests never touch.

        Returns:
            The timer, or None when the replay is unusable.

        """
        return build_race_timer(
            options,
            session='KEY',
            scramble=SHORT_SCRAMBLE,
            stack=stack,
            rng=Random(),  # noqa: S311
            save_directory=SAVE_DIRECTORY,
        )

    def built(self, options: Namespace, stack: list[Solve]) -> Timer:
        """
        Build a race timer the test expects to exist.

        Returns:
            The timer.

        """
        instance = self.build(options, stack)
        if instance is None:
            self.fail('The race timer should have been built')
        return instance

    def test_session_wiring(self) -> None:
        """The timer carries the session, its scramble and its stack."""
        solve = make_solve()

        instance = self.built(self.parse(), [solve])

        self.assertEqual(instance.session, 'KEY')
        self.assertEqual(instance.raw_scramble, SHORT_SCRAMBLE)
        self.assertEqual(instance.stack, [solve])
        self.assertEqual(instance.save_directory, SAVE_DIRECTORY)

    def test_imposed_scramble_leaves_no_generation(self) -> None:
        """The scramble being given, nothing is generated for the session."""
        instance = self.built(self.parse(), [])

        self.assertEqual(instance.iterations, 0)
        self.assertEqual(instance.scrambles, [])

    def test_ghost_is_elected_on_build(self) -> None:
        """The time to beat is known before the first attempt starts."""
        slower = make_solve(date=1, time=9_000_000_000)
        faster = make_solve(date=2, time=1_000_000_000)

        instance = self.built(self.parse(), [slower, faster])

        self.assertIs(instance.ghost, faster)

    def test_empty_stack_builds_a_ghostless_timer(self) -> None:
        """A session with nothing recorded yet races without a target."""
        instance = self.built(self.parse(), [])

        self.assertIsNone(instance.ghost)

    def test_unusable_replay_builds_nothing(self) -> None:
        """A replay that cannot be loaded aborts the session."""
        options = self.parse('--replay', '/nowhere/missing.json')

        self.assertIsNone(self.build(options, [make_solve()]))
