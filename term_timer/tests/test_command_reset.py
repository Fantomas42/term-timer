"""Tests for the reset command."""
from __future__ import annotations

import unittest
from argparse import Namespace
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Self
from unittest import mock

from term_timer.config import CubeDevice
from term_timer.scripts.commands.reset import reset

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from term_timer.bluetooth.annotations import EventDict
    from term_timer.bluetooth.annotations import ResetEventDict

    CubeQueue = asyncio.Queue[list[EventDict] | None]


@dataclass
class FakeDriver:
    """Driver stub carrying only the reset confirmation capability."""

    confirms_reset: bool


class FakeBluetoothInterface:
    """
    BT interface stub for the reset command, no real BLE calls.

    ``on_send`` runs once REQUEST_RESET is sent, standing in for
    whatever the cube pushes onto the queue in response: a reset
    event, a disconnect sentinel, or nothing at all for a timeout.
    """

    scan_timeout = 5

    def __init__(
            self,
            queue: CubeQueue,
            *,
            confirms_reset: bool,
            on_send: Callable[[CubeQueue], None] | None = None,
    ) -> None:
        """Store the queue and the capability the test is exercising."""
        self.queue = queue
        self.driver = FakeDriver(confirms_reset=confirms_reset)
        self.on_send = on_send

    async def scan(  # noqa: PLR6301
            self, *args: object, **kwargs: object,  # noqa: ARG002
    ) -> None:
        """Report no device found by scanning, unused by these tests."""
        return

    async def __aenter__(
            self, *args: object, **kwargs: object,
    ) -> Self:
        """
        Enter the connection, a no-op for this stub.

        Returns:
            This same instance, as the real interface does.

        """
        return self

    async def send_command(self, command: str) -> bool:  # noqa: ARG002
        """
        Run `on_send` in place of an actual write to the cube.

        Returns:
            True, as the real interface does once the write succeeds.

        """
        if self.on_send:
            self.on_send(self.queue)
        return True

    async def __aexit__(
            self, *args: object,
    ) -> None:
        """Exit the connection, a no-op for this stub."""
        return


def reset_options() -> Namespace:
    """
    Build the options of a reset run against a known address.

    A non-empty address skips the scanning branch entirely.

    Returns:
        The options the command parses its run from.

    """
    return Namespace(
        bluetooth=CubeDevice(address='AA:BB:CC:DD:EE:FF'),
        filter_name='',
    )


def reset_event(result: int) -> list[EventDict]:
    """
    Build a queue payload holding a single reset confirmation.

    Args:
        result: The `result` field the cube's `reset` event carries.

    Returns:
        A one-element event batch, as the queue receives them.

    """
    event: ResetEventDict = {
        'event': 'reset',
        'clock': 0,
        'timestamp': datetime.now(tz=UTC),
        'result': result,
    }
    return [event]


class TestResetCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for the reset command's validation of the cube's answer."""

    async def run_reset(  # noqa: PLR6301
            self,
            *,
            confirms_reset: bool,
            on_send: Callable[[CubeQueue], None] | None = None,
    ) -> tuple[int, mock.MagicMock]:
        """
        Run the reset command against a faked Bluetooth interface.

        Returns:
            The exit code and the mocked console the command printed to.

        """
        def factory(queue: CubeQueue) -> FakeBluetoothInterface:
            return FakeBluetoothInterface(
                queue, confirms_reset=confirms_reset, on_send=on_send,
            )

        with (
                mock.patch(
                    'term_timer.scripts.commands.reset.BluetoothInterface',
                    factory,
                ),
                mock.patch(
                    'term_timer.scripts.commands.reset.SOUND_PLAYER',
                ),
                mock.patch(
                    'term_timer.scripts.commands.reset.console',
                ) as printer,
        ):
            code = await reset(reset_options())

        return code, printer

    async def test_driver_without_confirmation_succeeds(self) -> None:
        """A driver unable to confirm keeps today's immediate success."""
        code, printer = await self.run_reset(confirms_reset=False)

        self.assertEqual(code, 0)
        self.assertIn(
            'reset successfully', str(printer.print.call_args.args),
        )

    async def test_driver_confirms_successful_reset(self) -> None:
        """A `reset` event with a truthy result reports success."""
        def on_send(queue: CubeQueue) -> None:
            queue.put_nowait(reset_event(1))

        code, printer = await self.run_reset(
            confirms_reset=True, on_send=on_send,
        )

        self.assertEqual(code, 0)
        self.assertIn(
            'reset successfully', str(printer.print.call_args.args),
        )

    async def test_driver_confirms_refused_reset(self) -> None:
        """A `reset` event with a falsy result is reported as a refusal."""
        def on_send(queue: CubeQueue) -> None:
            queue.put_nowait(reset_event(0))

        code, printer = await self.run_reset(
            confirms_reset=True, on_send=on_send,
        )

        self.assertEqual(code, 1)
        self.assertIn('refused', str(printer.print.call_args.args))

    async def test_driver_confirms_but_link_drops(self) -> None:
        """A disconnect sentinel before any `reset` event is a failure."""
        def on_send(queue: CubeQueue) -> None:
            queue.put_nowait(None)

        code, printer = await self.run_reset(
            confirms_reset=True, on_send=on_send,
        )

        self.assertEqual(code, 1)
        self.assertIn('did not confirm', str(printer.print.call_args.args))

    async def test_driver_confirms_but_times_out(self) -> None:
        """No event at all before the timeout is a failure."""
        with mock.patch(
                'term_timer.scripts.commands.reset.'
                'BLUETOOTH_RESET_CONFIRMATION_TIMEOUT',
                0.05,
        ):
            code, printer = await self.run_reset(confirms_reset=True)

        self.assertEqual(code, 1)
        self.assertIn('did not confirm', str(printer.print.call_args.args))
