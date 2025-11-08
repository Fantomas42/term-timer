"""Bluetooth cube interface for scanning, connecting, and communication."""

import logging
from asyncio import Queue
from typing import Final
from typing import cast

from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from term_timer.bluetooth.constants import PREFIX
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.drivers.gan_gen4 import GanGen4Driver
from term_timer.bluetooth.drivers.moyu import MoyuWeilong10Driver
from term_timer.bluetooth.types import EventDict
from term_timer.config import DEBUG
from term_timer.exceptions import CubeNotFoundError

logger = logging.getLogger(__name__)

DRIVERS: Final[list[type[Driver]]] = [
    GanGen2Driver,
    GanGen3Driver,
    GanGen4Driver,
    MoyuWeilong10Driver,
]


class BluetoothInterface:
    client: BleakClient | None = None
    driver: Driver | None = None

    scan_timeout: int = 5
    connect_timeout: int = 5

    def __init__(self, queue: Queue[list[EventDict] | None]) -> None:
        self.queue: Queue[list[EventDict] | None] = queue

    async def __aenter__(
            self,
            address: str | None = None,
            filter_name: str | None = None,
    ) -> 'BluetoothInterface':
        """Enter async context manager by connecting to Bluetooth cube."""
        if not address:
            device = await self.scan(filter_name)

            if not device:
                logger.debug(
                    'No Bluetooth cube found.\n'
                    'Make sure a cube is powered on and in pairing mode.',
                )
                raise CubeNotFoundError
            address = device.address

        self.client = BleakClient(address, timeout=self.connect_timeout)

        try:
            await self.client.connect()
        except BleakError as error:
            msg = (
                f'No Bluetooth cube found at { address }.\n'
                'Make sure the cube is powered on and in pairing mode.'
            )
            logger.debug(msg)
            raise CubeNotFoundError from error

        logger.debug(' * Connected: %r', self.client.is_connected)

        for service in self.client.services:
            for driver in DRIVERS:
                if service.uuid == driver.service_uid:
                    logger.debug(' * Using %s driver', driver.__name__)
                    self.driver = driver(self.client)
                    break
            if self.driver:
                break

        if not self.driver:
            logger.debug('No driver found')
            raise CubeNotFoundError

        await self.client.start_notify(
            self.driver.state_characteristic_uid,
            self.notification_handler,
        )

        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc_value: BaseException | None,
                        exc_traceback: object) -> None:
        """Exit async context manager by disconnecting from cube."""
        logger.debug('Disconnect from client')
        # Send an "exit command to the consumer"
        await self.queue.put(None)

        if self.client and self.client.is_connected and self.driver:
            await self.client.stop_notify(
                self.driver.state_characteristic_uid,
            )
            await self.client.disconnect()

    async def notification_handler(self, sender: BleakGATTCharacteristic,
                                   data: bytearray) -> None:
        self.driver = cast(Driver, self.driver)

        events = await self.driver.event_handler(sender, data)

        if DEBUG:
            for event in events:
                logger.debug('Event: %s', event['event'].upper())
        await self.queue.put(events)

    async def send_command(self, command: str) -> bool:
        """Send a command to the cube"""
        if not self.client or not self.client.is_connected:
            logger.debug('Command not connected to cube')
            return False

        logger.debug('Sending: %s', command)

        self.driver = cast(Driver, self.driver)
        msg = self.driver.send_command_handler(command)

        if msg is False:
            logger.debug('Unknown command "%s"', command)
            return False

        msg = cast(bytes, msg)
        await self.client.write_gatt_char(
            self.driver.command_characteristic_uid,
            msg,
        )

        return True

    async def scan(self, filter_name: str | None = None) -> BLEDevice | None:
        logger.debug(
            'Scanning for cube during %ss...',
            self.scan_timeout,
        )
        selected_device = None
        try:
            devices = await BleakScanner.discover(
                timeout=self.scan_timeout,
            )
        except (BleakError, OSError) as error:
            logger.debug(str(error))
            raise CubeNotFoundError from error

        for device in devices:
            name = device.name or 'N/A'
            logger.debug(' * %s %s', device, name)

            for prefix in PREFIX:
                if prefix in name and (not filter_name or filter_name in name):
                    logger.debug(
                        'Found %s cube: %s (%s)',
                        prefix, device.name, device.address,
                    )
                    selected_device = device
                    break
            if selected_device:
                break

        if not selected_device:
            return None

        return selected_device
