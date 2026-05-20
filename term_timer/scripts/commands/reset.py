"""Reset command for Bluetooth cube."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.config import DEVICE_ADDRESS
from term_timer.config import DEVICE_NAME
from term_timer.exceptions import CubeNotFoundError
from term_timer.interface.console import console
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.interface.terminal import Terminal

if TYPE_CHECKING:
    from argparse import Namespace

    from term_timer.bluetooth.annotations import EventDict


async def reset(options: Namespace) -> int:
    """
    Reset the state of the Bluetooth cube.

    Returns:
        Exit code (0 for success, 1 if cube not found).

    """
    queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()
    bluetooth_interface = BluetoothInterface(queue)

    address = DEVICE_ADDRESS
    filter_name = options.filter_name or None

    try:
        if not address:
            console.print(
                '[bluetooth]📡Bluetooth:[/bluetooth] '
                'Scanning for Bluetooth cube for '
                f'{ bluetooth_interface.scan_timeout }s...',
                end='',
            )
            device = await bluetooth_interface.scan(filter_name)
            if device:
                address = device.address
        else:
            console.print(
                '[bluetooth]📡Bluetooth:[/bluetooth] '
                f'Connecting to [b]{ DEVICE_NAME or address }[/b]...',
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
    SOUND_PLAYER.success()

    await bluetooth_interface.__aexit__(None, None, None)

    console.print(
        '[bluetooth]✅Bluetooth:[/bluetooth] '
        'Cube reset successfully.',
    )

    return 0
