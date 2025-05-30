import logging
from asyncio import Queue

from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from term_timer.bluetooth.constants import PREFIX
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.drivers.gan_gen4 import GanGen4Driver
from term_timer.bluetooth.drivers.moyu import MoyuWeilong10Driver

logger = logging.getLogger(__name__)

DRIVERS = [
    GanGen2Driver,
    GanGen3Driver,
    GanGen4Driver,
    MoyuWeilong10Driver,
]


class CubeNotFoundError(Exception):
    pass


class BluetoothInterface:
    device = None
    client = None
    driver = None

    scan_timeout = 5

    def __init__(self, queue: Queue):
        self.queue = queue

    async def __aenter__(self, device=None) -> bool:
        if not device:
            device = await self.scan()

        if not device:
            logger.debug(
                'No bluetooth cube found.\n'
                "Make sure it's powered on and in pairing mode.",
            )
            raise CubeNotFoundError

        self.device = device
        self.client = BleakClient(self.device.address)
        await self.client.connect()

        logger.debug(' * Connected: %r', self.client.is_connected)

        for service in self.client.services:
            for driver in DRIVERS:
                if service.uuid == driver.service_uid:
                    logger.debug(' * Using %s driver', driver.__name__)
                    self.driver = driver(self.client, self.device)
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

    async def __aexit__(self, exc_type, exc_value, exc_traceback) -> None:
        logger.debug('Disconnect from client')
        # Send an "exit command to the consumer"
        await self.queue.put(None)

        if self.client and self.client.is_connected:
            await self.client.stop_notify(
                self.driver.state_characteristic_uid,
            )
            await self.client.disconnect()

    async def notification_handler(self, sender, data) -> None:
        events = await self.driver.event_handler(sender, data)
        for event in events:
            logger.debug('Event: %s', event['event'].upper())
        await self.queue.put(events)

    async def send_command(self, command: str) -> bool:
        """Send a command to the cube"""
        if not self.client or not self.client.is_connected:
            logger.debug('Command not connected to cube')
            return False

        logger.debug('Sending: %s', command)
        msg = self.driver.send_command_handler(command)

        if not msg:
            logger.debug('Unknown command "%s"', command)
            return False

        await self.client.write_gatt_char(
            self.driver.command_characteristic_uid,
            msg,
        )

        return True

    async def scan(self) -> BLEDevice | None:
        logger.debug(
            'Scanning for cube during %ss...',
            self.scan_timeout,
        )
        selected_device = None
        try:
            devices = await BleakScanner.discover(
                timeout=self.scan_timeout,
            )
        except BleakError as error:
            logger.debug(str(error))
            raise CubeNotFoundError from error

        for device in devices:
            name = device.name or 'N/A'
            logger.debug(' * %s %s', device, name)

            for prefix in PREFIX:
                if prefix in name:
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
