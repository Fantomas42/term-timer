"""Tests for the routine command."""
import json
import unittest
from argparse import Namespace
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from typing import Any
from typing import ClassVar
from unittest import mock

from cubing_algs.exceptions import InvalidCubeStateError
from cubing_algs.exceptions import InvalidMoveError
from rich.console import Console

from term_timer.config import CubeDevice
from term_timer.exceptions import InvalidAlgorithmError
from term_timer.exceptions import InvalidCaseError
from term_timer.in_out import save_solves
from term_timer.in_out import scramble_to_key
from term_timer.routine import SessionConfig
from term_timer.routine import display_flag
from term_timer.routine import race_options
from term_timer.scrambler import scrambler
from term_timer.scripts.commands import daily as daily_mod
from term_timer.scripts.commands import ghost as ghost_mod
from term_timer.scripts.commands import routine as routine_mod
from term_timer.scripts.commands.routine import build_daily_instance
from term_timer.scripts.commands.routine import build_ghost_instance
from term_timer.scripts.commands.routine import list_routines
from term_timer.scripts.commands.routine import resolve_routine_cube
from term_timer.scripts.commands.routine import resolve_routine_gyroscope
from term_timer.scripts.commands.routine import routine
from term_timer.scripts.commands.routine import run_routine_sessions
from term_timer.solve import Solve
from term_timer.timer import Timer

SHORT_SCRAMBLE = "L2 D' L' F' L'"
SHORT_MOVES = 'L@0 F@507 L@1019 D@1768 L@2518 L@2608'
DAY = '2026-08-09'
LOOP_CAP = 20

CUBES: dict[str, CubeDevice] = {
    'weilong': CubeDevice(
        label='weilong',
        address='11:22:33:44:55:77',
        use_gyroscope=False,
    ),
    'gan12': CubeDevice(
        label='gan12',
        name='GAN 12',
        address='AA:BB:CC:DD:EE:FF',
    ),
}


class RoutineInterfaceDouble:
    """A solving interface recording the Bluetooth calls it receives."""

    def __init__(self, session_config: SessionConfig) -> None:
        """
        Build a double for the session it was asked to run.

        Args:
            session_config: The session the routine builds it from.

        """
        self.session_config = session_config
        self.bluetooth_interface: object | None = None
        self.gyroscope: bool | None = None
        self.cube: CubeDevice | None = None
        self.received: RoutineInterfaceDouble | None = None
        self.disconnections = 0

    async def bluetooth_connect(
            self,
            device: CubeDevice | None = None,
            *,
            use_gyroscope: bool | None = None,
    ) -> None:
        """Open a connection, as the real interface would."""
        self.gyroscope = use_gyroscope
        self.cube = device
        self.bluetooth_interface = object()

    async def bluetooth_handoff(
            self,
            target: 'RoutineInterfaceDouble',
    ) -> None:
        """Hand the connection over to the next session."""
        self.received = target
        target.bluetooth_interface = self.bluetooth_interface
        self.bluetooth_interface = None

    async def bluetooth_disconnect(self) -> None:
        """Close the connection the routine opened."""
        self.disconnections += 1


class RoutineBuilderDouble:
    """A session builder handing out doubles, or failing."""

    def __init__(
            self,
            instances: list['RoutineInterfaceDouble'],
            failure: Exception | None = None,
            *,
            refuses: bool = False,
    ) -> None:
        """
        Build a builder, optionally refusing every session.

        Args:
            instances: The doubles built so far, in build order, shared
                by every builder of the same routine.
            failure: The error every build raises, None to succeed.
            refuses: Whether every build returns None instead, the way a
                race step reports a scramble it cannot resolve.

        """
        self.failure = failure
        self.refuses = refuses
        self.instances = instances

    def __call__(
            self,
            session_config: SessionConfig,
    ) -> RoutineInterfaceDouble | None:
        """
        Build the interface driving one session.

        Args:
            session_config: The session to build an interface for.

        Returns:
            The double the routine will drive, or None when the builder
            refuses the session.

        """
        if self.failure is not None:
            raise self.failure

        if self.refuses:
            return None

        instance = RoutineInterfaceDouble(session_config)
        self.instances.append(instance)

        return instance


class RoutineRun:
    """The outcome of a routine, and the doubles it drove."""

    def __init__(self) -> None:
        """Build an empty outcome, filled once the routine returns."""
        self.code = 0
        self.instances: list[RoutineInterfaceDouble] = []
        self.sessions = mock.AsyncMock()
        self.races = mock.AsyncMock()
        self.instance_stats = mock.MagicMock()
        self.console = mock.MagicMock()
        self.wake_lock = mock.MagicMock()

    @property
    def printed(self) -> str:
        """
        Join everything the routine printed.

        Returns:
            The printed text, as a single string.

        """
        return ' '.join(
            str(argument)
            for call in self.console.print.call_args_list
            for argument in call.args
        )


@contextmanager
def routine_doubles(
        failures: dict[str, Exception] | None = None,
        session_failure: Exception | None = None,
        refusals: set[str] | None = None,
) -> Iterator[RoutineRun]:
    """
    Replace what a routine builds and prints with doubles.

    Args:
        failures: The error each session type raises, by type.
        session_failure: The error running a session raises, None to
            let every session run to its end.
        refusals: The session types whose builder returns None.

    Yields:
        The outcome the routine fills in.

    """
    failures = failures or {}
    refusals = refusals or set()
    run = RoutineRun()

    if session_failure is not None:
        run.sessions.side_effect = session_failure
        run.races.side_effect = session_failure
    builders = {
        session_type: RoutineBuilderDouble(
            run.instances,
            failures.get(session_type),
            refuses=session_type in refusals,
        )
        for session_type in ('train', 'solve', 'drill', 'daily', 'ghost')
    }

    with (
            mock.patch('term_timer.config.BLUETOOTH_CUBES', CUBES),
            mock.patch('term_timer.config.BLUETOOTH_DEFAULT', 'weilong'),
            mock.patch(
                'term_timer.scripts.commands.routine.console',
                run.console,
            ),
            mock.patch(
                'term_timer.scripts.commands.routine.run_session',
                run.sessions,
            ),
            mock.patch(
                'term_timer.scripts.commands.routine.race_loop',
                run.races,
            ),
            mock.patch(
                'term_timer.scripts.commands.routine.show_instance_stats',
                run.instance_stats,
            ),
            mock.patch(
                'term_timer.scripts.commands.routine.keep_awake',
                run.wake_lock,
            ),
            mock.patch.dict(
                'term_timer.scripts.commands.routine.SESSION_BUILDERS',
                builders,
            ),
    ):
        yield run


class TestResolveRoutineCube(unittest.TestCase):
    """Tests for the cube a routine file asks for."""

    def test_missing_key_runs_without_a_cube(self) -> None:
        """A routine saying nothing about Bluetooth connects to nothing."""
        self.assertIsNone(resolve_routine_cube(None))

    def test_false_runs_without_a_cube(self) -> None:
        """A routine refusing Bluetooth connects to nothing."""
        self.assertIsNone(resolve_routine_cube(selector=False))

    def test_true_takes_the_configured_cube(self) -> None:
        """A routine asking for Bluetooth takes the designated cube."""
        with (
                mock.patch('term_timer.config.BLUETOOTH_CUBES', CUBES),
                mock.patch('term_timer.config.BLUETOOTH_DEFAULT', 'weilong'),
        ):
            cube = resolve_routine_cube(selector=True)

        self.assertIsNotNone(cube)
        self.assertEqual(cube.label, 'weilong')  # type: ignore[union-attr]

    def test_label_pins_the_cube_the_routine_names(self) -> None:
        """A routine naming a cube connects to that one, not the default."""
        with (
                mock.patch('term_timer.config.BLUETOOTH_CUBES', CUBES),
                mock.patch('term_timer.config.BLUETOOTH_DEFAULT', 'weilong'),
        ):
            cube = resolve_routine_cube('gan12')

        self.assertIsNotNone(cube)
        self.assertEqual(cube.label, 'gan12')  # type: ignore[union-attr]

    def test_unknown_label_warns_and_runs_without_a_cube(self) -> None:
        """A routine naming no known cube is reported, and runs on."""
        with (
                mock.patch('term_timer.config.BLUETOOTH_CUBES', CUBES),
                mock.patch(
                    'term_timer.scripts.commands.routine.console',
                ) as printer,
        ):
            cube = resolve_routine_cube('unknown')

        self.assertIsNone(cube)
        self.assertIn('unknown', printer.print.call_args.args[0])


class TestResolveRoutineGyroscope(unittest.TestCase):
    """Tests for the gyroscope setting a routine file asks for."""

    def test_missing_key_leaves_the_choice_to_the_cube(self) -> None:
        """A routine saying nothing lets the cube keep its own setting."""
        self.assertIsNone(resolve_routine_gyroscope(None))

    def test_true_forces_the_gyroscope_on(self) -> None:
        """A routine asking for the gyroscope overrides the cube."""
        self.assertTrue(resolve_routine_gyroscope(selector=True))

    def test_false_forces_the_gyroscope_off(self) -> None:
        """A routine refusing the gyroscope overrides the cube."""
        resolved = resolve_routine_gyroscope(selector=False)

        self.assertIsNotNone(resolved)
        self.assertFalse(resolved)


class TestDisplayFlag(unittest.TestCase):
    """Tests for the display toggles a routine step resolves."""

    def test_the_step_wins_over_the_configuration(self) -> None:
        """A step saying what it wants to see is obeyed."""
        session: SessionConfig = {'show_doctor': True}

        self.assertTrue(
            display_flag(session, 'show_doctor', 'doctor', {'doctor': False}),
        )

    def test_a_silent_step_falls_back_on_the_configuration(self) -> None:
        """A step saying nothing is displayed the configured way."""
        self.assertFalse(
            display_flag({}, 'show_doctor', 'doctor', {'doctor': False}),
        )

    def test_an_unconfigured_toggle_is_on(self) -> None:
        """A toggle nothing names anywhere is displayed."""
        self.assertTrue(display_flag({}, 'show_doctor', 'doctor', {}))

    def test_steps_falls_back_on_the_timer_section(self) -> None:
        """A step saying nothing about steps follows the timer config."""
        with mock.patch(
                'term_timer.routine.TIMER_CONFIG', {'steps': True},
        ):
            options = race_options({})

        self.assertTrue(options.show_steps)

    def test_steps_follows_a_timer_section_refusing_them(self) -> None:
        """A configuration hiding the steps hides them in a routine too."""
        with mock.patch(
                'term_timer.routine.TIMER_CONFIG', {'steps': False},
        ):
            options = race_options({})

        self.assertFalse(options.show_steps)


class TestListRoutines(unittest.TestCase):
    """Tests for the listing of the available routine files."""

    def test_empty_directory_reports_nothing_found(self) -> None:
        """A routines directory holding nothing is reported as such."""
        with TemporaryDirectory() as directory, mock.patch(
                'term_timer.scripts.commands.routine.ROUTINES_DIRECTORY',
                Path(directory),
        ), mock.patch(
            'term_timer.scripts.commands.routine.console',
        ) as printer:
            code = list_routines()

        self.assertEqual(code, 0)
        self.assertIn('No routines found', printer.print.call_args.args[0])

    def test_unreadable_file_is_skipped(self) -> None:
        """A routine file no parser accepts is left out of the table."""
        with TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'broken.json').write_text('{', encoding='utf-8')
            (path / 'daily.json').write_text(
                json.dumps(
                    {
                        'comment': 'Warm up',
                        'bluetooth': True,
                        'sessions': [{'type': 'solve', 'count': 2}],
                    },
                ),
                encoding='utf-8',
            )

            with mock.patch(
                    'term_timer.scripts.commands.routine.ROUTINES_DIRECTORY',
                    path,
            ), mock.patch(
                'term_timer.scripts.commands.routine.console',
            ) as printer:
                code = list_routines()

        self.assertEqual(code, 0)

        recorder = Console(width=200)
        with recorder.capture() as capture:
            recorder.print(printer.print.call_args.args[0])
        rendered = capture.get()

        self.assertIn('daily', rendered)
        self.assertIn('Warm up', rendered)
        self.assertNotIn('broken', rendered)


class RoutineTestCase(unittest.IsolatedAsyncioTestCase):
    """Base of the routine tests, running a routine file on doubles."""

    SOLVE_SESSION: ClassVar[dict[str, Any]] = {'type': 'solve', 'count': 1}

    @staticmethod
    async def run_routine(
            config: dict[str, Any],
            *,
            failures: dict[str, Exception] | None = None,
            session_failure: Exception | None = None,
            refusals: set[str] | None = None,
    ) -> RoutineRun:
        """
        Run a routine file written to a temporary directory.

        Args:
            config: Contents of the routine file to run.
            failures: The error each session type raises, by type.
            session_failure: The error running a session raises.
            refusals: The session types whose builder returns None.

        Returns:
            The outcome of the routine, and the doubles it drove.

        """
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / 'testing.json'
            config_path.write_text(json.dumps(config), encoding='utf-8')

            with routine_doubles(failures, session_failure, refusals) as run:
                run.code = await routine(
                    Namespace(routine_file=str(config_path)),
                )

        return run


class TestRoutine(RoutineTestCase):
    """Tests for the sessions a routine file chains."""

    async def test_missing_file_reports_a_failure(self) -> None:
        """A routine file that is nowhere stops on an error."""
        with routine_doubles() as run:
            code = await routine(
                Namespace(routine_file='/nowhere/missing.json'),
            )

        self.assertEqual(code, 1)
        self.assertIn('Routine not found', run.printed)

    async def test_unreadable_file_reports_a_failure(self) -> None:
        """A routine file no JSON can be read from stops on an error."""
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / 'broken.json'
            config_path.write_text('{ not json', encoding='utf-8')

            with routine_doubles() as run:
                run.code = await routine(
                    Namespace(routine_file=str(config_path)),
                )

        self.assertEqual(run.code, 1)
        self.assertIn('Unreadable routine', run.printed)
        self.assertEqual(len(run.instances), 0)

    async def test_bare_name_is_looked_up_in_the_directory(self) -> None:
        """A routine named without an extension comes from the directory."""
        with TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'daily.json').write_text(
                json.dumps({'sessions': [self.SOLVE_SESSION]}),
                encoding='utf-8',
            )

            with routine_doubles() as run, mock.patch(
                    'term_timer.scripts.commands.routine.ROUTINES_DIRECTORY',
                    path,
            ):
                run.code = await routine(Namespace(routine_file='daily'))

        self.assertEqual(run.code, 0)
        self.assertEqual(len(run.instances), 1)

    async def test_no_file_lists_the_routines(self) -> None:
        """A routine command given no file lists what is available."""
        with TemporaryDirectory() as directory, routine_doubles() as run, (
            mock.patch(
                'term_timer.scripts.commands.routine.ROUTINES_DIRECTORY',
                Path(directory),
            )
        ):
            run.code = await routine(Namespace(routine_file=''))

        self.assertEqual(run.code, 0)
        self.assertIn('No routines found', run.printed)

    async def test_empty_sessions_stops_on_a_success(self) -> None:
        """A routine defining no session is reported, without failing."""
        run = await self.run_routine({'sessions': []})

        self.assertEqual(run.code, 0)
        self.assertIn('No sessions defined', run.printed)

    async def test_every_session_type_is_built_and_run(self) -> None:
        """Each session of a routine is built and run in order."""
        run = await self.run_routine(
            {
                'sessions': [
                    {'type': 'train', 'step': 'oll', 'count': 2},
                    {'type': 'solve', 'count': 3, 'show_stats': True},
                    {'type': 'drill', 'algorithm': "R U R'", 'count': 4},
                    {'type': 'daily', 'count': 5},
                    {'type': 'ghost', 'reference': 'abcd', 'count': 6},
                ],
            },
        )

        self.assertEqual(run.code, 0)
        self.assertEqual(
            [instance.session_config.get('type') for instance in run.instances],
            ['train', 'solve', 'drill', 'daily', 'ghost'],
        )
        self.assertEqual(
            [call.args[1] for call in run.sessions.call_args_list],
            [2, 3, 4],
        )
        self.assertEqual(
            [call.args[1] for call in run.races.call_args_list],
            [5, 6],
        )
        self.assertEqual(
            [
                call.kwargs['show_stats']
                for call in run.sessions.call_args_list
            ],
            [False, True, False],
        )
        self.assertIn('Routine complete', run.printed)

    async def test_race_sessions_keep_out_of_the_regular_loop(self) -> None:
        """A solve step never goes through the race loop, and back."""
        run = await self.run_routine(
            {
                'sessions': [
                    self.SOLVE_SESSION,
                    {'type': 'daily', 'count': 2},
                ],
            },
        )

        self.assertEqual(run.code, 0)
        self.assertEqual(run.sessions.await_count, 1)
        self.assertEqual(run.races.await_count, 1)

    async def test_race_session_stats_close_the_step(self) -> None:
        """A race step asking for stats prints the summary of its own."""
        run = await self.run_routine(
            {
                'sessions': [
                    {'type': 'daily', 'count': 2, 'show_stats': True},
                    {'type': 'ghost', 'reference': 'abcd', 'count': 2},
                ],
            },
        )

        self.assertEqual(run.code, 0)
        run.instance_stats.assert_called_once_with(run.instances[0])

    async def test_the_cube_is_handed_over_between_race_sessions(self) -> None:
        """One connection is opened, and passed from a race to the next."""
        run = await self.run_routine(
            {
                'bluetooth': True,
                'sessions': [
                    {'type': 'daily', 'count': 1},
                    {'type': 'ghost', 'reference': 'abcd', 'count': 1},
                ],
            },
        )

        first, second = run.instances

        self.assertEqual(run.code, 0)
        self.assertEqual(first.cube, CUBES['weilong'])
        self.assertIsNone(second.cube)
        self.assertEqual(first.received, second)
        self.assertEqual(second.disconnections, 1)

    async def test_the_routine_holds_a_wake_lock(self) -> None:
        """The whole routine keeps the screen awake, released at the end."""
        run = await self.run_routine({'sessions': [self.SOLVE_SESSION]})

        self.assertEqual(run.code, 0)
        run.wake_lock.assert_called_once_with()
        self.assertEqual(run.wake_lock.return_value.__exit__.call_count, 1)

    async def test_without_bluetooth_nothing_is_connected(self) -> None:
        """A routine refusing Bluetooth builds sessions holding no cube."""
        run = await self.run_routine({'sessions': [self.SOLVE_SESSION]})

        self.assertEqual(run.code, 0)
        self.assertIsNone(run.instances[0].cube)
        self.assertIsNone(run.instances[0].bluetooth_interface)
        self.assertEqual(run.instances[0].disconnections, 0)

    async def test_the_cube_is_connected_once_and_handed_over(self) -> None:
        """One connection is opened, passed along, and closed at the end."""
        run = await self.run_routine(
            {
                'bluetooth': True,
                'sessions': [
                    self.SOLVE_SESSION,
                    {'type': 'train', 'step': 'oll', 'count': 1},
                    {'type': 'drill', 'algorithm': "R U R'", 'count': 1},
                ],
            },
        )

        first, second, third = run.instances

        self.assertEqual(run.code, 0)
        self.assertEqual(first.cube, CUBES['weilong'])
        self.assertIsNone(second.cube)
        self.assertIsNone(third.cube)

        self.assertEqual(first.received, second)
        self.assertEqual(second.received, third)

        self.assertEqual(first.disconnections, 0)
        self.assertEqual(second.disconnections, 0)
        self.assertEqual(third.disconnections, 1)

    async def test_the_routine_pins_the_cube_it_names(self) -> None:
        """A routine naming a cube connects to that one."""
        run = await self.run_routine(
            {
                'bluetooth': 'gan12',
                'sessions': [self.SOLVE_SESSION],
            },
        )

        self.assertEqual(run.code, 0)
        self.assertEqual(run.instances[0].cube, CUBES['gan12'])

    async def test_missing_gyroscope_leaves_the_choice_to_the_cube(
            self,
    ) -> None:
        """A routine saying nothing connects on the cube's own setting."""
        run = await self.run_routine(
            {'bluetooth': True, 'sessions': [self.SOLVE_SESSION]},
        )

        self.assertIsNone(run.instances[0].gyroscope)

    async def test_gyroscope_true_forces_it_on(self) -> None:
        """A routine asking for the gyroscope connects with it enabled."""
        run = await self.run_routine(
            {
                'bluetooth': True,
                'use_gyroscope': True,
                'sessions': [self.SOLVE_SESSION],
            },
        )

        self.assertTrue(run.instances[0].gyroscope)

    async def test_gyroscope_false_forces_it_off(self) -> None:
        """A routine refusing the gyroscope connects with it disabled."""
        run = await self.run_routine(
            {
                'bluetooth': True,
                'use_gyroscope': False,
                'sessions': [self.SOLVE_SESSION],
            },
        )

        self.assertIsNotNone(run.instances[0].gyroscope)
        self.assertFalse(run.instances[0].gyroscope)


class TestRoutineFailures(RoutineTestCase):
    """Tests for what a routine does of the errors it meets."""

    async def test_unknown_session_type_reports_a_failure(self) -> None:
        """A session type nothing can build stops the routine."""
        run = await self.run_routine(
            {'sessions': [{'type': 'meditate', 'count': 1}]},
        )

        self.assertEqual(run.code, 1)
        self.assertIn('Unknown session type: meditate', run.printed)

    async def test_invalid_case_reports_a_failure(self) -> None:
        """A training session naming no known case stops the routine."""
        run = await self.run_routine(
            {'sessions': [{'type': 'train', 'step': 'oll', 'count': 1}]},
            failures={'train': InvalidCaseError('Invalid case: Zz')},
        )

        self.assertEqual(run.code, 1)
        self.assertIn('Invalid case: Zz', run.printed)

    async def test_invalid_move_reports_a_failure(self) -> None:
        """A drill session holding an impossible move stops the routine."""
        run = await self.run_routine(
            {'sessions': [{'type': 'drill', 'algorithm': 'Z', 'count': 1}]},
            failures={'drill': InvalidMoveError('Invalid move: Z')},
        )

        self.assertEqual(run.code, 1)
        self.assertIn('Invalid move: Z', run.printed)

    async def test_invalid_algorithm_reports_a_failure(self) -> None:
        """A drill session holding too short an algorithm stops it."""
        run = await self.run_routine(
            {'sessions': [{'type': 'drill', 'algorithm': 'R', 'count': 1}]},
            failures={
                'drill': InvalidAlgorithmError('Invalid algorithm: R'),
            },
        )

        self.assertEqual(run.code, 1)
        self.assertIn('Invalid algorithm: R', run.printed)

    async def test_invalid_cube_state_reports_a_failure(self) -> None:
        """Any error of the algorithm library stops the routine."""
        run = await self.run_routine(
            {'sessions': [self.SOLVE_SESSION]},
            failures={'solve': InvalidCubeStateError('Invalid state')},
        )

        self.assertEqual(run.code, 1)
        self.assertIn('Invalid state', run.printed)

    async def test_error_while_running_reports_a_failure(self) -> None:
        """An error thrown by a running session stops the routine."""
        run = await self.run_routine(
            {'sessions': [self.SOLVE_SESSION]},
            session_failure=InvalidMoveError('Invalid move: Z'),
        )

        self.assertEqual(run.code, 1)
        self.assertIn('Invalid move: Z', run.printed)
        self.assertNotIn('Routine complete', run.printed)

    async def test_error_while_running_skips_the_next_sessions(self) -> None:
        """A session failing leaves the sessions it precedes unbuilt."""
        run = await self.run_routine(
            {
                'sessions': [
                    self.SOLVE_SESSION,
                    {'type': 'train', 'step': 'oll', 'count': 1},
                ],
            },
            session_failure=InvalidMoveError('Invalid move: Z'),
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(len(run.instances), 1)
        self.assertEqual(run.sessions.await_count, 1)

    async def test_unresolved_race_session_stops_the_routine(self) -> None:
        """A race step whose scramble resolves to nothing stops it."""
        run = await self.run_routine(
            {
                'sessions': [
                    {'type': 'ghost', 'reference': 'dead', 'count': 1},
                    self.SOLVE_SESSION,
                ],
            },
            refusals={'ghost'},
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(len(run.instances), 0)
        self.assertEqual(run.races.await_count, 0)
        self.assertEqual(run.sessions.await_count, 0)
        self.assertNotIn('Routine complete', run.printed)

    async def test_the_cube_is_released_when_a_step_refuses(self) -> None:
        """A routine stopping on an unbuildable step hangs up the cube."""
        run = await self.run_routine(
            {
                'bluetooth': True,
                'sessions': [
                    self.SOLVE_SESSION,
                    {'type': 'ghost', 'reference': 'dead', 'count': 1},
                ],
            },
            refusals={'ghost'},
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(run.instances[0].disconnections, 1)

    async def test_the_cube_is_released_on_a_build_failure(self) -> None:
        """A routine stopping on an error still hangs up the cube."""
        run = await self.run_routine(
            {
                'bluetooth': True,
                'sessions': [
                    self.SOLVE_SESSION,
                    {'type': 'meditate', 'count': 1},
                ],
            },
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(run.instances[0].disconnections, 1)

    async def test_the_cube_is_released_on_a_running_failure(self) -> None:
        """A session failing on the cube still hangs it up."""
        run = await self.run_routine(
            {'bluetooth': True, 'sessions': [self.SOLVE_SESSION]},
            session_failure=InvalidMoveError('Invalid move: Z'),
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(run.instances[0].disconnections, 1)

    async def test_the_wake_lock_is_released_on_a_failure(self) -> None:
        """A routine stopping on an error lets the screen sleep again."""
        run = await self.run_routine(
            {'sessions': [self.SOLVE_SESSION]},
            session_failure=InvalidMoveError('Invalid move: Z'),
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(run.wake_lock.return_value.__exit__.call_count, 1)


def make_solve(
        date: int = 1766883476,
        time: int = 2608404439,
        moves: str | None = SHORT_MOVES,
) -> Solve:
    """
    Build a Solve fixture on the fixture scramble.

    Returns:
        A configured Solve instance.

    """
    solve = Solve(date, time, SHORT_SCRAMBLE, moves=moves)
    solve.method_name = 'cfop'
    solve.orientation = 'auto'
    return solve


class RaceStepTestCase(unittest.IsolatedAsyncioTestCase):
    """Base of the tests running real timers as routine race steps."""

    def setUp(self) -> None:
        """Point the daily and ghost libraries at temporary folders."""
        daily = TemporaryDirectory()
        self.addCleanup(daily.cleanup)
        self.daily_directory = Path(daily.name)

        ghosts = TemporaryDirectory()
        self.addCleanup(ghosts.cleanup)
        self.ghosts_directory = Path(ghosts.name)

        for module, attribute, directory in (
                (daily_mod, 'DAILY_DIRECTORY', self.daily_directory),
                (ghost_mod, 'GHOSTS_DIRECTORY', self.ghosts_directory),
        ):
            patcher = mock.patch.object(module, attribute, directory)
            patcher.start()
            self.addCleanup(patcher.stop)

        pool = mock.patch.object(
            routine_mod, 'load_all_solves', return_value=[],
        )
        pool.start()
        self.addCleanup(pool.stop)

        self.printer = mock.MagicMock()
        for module in (routine_mod, daily_mod, ghost_mod):
            printer = mock.patch.object(module, 'console', self.printer)
            printer.start()
            self.addCleanup(printer.stop)

    @property
    def printed(self) -> str:
        """
        Join everything the routine printed.

        Returns:
            The printed text, as a single string.

        """
        return ' '.join(
            str(argument)
            for call in self.printer.print.call_args_list
            for argument in call.args
        )

    def seed_ghost(self, *, analysable: bool = True) -> str:
        """
        Store a raced scramble in the ghost library.

        Args:
            analysable: Whether the seeding attempt carries the
                reconstruction a race needs.

        Returns:
            The scramble key naming the stored file.

        """
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(
            3,
            key,
            [make_solve(moves=SHORT_MOVES if analysable else None)],
            directory=self.ghosts_directory,
        )
        return key


class TestRoutineRaceBuilders(RaceStepTestCase):
    """Tests for the timers a daily and a ghost step build."""

    def test_daily_step_runs_the_scramble_of_the_named_date(self) -> None:
        """A step naming a date races the scramble of that day."""
        expected, _ = scrambler(3, 0, rng=Random(DAY))  # noqa: S311

        instance = build_daily_instance({'type': 'daily', 'date': DAY})

        self.assertIsNotNone(instance)
        self.assertEqual(instance.raw_scramble, str(expected))  # type: ignore[union-attr]
        self.assertEqual(instance.session, DAY)  # type: ignore[union-attr]
        self.assertIn(DAY, self.printed)

    def test_daily_step_without_a_date_runs_the_scramble_of_today(
            self,
    ) -> None:
        """A step saying nothing about a date races the day's scramble."""
        today = date.today().strftime('%Y-%m-%d')  # noqa: DTZ011
        expected, _ = scrambler(3, 0, rng=Random(today))  # noqa: S311

        instance = build_daily_instance({'type': 'daily'})

        self.assertIsNotNone(instance)
        self.assertEqual(instance.raw_scramble, str(expected))  # type: ignore[union-attr]
        self.assertEqual(instance.session, today)  # type: ignore[union-attr]

    def test_daily_step_writes_into_the_daily_library(self) -> None:
        """A daily step saves its attempts away from the regular solves."""
        instance = build_daily_instance({'type': 'daily', 'date': DAY})

        self.assertIsNotNone(instance)
        self.assertEqual(instance.save_directory, self.daily_directory)  # type: ignore[union-attr]

    def test_daily_step_seeds_the_stack_with_the_day(self) -> None:
        """A daily step already played opens on the attempts of the day."""
        save_solves(
            3, DAY, [make_solve()], directory=self.daily_directory,
        )

        instance = build_daily_instance({'type': 'daily', 'date': DAY})

        self.assertIsNotNone(instance)
        self.assertEqual(len(instance.stack), 1)  # type: ignore[union-attr]
        self.assertIsNotNone(instance.ghost)  # type: ignore[union-attr]

    def test_ghost_step_races_the_scramble_its_key_names(self) -> None:
        """A step naming a scramble key races that very scramble."""
        key = self.seed_ghost()

        instance = build_ghost_instance(
            {'type': 'ghost', 'reference': key[:8]},
        )

        self.assertIsNotNone(instance)
        self.assertEqual(instance.raw_scramble, SHORT_SCRAMBLE)  # type: ignore[union-attr]
        self.assertEqual(instance.session, key)  # type: ignore[union-attr]
        self.assertEqual(instance.save_directory, self.ghosts_directory)  # type: ignore[union-attr]

    def test_ghost_step_seeds_the_stack_with_the_reference(self) -> None:
        """The reference joins the race as its first attempt."""
        key = self.seed_ghost()

        instance = build_ghost_instance(
            {'type': 'ghost', 'reference': key[:8]},
        )

        self.assertIsNotNone(instance)
        self.assertEqual(len(instance.stack), 1)  # type: ignore[union-attr]
        self.assertIsNotNone(instance.ghost)  # type: ignore[union-attr]

    def test_ghost_step_refuses_an_unknown_key(self) -> None:
        """A step naming no stored scramble is reported, and refused."""
        instance = build_ghost_instance(
            {'type': 'ghost', 'reference': 'deadbeef'},
        )

        self.assertIsNone(instance)
        self.assertIn('Invalid scramble key deadbeef', self.printed)

    def test_ghost_step_refuses_a_key_too_short(self) -> None:
        """A step naming too short a prefix is reported, and refused."""
        self.seed_ghost()

        instance = build_ghost_instance({'type': 'ghost', 'reference': 'ab'})

        self.assertIsNone(instance)
        self.assertIn('at least', self.printed)

    def test_ghost_step_refuses_a_reference_with_nothing_to_race(
            self,
    ) -> None:
        """A reference carrying no reconstruction is reported, and refused."""
        key = self.seed_ghost(analysable=False)

        instance = build_ghost_instance(
            {'type': 'ghost', 'reference': key[:8]},
        )

        self.assertIsNone(instance)
        self.assertIn('no reconstruction', self.printed)


class TestRoutineRaceSteps(RaceStepTestCase):
    """Tests for the loop a routine runs its race steps on."""

    async def run_sessions(
            self,
            sessions: list[SessionConfig],
            *,
            cube: CubeDevice | None = None,
            quit_on: int = 0,
    ) -> tuple[int, int, list[int]]:
        """
        Run race steps on real timers whose attempts are stubbed.

        Every attempt reports as completed, until the ``quit_on``-th one
        which reports the solver leaving, zero never leaving. The loop
        is capped either way, so a count that never lands fails on the
        call count instead of hanging.

        Args:
            sessions: The steps the routine chains.
            cube: The cube the routine connects to, if any.
            quit_on: The attempt the solver leaves on.

        Returns:
            The exit code, the count of the attempts run and the size of
            the stack at each ghost election.

        """
        calls = 0

        def landed() -> bool:
            nonlocal calls
            calls += 1
            if quit_on and calls >= quit_on:
                return False
            return calls < LOOP_CAP

        elections: list[int] = []
        elect = Timer.elect_ghost

        def spy(instance: Timer) -> None:
            elections.append(len(instance.stack))
            elect(instance)

        with (
                mock.patch.object(
                    Timer, 'start', mock.AsyncMock(side_effect=landed),
                ),
                mock.patch.object(
                    Timer, 'elect_ghost', autospec=True, side_effect=spy,
                ),
                mock.patch.object(
                    Timer, 'bluetooth_connect', autospec=True,
                    side_effect=self.connect,
                ),
                mock.patch.object(
                    Timer, 'bluetooth_handoff', autospec=True,
                    side_effect=self.handoff,
                ),
                mock.patch.object(
                    Timer, 'bluetooth_disconnect', autospec=True,
                ) as disconnect,
                mock.patch.object(routine_mod, 'keep_awake', mock.MagicMock()),
        ):
            self.connections = 0
            self.disconnections = disconnect
            code = await run_routine_sessions(
                sessions, cube, use_gyroscope=None,
            )

        return code, calls, elections

    async def connect(
            self,
            instance: Timer,
            device: CubeDevice | None = None,
            *,
            use_gyroscope: bool | None = None,
    ) -> None:
        """Open a connection, as the real interface would."""
        self.connections += 1
        self.connected_cube = device
        self.gyroscope = use_gyroscope
        instance.bluetooth_interface = mock.MagicMock()

    @staticmethod
    async def handoff(instance: Timer, target: Timer) -> None:
        """Hand the connection over to the next step."""
        target.bluetooth_interface = instance.bluetooth_interface
        instance.bluetooth_interface = None

    async def test_count_bounds_a_daily_step(self) -> None:
        """A count stops a daily step even while attempts keep landing."""
        code, calls, _elections = await self.run_sessions(
            [{'type': 'daily', 'date': DAY, 'count': 3}],
        )

        self.assertEqual(code, 0)
        self.assertEqual(calls, 3)

    async def test_count_bounds_a_ghost_step(self) -> None:
        """A count stops a ghost step even while attempts keep landing."""
        key = self.seed_ghost()

        code, calls, _elections = await self.run_sessions(
            [{'type': 'ghost', 'reference': key[:8], 'count': 3}],
        )

        self.assertEqual(code, 0)
        self.assertEqual(calls, 3)

    async def test_no_count_runs_until_the_solver_quits(self) -> None:
        """A race step without a count runs on until an attempt is left."""
        code, calls, _elections = await self.run_sessions(
            [{'type': 'daily', 'date': DAY}],
            quit_on=4,
        )

        self.assertEqual(code, 0)
        self.assertEqual(calls, 4)

    async def test_the_ghost_is_re_elected_after_every_attempt(self) -> None:
        """A race step moves its target as soon as it is beaten."""
        _code, _calls, elections = await self.run_sessions(
            [{'type': 'daily', 'date': DAY, 'count': 3}],
        )

        self.assertEqual(len(elections), 4)

    async def test_a_solve_step_never_elects_a_ghost(self) -> None:
        """A regular solving step races nothing, and elects nothing."""
        _code, _calls, elections = await self.run_sessions(
            [{'type': 'solve', 'count': 2, 'free_play': True}],
        )

        self.assertEqual(elections, [])

    async def test_the_cube_is_connected_once_across_race_steps(self) -> None:
        """A routine chaining races opens a single connection."""
        key = self.seed_ghost()

        code, _calls, _elections = await self.run_sessions(
            [
                {'type': 'daily', 'date': DAY, 'count': 1},
                {'type': 'ghost', 'reference': key[:8], 'count': 1},
            ],
            cube=CUBES['weilong'],
        )

        self.assertEqual(code, 0)
        self.assertEqual(self.connections, 1)
        self.assertEqual(self.disconnections.await_count, 1)

    async def test_an_unresolved_step_stops_the_routine(self) -> None:
        """A ghost step naming no stored scramble stops the routine."""
        code, calls, _elections = await self.run_sessions(
            [
                {'type': 'ghost', 'reference': 'deadbeef', 'count': 1},
                {'type': 'daily', 'date': DAY, 'count': 1},
            ],
        )

        self.assertEqual(code, 1)
        self.assertEqual(calls, 0)
        self.assertNotIn('Routine complete', self.printed)
