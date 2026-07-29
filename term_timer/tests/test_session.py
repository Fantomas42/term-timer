"""Tests for the shared plumbing of the solving commands."""
import unittest
from argparse import Namespace
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest import mock

from cubing_algs.exceptions import InvalidMoveError

from term_timer.arguments import get_parser
from term_timer.scripts.commands.session import build_race_timer
from term_timer.scripts.commands.session import race_header
from term_timer.scripts.commands.session import solve_session
from term_timer.solve import Solve
from term_timer.tests.test_ghost import SHORT_SCRAMBLE
from term_timer.tests.test_ghost import make_solve
from term_timer.timer import Timer

if TYPE_CHECKING:
    from term_timer.interface import SolveInterface

SAVE_DIRECTORY = Path('/nowhere')


class SessionInterfaceDouble:
    """A solving interface counting the Bluetooth calls it receives."""

    def __init__(
            self,
            bluetooth_replay: dict[str, Any] | None = None,
            failure: Exception | None = None,
    ) -> None:
        """
        Build a double, optionally failing the attempts it runs.

        Args:
            bluetooth_replay: The replay payload the session drives.
            failure: The error every attempt raises, None to succeed.

        """
        self.bluetooth_replay = bluetooth_replay
        self.failure = failure
        self.bluetooth_interface: object | None = None
        self.connections = 0
        self.disconnections = 0
        self.gyroscope: bool | None = None

    async def start(self) -> bool:
        """
        Run one attempt of the session.

        Returns:
            Whether the attempt was completed.

        """
        if self.failure is not None:
            raise self.failure

        return True

    async def bluetooth_connect(self, *, use_gyroscope: bool) -> None:
        """Open a connection, as the real interface would."""
        self.connections += 1
        self.gyroscope = use_gyroscope
        self.bluetooth_interface = object()

    async def bluetooth_disconnect(self) -> None:
        """Close the connection the session opened."""
        self.disconnections += 1


def session_options(*, bluetooth: bool = False) -> Namespace:
    """
    Build the options a solving command hands to the session.

    Args:
        bluetooth: Whether the command asks for a cube.

    Returns:
        The parsed namespace stand-in.

    """
    return Namespace(bluetooth=bluetooth, use_gyroscope=False)


class TestSolveSession(unittest.IsolatedAsyncioTestCase):
    """Tests for the connection and exit code held around a session."""

    async def test_normal_exit_disconnects_on_zero(self) -> None:
        """A session run to its end reports a success and hangs up."""
        double = SessionInterfaceDouble()

        async with solve_session(
                cast('SolveInterface', double),
                session_options(bluetooth=True),
        ) as outcome:
            await double.start()

        self.assertEqual(outcome.code, 0)
        self.assertEqual(double.connections, 1)
        self.assertEqual(double.disconnections, 1)

    async def test_invalid_move_ends_the_session_on_one(self) -> None:
        """A move the cube cannot make stops the session, printed."""
        double = SessionInterfaceDouble(
            failure=InvalidMoveError('Invalid move: Z'),
        )

        with mock.patch(
                'term_timer.scripts.commands.session.console',
        ) as printer:
            async with solve_session(
                    cast('SolveInterface', double),
                    session_options(bluetooth=True),
            ) as outcome:
                await double.start()

        self.assertEqual(outcome.code, 1)
        self.assertEqual(double.disconnections, 1)
        self.assertIn('Invalid move: Z', printer.print.call_args.args)

    async def test_other_exception_still_disconnects(self) -> None:
        """The cube is released whatever ends the session."""
        double = SessionInterfaceDouble(failure=ValueError('boom'))

        with self.assertRaises(ValueError):
            async with solve_session(
                    cast('SolveInterface', double),
                    session_options(bluetooth=True),
            ):
                await double.start()

        self.assertEqual(double.disconnections, 1)

    async def test_no_cube_asked_connects_nothing(self) -> None:
        """A session run on the keyboard never touches Bluetooth."""
        double = SessionInterfaceDouble()

        async with solve_session(
                cast('SolveInterface', double),
                session_options(),
        ) as outcome:
            await double.start()

        self.assertEqual(outcome.code, 0)
        self.assertEqual(double.connections, 0)
        self.assertEqual(double.disconnections, 0)

    async def test_replay_connects_without_the_flag(self) -> None:
        """A replayed solve file drives the cube interface on its own."""
        double = SessionInterfaceDouble({'solves': []})

        async with solve_session(
                cast('SolveInterface', double),
                session_options(),
        ):
            await double.start()

        self.assertEqual(double.connections, 1)
        self.assertEqual(double.disconnections, 1)

    async def test_gyroscope_option_is_carried(self) -> None:
        """The connection is opened with the orientation the user asked."""
        double = SessionInterfaceDouble()
        options = session_options(bluetooth=True)
        options.use_gyroscope = True

        async with solve_session(cast('SolveInterface', double), options):
            await double.start()

        self.assertTrue(double.gyroscope)


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
