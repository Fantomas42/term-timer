"""Async task control utilities for managing concurrent operations."""
import asyncio
from collections.abc import Iterable
from typing import TYPE_CHECKING

from term_timer.exceptions import CubeDisconnectedError
from term_timer.logger import spawn


class Controler:
    """Mixin providing async task control utilities."""

    if TYPE_CHECKING:
        # Attributes from Bluetooth mixin
        bluetooth_lost_event: asyncio.Event

    async def wait_control(
            self,
            tasks: Iterable[asyncio.Task[object]],
    ) -> set[asyncio.Task[object]]:
        """
        Wait for first task to complete, then cancel remaining tasks.

        The loss of the cube runs in the race: every phase waiting here
        waits for a cube event, and once the cube is gone that event
        cannot come. The session ends instead of waiting for it.

        Returns:
            Set of completed tasks.

        Raises:
            CubeDisconnectedError: The cube announced its disconnection
                while the phase was waiting for it.

        """
        lost_task: asyncio.Task[object] = spawn(
            self.bluetooth_lost_event.wait(),
            'event-bluetooth-lost',
        )

        done, pending = await asyncio.wait(
            [*tasks, lost_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)

        if lost_task in done:
            msg = 'Cube disconnected, ending the session.'
            raise CubeDisconnectedError(msg)

        return done
