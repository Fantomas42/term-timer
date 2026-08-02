"""Tests for the bt-info utility script."""
import asyncio
import logging
import threading
import unittest
from argparse import Namespace
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime
from typing import Any
from typing import cast
from unittest.mock import patch

from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.constants import BLUETOOTH_EVENTS
from term_timer.exceptions import CubeNotFoundError
from term_timer.orientation import get_orientation_moves
from term_timer.scripts.bluetooth_info import SessionReport
from term_timer.scripts.bluetooth_info import consumer_cb
from term_timer.scripts.bluetooth_info import linear_regression
from term_timer.scripts.bluetooth_info import run
from term_timer.scripts.bluetooth_info import show_state


def facelets_event(facelets: str) -> EventDict:
    """
    Build a facelets event carrying the given cube state.

    Args:
        facelets: The facelet string the cube announces.

    Returns:
        The event as the drivers publish it.

    """
    event: dict[str, Any] = {
        'event': 'facelets',
        'clock': 0,
        'timestamp': datetime.now(),  # noqa: DTZ005
        'serial': 1,
        'facelets': facelets,
        'state': {'CP': [], 'CO': [], 'EP': [], 'EO': []},
    }
    return cast('EventDict', event)


def driver_event(name: str) -> EventDict:
    """
    Build an event of the given name, carrying every payload field.

    The fields of all the event types are merged into one dictionary so
    that a single builder covers the whole contract: a branch reading a
    field its own event type declares always finds it.

    Args:
        name: The value of the 'event' key, handled or not.

    Returns:
        The event as the drivers publish it.

    """
    event: dict[str, Any] = {
        'event': name,
        'clock': 0,
        'timestamp': datetime.now(),  # noqa: DTZ005
        'serial': 1,
        # move, move_history
        'face': 0,
        'direction': 0,
        'move': 'R',
        'local_timestamp': None,
        'cube_timestamp': None,
        # facelets
        'facelets': VCube().state,
        'state': {'CP': [], 'CO': [], 'EP': [], 'EO': []},
        # hardware, gyro-config
        'hardware_name': 'GAN',
        'hardware_version': '1.0',
        'software_version': '1.0',
        'gyroscope_supported': True,
        'gyroscope_enabled': True,
        'gyroscope_ready': True,
        'restart_no_power': 0,
        # battery
        'level': 80,
        'charging_state': 0,
        # gyro
        'quaternion': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
        'velocity': {'x': 0.0, 'y': 0.0, 'z': 0.0},
    }
    return cast('EventDict', event)


async def fake_client(*_args: object, **_kwargs: object) -> None:
    """Stand for a client connecting and leaving without a hitch."""
    await asyncio.sleep(0)


async def missing_cube_client(*_args: object, **_kwargs: object) -> None:
    """
    Stand for a client finding no cube to connect to.

    Raises:
        CubeNotFoundError: Always, that is the point.

    """
    await asyncio.sleep(0)
    raise CubeNotFoundError


async def fake_consumer(*_args: object, **_kwargs: object) -> None:
    """Stand for a consumer having nothing to drain."""
    await asyncio.sleep(0)


class TestLinearRegression(unittest.TestCase):
    """Tests for the least squares regression of bt-info."""

    def test_perfect_line(self) -> None:
        """Test an exact affine relation."""
        slope, intercept = linear_regression(
            [1.0, 2.0, 3.0, 4.0],
            [3.0, 5.0, 7.0, 9.0],
        )

        self.assertAlmostEqual(slope, 2.0)
        self.assertAlmostEqual(intercept, 1.0)

    def test_noisy_line(self) -> None:
        """Test a relation with a residual on each point."""
        slope, intercept = linear_regression(
            [0.0, 1.0, 2.0, 3.0],
            [1.0, 3.0, 4.0, 6.0],
        )

        self.assertAlmostEqual(slope, 1.6)
        self.assertAlmostEqual(intercept, 1.1)

    def test_constant_x(self) -> None:
        """Test a null variance on x, where no slope can be computed."""
        slope, intercept = linear_regression(
            [2.0, 2.0, 2.0],
            [1.0, 5.0, 9.0],
        )

        self.assertAlmostEqual(slope, 1.0)
        self.assertAlmostEqual(intercept, 3.0)

    def test_empty(self) -> None:
        """Test that no data point gives the neutral line."""
        self.assertEqual(
            linear_regression([], []),
            (1.0, 0.0),
        )

    def test_single_point(self) -> None:
        """Test that a single point gives the neutral line through it."""
        self.assertEqual(
            linear_regression([2.0], [5.0]),
            (1.0, 3.0),
        )

    def test_mismatched_lengths(self) -> None:
        """Test that two series of different sizes are refused."""
        with self.assertRaises(ValueError):
            linear_regression([1.0, 2.0, 3.0], [1.0, 2.0])

        with self.assertRaises(ValueError):
            linear_regression([1.0, 2.0], [1.0, 2.0, 3.0])


class TestShowStateTiming(unittest.TestCase):
    """Tests for the rendering duration reported by show_state."""

    def setUp(self) -> None:
        """Build the orientation and the solved cube used by the renders."""
        self.orientation_moves = get_orientation_moves('UF')
        self.cube = VCube()

    def test_render_is_timed(self) -> None:
        """Test that a rendering reports its duration in the log."""
        with self.assertLogs(
                'term_timer.scripts.bluetooth_info',
                level=logging.DEBUG,
        ) as logs:
            show_state(
                ['R@100', 'U@200'],
                self.orientation_moves,
                self.cube,
            )

        records = [
            record for record in logs.records
            if record.getMessage().startswith('SHOW STATE:')
        ]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].levelno, logging.DEBUG)
        self.assertEqual(records[0].args[0], 2)  # type: ignore[index]

    def test_empty_render_is_timed(self) -> None:
        """Test that a rendering without any move is timed too."""
        with self.assertLogs(
                'term_timer.scripts.bluetooth_info',
                level=logging.DEBUG,
        ) as logs:
            show_state([], self.orientation_moves, self.cube)

        records = [
            record for record in logs.records
            if record.getMessage().startswith('SHOW STATE:')
        ]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].args[0], 0)  # type: ignore[index]

    def test_slow_render_is_warned(self) -> None:
        """Test that a rendering above the threshold is raised to warning."""
        with (
                patch(
                    'term_timer.scripts.bluetooth_info.'
                    'SHOW_STATE_SLOW_THRESHOLD',
                    -1.0,
                ),
                self.assertLogs(
                    'term_timer.scripts.bluetooth_info',
                    level=logging.DEBUG,
                ) as logs,
        ):
            show_state(
                ['R@100'],
                self.orientation_moves,
                self.cube,
            )

        records = [
            record for record in logs.records
            if record.getMessage().startswith('SHOW STATE:')
        ]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].levelno, logging.WARNING)


class TestSessionReport(unittest.TestCase):
    """Tests for the closing summary of a session."""

    def summary(self, report: SessionReport) -> str:
        """
        Capture the summary block a report logs.

        Args:
            report: The report to summarize.

        Returns:
            The logged message, colors included.

        """
        with self.assertLogs(
                'term_timer.scripts.bluetooth_info',
                level=logging.INFO,
        ) as logs:
            report.log_summary()

        return logs.records[0].getMessage()

    def test_events_are_counted_by_type(self) -> None:
        """Test that the summary counts the events of each type."""
        report = SessionReport(
            events=[
                facelets_event(VCube().state),
                facelets_event(VCube().state),
            ],
        )

        summary = self.summary(report)

        self.assertIn('Duration', summary)
        self.assertIn('2', summary)
        self.assertIn('facelets', summary)

    def test_empty_session_is_summarized(self) -> None:
        """Test that a session without any event still says so."""
        self.assertIn('none', self.summary(SessionReport()))

    def test_desynchros_are_reported(self) -> None:
        """Test that the checked facelets are reported when there are."""
        report = SessionReport(facelets_checked=47, desynchronisations=3)

        summary = self.summary(report)

        self.assertIn('Desynchros', summary)
        self.assertIn('47 facelets checked', summary)

    def test_desynchros_are_skipped_without_check(self) -> None:
        """Test that no line is written when nothing was ever checked."""
        self.assertNotIn('Desynchros', self.summary(SessionReport()))


class TestConsumerDesynchronisation(unittest.IsolatedAsyncioTestCase):
    """Tests for the desynchronisations counted by the consumer."""

    @staticmethod
    async def consume(states: list[str]) -> SessionReport:
        """
        Run the consumer over facelets events, then disconnect.

        Args:
            states: The successive cube states the cube announces.

        Returns:
            The report the consumer filled.

        """
        queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()
        for state in states:
            queue.put_nowait([facelets_event(state)])
        queue.put_nowait(None)

        report = SessionReport()

        with patch('term_timer.scripts.bluetooth_info.SOUND_PLAYER'):
            await consumer_cb(
                queue,
                threading.Event(),
                None,
                report,
                show_cube=False,
                orientation_faces='UF',
            )

        return report

    async def test_desynchronisation_is_counted(self) -> None:
        """Test that facelets contradicting the moves are counted."""
        turned = VCube()
        turned.rotate('R')

        report = await self.consume(
            [VCube().state, turned.state],
        )

        self.assertEqual(report.facelets_checked, 1)
        self.assertEqual(report.desynchronisations, 1)

    async def test_synchronized_facelets_are_not_counted(self) -> None:
        """Test that facelets agreeing with the moves count as checked."""
        report = await self.consume(
            [VCube().state, VCube().state, VCube().state],
        )

        self.assertEqual(report.facelets_checked, 2)
        self.assertEqual(report.desynchronisations, 0)


class TestConsumerEventCoverage(unittest.IsolatedAsyncioTestCase):
    """Tests that the consumer covers what the drivers publish."""

    @staticmethod
    async def consume(event: EventDict) -> list[str]:
        """
        Run the consumer over a single event, then disconnect.

        Args:
            event: The event the cube announces.

        Returns:
            The names of the events that fell into the unhandled branch.

        """
        queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()
        queue.put_nowait([event])
        queue.put_nowait(None)

        with (
                patch('term_timer.scripts.bluetooth_info.SOUND_PLAYER'),
                patch('term_timer.scripts.bluetooth_info.logger') as logged,
        ):
            await consumer_cb(
                queue,
                threading.Event(),
                None,
                SessionReport(),
                show_cube=False,
                orientation_faces='UF',
            )

        return [
            call.args[1]
            for call in logged.warning.call_args_list
            if 'UNHANDLED' in str(call.args[0])
        ]

    async def test_every_driver_event_is_handled(self) -> None:
        """Test that no event of the contract reaches the repli branch."""
        for name in sorted(BLUETOOTH_EVENTS):
            with self.subTest(event=name):
                self.assertEqual(await self.consume(driver_event(name)), [])

    async def test_unknown_event_is_reported(self) -> None:
        """Test that an event outside the contract is caught, as a proof."""
        self.assertEqual(
            await self.consume(driver_event('nonsense')),
            ['nonsense'],
        )


class TestRunExitCode(unittest.IsolatedAsyncioTestCase):
    """Tests for the exit code a session ends on."""

    def setUp(self) -> None:
        """Build the options of a plain live session."""
        self.options = Namespace(
            input='',
            output='',
            time=1,
            filter_name='',
            cube_reset=False,
            gyroscope_enable=False,
            gyroscope_disable=False,
            show_cube=False,
            orientation='UF',
            rotation_threshold=75.0,
        )

    async def run_session(
            self,
            client: Callable[..., Awaitable[None]],
    ) -> tuple[int, list[str]]:
        """
        Run a session over a faked client and consumer.

        Args:
            client: The coroutine function standing for the client.

        Returns:
            The exit code and the messages logged by the session.

        """
        with (
                patch(
                    'term_timer.scripts.bluetooth_info.client_cb',
                    client,
                ),
                patch(
                    'term_timer.scripts.bluetooth_info.consumer_cb',
                    fake_consumer,
                ),
                self.assertLogs(
                    'term_timer.scripts.bluetooth_info',
                    level=logging.INFO,
                ) as logs,
        ):
            code = await run(self.options, None, threading.Event())

        return code, [record.getMessage() for record in logs.records]

    async def test_missing_cube_fails(self) -> None:
        """Test that a session without any cube reports a failure."""
        code, messages = await self.run_session(missing_cube_client)

        self.assertEqual(code, 1)
        self.assertTrue(
            any('No Bluetooth cube found' in message for message in messages),
        )
        self.assertNotIn('Bye bye', messages)

    async def test_session_succeeds(self) -> None:
        """Test that a session that took place succeeds and summarizes."""
        code, messages = await self.run_session(fake_client)

        self.assertEqual(code, 0)
        self.assertIn('Bye bye', messages)
        self.assertTrue(
            any(message.startswith('Session summary:')
                for message in messages),
        )

    async def test_replay_succeeds(self) -> None:
        """Test that a replay never reports a connection failure."""
        self.options.input = 'events.json'

        with patch('term_timer.scripts.bluetooth_info.replay') as replayer:
            code = await run(self.options, None, threading.Event())

        self.assertEqual(code, 0)
        replayer.assert_called_once_with(self.options)
