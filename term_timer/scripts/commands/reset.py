"""Reset command for Bluetooth cube."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
from typing import cast

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.config import CubeDevice
from term_timer.constants import BLUETOOTH_RESET_CONFIRMATION_TIMEOUT
from term_timer.exceptions import CubeNotFoundError
from term_timer.interface.console import console
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.interface.terminal import Terminal

if TYPE_CHECKING:
    from argparse import Namespace

    from term_timer.bluetooth.annotations import EventDict
    from term_timer.bluetooth.annotations import ResetEventDict
    from term_timer.bluetooth.drivers.base import Driver


async def wait_for_reset_result(
        queue: asyncio.Queue[list[EventDict] | None],
) -> int | None:
    """
    Wait for the cube's reset confirmation event.

    Returns:
        The `result` field of the `reset` event, or None if the link
        closed or no confirmation arrived before the timeout.

    """
    clock = time.monotonic()

    while True:
        remaining = (
            BLUETOOTH_RESET_CONFIRMATION_TIMEOUT
            - (time.monotonic() - clock)
        )
        if remaining <= 0:
            return None

        try:
            events = await asyncio.wait_for(queue.get(), timeout=remaining)
        except asyncio.TimeoutError:  # noqa: UP041
            return None

        if events is None:
            return None

        for event in events:
            if event['event'] == 'reset':
                return cast('ResetEventDict', event)['result']


async def reset(options: Namespace) -> int:
    """
    Reset the state of the Bluetooth cube.

    Returns:
        Exit code (0 for success, 1 if the cube could not be found, or
        for a driver confirming the reset, if it was refused or timed
        out).

    """
    queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()
    bluetooth_interface = BluetoothInterface(queue)

    cube = options.bluetooth or CubeDevice.discovered(
        prefer_known=True,
    )
    address = cube.address
    filter_name = options.filter_name or None

    try:
        if not address:
            console.print(
                '[bluetooth]📡Bluetooth:[/bluetooth] '
                'Scanning for Bluetooth cube for '
                f'{ bluetooth_interface.scan_timeout }s...',
                end='',
            )
            device = await bluetooth_interface.scan(
                filter_name,
                cube.scan_addresses,
            )
            if device:
                address = device.address
        else:
            console.print(
                '[bluetooth]📡Bluetooth:[/bluetooth] '
                f'Connecting to [b]{ cube.display_name }[/b]...',
                end='',
            )

        await bluetooth_interface.__aenter__(
            address, use_gyroscope=False,
        )
    except CubeNotFoundError:
        Terminal.clear_line(full=True)
        console.print(
            '[bluetooth]😥Bluetooth:[/bluetooth] '
            '[warning]No Bluetooth cube could be found.[/warning]',
        )
        return 1

    Terminal.clear_line(full=True)
    console.print(
        '[bluetooth]🔗Bluetooth:[/bluetooth] '
        'Cube connected, sending reset...',
    )

    await bluetooth_interface.send_command('REQUEST_RESET')

    driver = cast('Driver', bluetooth_interface.driver)

    if driver.confirms_reset:
        result = await wait_for_reset_result(queue)

        if not result:
            await bluetooth_interface.__aexit__(None, None, None)
            SOUND_PLAYER.solve_failed()
            console.print(
                '[bluetooth]😥Bluetooth:[/bluetooth] '
                '[warning]Cube did not confirm the reset.[/warning]'
                if result is None else
                '[bluetooth]😥Bluetooth:[/bluetooth] '
                '[warning]Cube refused the reset.[/warning]',
            )
            return 1

    SOUND_PLAYER.solve_success()

    await bluetooth_interface.__aexit__(None, None, None)

    console.print(
        '[bluetooth]✅Bluetooth:[/bluetooth] '
        'Cube reset successfully.',
    )

    return 0
