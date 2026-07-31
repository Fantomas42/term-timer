"""Tests for the routine command."""
import json
import unittest
from argparse import Namespace
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from typing import ClassVar
from unittest import mock

from cubing_algs.exceptions import InvalidMoveError
from rich.console import Console

from term_timer.config import CubeDevice
from term_timer.exceptions import InvalidCaseError
from term_timer.routine import SessionConfig
from term_timer.scripts.commands.routine import list_routines
from term_timer.scripts.commands.routine import resolve_routine_cube
from term_timer.scripts.commands.routine import resolve_routine_gyroscope
from term_timer.scripts.commands.routine import routine

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
    ) -> None:
        """
        Build a builder, optionally refusing every session.

        Args:
            instances: The doubles built so far, in build order, shared
                by every builder of the same routine.
            failure: The error every build raises, None to succeed.

        """
        self.failure = failure
        self.instances = instances

    def __call__(
            self,
            session_config: SessionConfig,
    ) -> RoutineInterfaceDouble:
        """
        Build the interface driving one session.

        Args:
            session_config: The session to build an interface for.

        Returns:
            The double the routine will drive.

        """
        if self.failure is not None:
            raise self.failure

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
        self.console = mock.MagicMock()

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
) -> Iterator[RoutineRun]:
    """
    Replace what a routine builds and prints with doubles.

    Args:
        failures: The error each session type raises, by type.

    Yields:
        The outcome the routine fills in.

    """
    failures = failures or {}
    run = RoutineRun()
    builders = {
        session_type: RoutineBuilderDouble(
            run.instances,
            failures.get(session_type),
        )
        for session_type in ('train', 'solve', 'drill')
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


class TestRoutine(unittest.IsolatedAsyncioTestCase):
    """Tests for the sessions a routine file chains."""

    SOLVE_SESSION: ClassVar[dict[str, Any]] = {'type': 'solve', 'count': 1}

    @staticmethod
    async def run_routine(
            config: dict[str, Any],
            *,
            failures: dict[str, Exception] | None = None,
    ) -> RoutineRun:
        """
        Run a routine file written to a temporary directory.

        Args:
            config: Contents of the routine file to run.
            failures: The error each session type raises, by type.

        Returns:
            The outcome of the routine, and the doubles it drove.

        """
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / 'testing.json'
            config_path.write_text(json.dumps(config), encoding='utf-8')

            with routine_doubles(failures) as run:
                run.code = await routine(
                    Namespace(routine_file=str(config_path)),
                )

        return run

    async def test_missing_file_reports_a_failure(self) -> None:
        """A routine file that is nowhere stops on an error."""
        with routine_doubles() as run:
            code = await routine(
                Namespace(routine_file='/nowhere/missing.json'),
            )

        self.assertEqual(code, 1)
        self.assertIn('Routine not found', run.printed)

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

    async def test_every_session_type_is_built_and_run(self) -> None:
        """Each session of a routine is built and run in order."""
        run = await self.run_routine(
            {
                'sessions': [
                    {'type': 'train', 'step': 'oll', 'count': 2},
                    {'type': 'solve', 'count': 3, 'show_stats': True},
                    {'type': 'drill', 'algorithm': "R U R'", 'count': 4},
                ],
            },
        )

        self.assertEqual(run.code, 0)
        self.assertEqual(
            [instance.session_config.get('type') for instance in run.instances],
            ['train', 'solve', 'drill'],
        )
        self.assertEqual(
            [call.args[1] for call in run.sessions.call_args_list],
            [2, 3, 4],
        )
        self.assertEqual(
            [
                call.kwargs['show_stats']
                for call in run.sessions.call_args_list
            ],
            [False, True, False],
        )
        self.assertIn('Routine complete', run.printed)

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

    async def test_the_cube_is_released_on_a_failure(self) -> None:
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
