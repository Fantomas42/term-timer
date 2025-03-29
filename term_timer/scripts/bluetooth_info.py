import asyncio
import logging

from bleak import BleakClient
from bleak import BleakScanner

from term_timer.bluetooth.constants import PREFIX
from term_timer.bluetooth.drivers import GanGen2Driver
from term_timer.console import console
from term_timer.magic_cube import Cube

logger = logging.getLogger(__name__)

DRIVERS = [
    GanGen2Driver,
]


class DeviceNotFoundError(Exception):
    pass


class BluetoothCube:
    device = None
    client = None
    driver = None

    scan_timeout = 5

    def __init__(self, queue):
        self.queue = queue

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
            return DeviceNotFoundError

        self.device = device

        async with BleakClient(self.device.address) as self.client:
            logger.info(f' * Connected: { self.client.is_connected }')

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

            # Subscribe to notifications for state changes
            await self.client.start_notify(
                self.driver.state_characteristic_uid,
                self.notification_handler,
            )

            # Initialize/reset the cube
            await self.send_command('REQUEST_HARDWARE')
            await self.send_command('REQUEST_FACELETS')
            await self.send_command('REQUEST_BATTERY')

            logger.info('Free play for 5 seconds')
            await asyncio.sleep(5.0)
            await self.client.stop_notify(
                self.driver.state_characteristic_uid,
            )
            # # Send an "exit command to the consumer"
            await self.queue.put(None)

        return True

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


async def consumer_cb(queue):
    logger.info('CONSUMER : Start consumming')

    while True:
        # Use await asyncio.wait_for(queue.get(), timeout=1.0)
        # if you want a timeout for getting data.
        events = await queue.get()
        if events is None:
            logger.info(
                'CONSUMER : Got message from client about disconnection. '
                'Exiting consumer loop...',
            )
            break

        for event in events:
            event_name = event['event']
            if event_name == 'hardware':
                logger.info(
                    'CONSUMER : Hardware %s version %s, Software %s, %s',
                    event['hardware_name'],
                    event['hardware_version'],
                    event['software_version'],
                    (
                        (event['gyroscope_supported'] and 'with Gyroscope')
                        or 'w/o Gyroscope'
                    ),
                )
            elif event_name == 'battery':
                logger.info(
                    'CONSUMER : Battery : %s%%',
                    event['level'],
                )
            elif event_name == 'facelets':
                logger.info(
                    'CONSUMER : Facelets : %s',
                    event['facelets'],
                )
                show_cube(event['facelets'])
            elif event_name == 'move':
                logger.info(
                    'CONSUMER : Move : Face : %s, Direction : %s, Move : %s',
                    event['face'],
                    event['direction'],
                    event['move'],
                )


async def client_cb(queue):
    cube = BluetoothCube(queue)

    await cube.scan_and_connect()

    logger.warning('Disconnected')


async def run():
    queue = asyncio.Queue()

    client = client_cb(queue)
    consumer = consumer_cb(queue)

    try:
        await asyncio.gather(client, consumer)
    except DeviceNotFoundError:
        pass

    logger.info('Bye')


def show_cube(facelets):
    for color, face in (
            ('W', 'U'), ('Y', 'D'),
            ('G', 'F'), ('O', 'L'),
    ):
        facelets = facelets.replace(face, color)

    U, R, F, D, L, B = [facelets[i:i + 9] for i in range(0, len(facelets), 9)]
    final_facelets = ''.join([U, L, F, R, B, D])

    cube = Cube(3, final_facelets)
    console.print(str(cube), end='')


def main():
    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=logging.INFO,
    )
    asyncio.run(run())
