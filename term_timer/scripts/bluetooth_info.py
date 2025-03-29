import asyncio
import contextlib
import logging

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import CubeNotFoundError
from term_timer.console import console
from term_timer.magic_cube import Cube

logger = logging.getLogger(__name__)


async def consumer_cb(queue):
    logger.info('CONSUMER : Start consumming')

    internal_cube = None

    def show_cube(cube):
        console.print(str(cube), end='')

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
                internal_cube = Cube(3, event['facelets'])
                logger.info(
                    'CONSUMER : Facelets initialized',
                )
                show_cube(internal_cube)

            elif event_name == 'move':
                if internal_cube:
                    internal_cube.rotate([event['move']])
                    show_cube(internal_cube)
                logger.info(
                    'CONSUMER : Move : Face : %s, Direction : %s, Move : %s',
                    event['face'],
                    event['direction'],
                    event['move'],
                )


async def client_cb(queue):
    cube = BluetoothInterface(queue)

    await cube.scan_and_connect()
    logger.info('Free play for 5 seconds')
    await asyncio.sleep(5.0)
    await cube.disconnect()

    logger.warning('Disconnected')


async def run():
    queue = asyncio.Queue()

    client = client_cb(queue)
    consumer = consumer_cb(queue)

    with contextlib.suppress(CubeNotFoundError):
        await asyncio.gather(client, consumer)

    logger.info('Bye bye')


def main():
    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=logging.INFO,
    )
    asyncio.run(run())
