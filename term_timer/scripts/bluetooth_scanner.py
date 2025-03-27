import logging
from pprint import pformat
from time import sleep

import asyncio

from bleak import BleakClient
from bleak import BleakScanner

from term_timer.bluetooth.constants import PREFIX
from term_timer.bluetooth.drivers import GanGen2Driver

logger = logging.getLogger(__name__)

DRIVERS = [
    GanGen2Driver,
]


class BluetoothCube:
    device = None
    client = None
    driver = None

    scan_timeout = 5

    async def scan(self):
        logger.info(f'Scanning for cube during {self.scan_timeout}s...')
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
                        f'Found { prefix } cube: '
                        f'{ device.name } ({ device.address })',
                    )
                    selected_device = device
                break
            if selected_device:
                break

        if not selected_device:
            return None

        return selected_device

    async def scan_and_connect(self) -> bool:
        device = await self.scan()

        if not device:
            logger.warning(
                'No bluetooth cube found.\n'
                "Make sure it's powered on and in pairing mode.",
            )
            return False

        self.device = device

        async with BleakClient(self.device.address) as self.client:
            logger.info(f'Connected: { self.client.is_connected }')

            for service in self.client.services:
                for driver in DRIVERS:
                    if service.uuid == driver.service_uid:
                        logger.info('Using %s driver', driver.__name__)
                        self.driver = driver(self.client, self.device)
                        break
                if self.driver:
                    break

            if not self.driver:
                logger.warning('No driver found')

            # Subscribe to notifications for state changes
            await self.client.start_notify(
                self.driver.state_characteristic_uid,
                self.driver.notification_handler,
            )

            # Initialize/reset the cube
            await self.send_command('REQUEST_HARDWARE')
            await self.send_command('REQUEST_FACELETS')
            await self.send_command('REQUEST_BATTERY')

        return True

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


async def run():
    cube = BluetoothCube()
    if await cube.scan_and_connect():
        logger.info('Waiting 2sec...')
        await asyncio.sleep(2)
        logger.info('Ending connection')
        await cube.client.disconnect()

        for event in cube.driver.events:
            if event['event'] != 'gyro':
                logger.info('\n%s', pformat(event))


def main():
    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=logging.INFO,
    )
    asyncio.run(run())
