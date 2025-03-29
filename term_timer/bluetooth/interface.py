import logging

from bleak import BleakClient
from bleak import BleakScanner

from term_timer.bluetooth.constants import PREFIX
from term_timer.bluetooth.drivers import GanGen2Driver

logger = logging.getLogger(__name__)

DRIVERS = [
    GanGen2Driver,
]


class CubeNotFoundError(Exception):
    pass


class BluetoothInterface:
    device = None
    client = None
    driver = None

    scan_timeout = 5

    def __init__(self, queue):
        self.queue = queue

    async def __aenter__(self) -> bool:
        device = await self.scan()

        if not device:
            logger.warning(
                'No bluetooth cube found.\n'
                "Make sure it's powered on and in pairing mode.",
            )
            raise CubeNotFoundError

        self.device = device
        self.client = BleakClient(self.device.address)
        await self.client.connect()

        logger.info(' * Connected: %r', self.client.is_connected)

        for service in self.client.services:
            for driver in DRIVERS:
                if service.uuid == driver.service_uid:
                    logger.info(' * Using %s driver', driver.__name__)
                    self.driver = driver(self.client, self.device)
                    break
            if self.driver:
                break

        if not self.driver:
            logger.warning('No driver found')

        await self.client.start_notify(
            self.driver.state_characteristic_uid,
            self.notification_handler,
        )

        return self

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        await self.client.stop_notify(
            self.driver.state_characteristic_uid,
        )
        await self.client.disconnect()
        # Send an "exit command to the consumer"
        await self.queue.put(None)

    async def notification_handler(self, sender, data):
        events = await self.driver.event_handler(sender, data)
        await self.queue.put(events)

    async def send_command(self, command: str) -> bool:
        """Send a command to the cube"""
        if not self.client or not self.client.is_connected:
            logger.warning('Not connected to cube')
            return False

        msg = self.driver.send_command_handler(command)

        if not msg:
            logger.warning('Unknown command')
            return False

        await self.client.write_gatt_char(
            self.driver.command_characteristic_uid,
            msg,
        )

        return True

    async def scan(self):
        logger.info(
            'Scanning for cube during %ss...',
            self.scan_timeout,
        )
        selected_device = None
        devices = await BleakScanner.discover(
            timeout=self.scan_timeout,
        )

        for device in devices:
            name = device.name or 'N/A'
            logger.info(' * %s %s', device, name)

            for prefix in PREFIX:
                if prefix in name:
                    logger.info(
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
