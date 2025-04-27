import asyncio
import contextlib
import logging

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_moves

from term_timer.bluetooth.facelets import to_magiccube_facelets
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import CubeNotFoundError
from term_timer.console import console
from term_timer.magic_cube import Cube

logger = logging.getLogger(__name__)


async def consumer_cb(queue):
    internal_cube = None
    moves = []

    def show_cube(cube):
        console.print(str(cube), end='')

    while True:
        events = await queue.get()

        if events is None:
            logger.info(
                'CONSUMER: Got message from client about disconnection. '
                'Exiting consumer loop...',
            )
            break

        for event in events:
            event_name = event['event']
            if event_name == 'hardware':
                logger.info(
                    'CONSUMER: Hardware %s version %s, Software %s, %s',
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
                    'CONSUMER: Battery: %s%%',
                    event['level'],
                )
            elif event_name == 'facelets':
                internal_cube = Cube(3, to_magiccube_facelets(['facelets']))
                logger.info(
                    'CONSUMER: Facelets initialized',
                )
                show_cube(internal_cube)

            elif event_name == 'move':
                logger.info(
                    'CONSUMER: Face: %s, Direction: %s, Move: %s',
                    event['face'],
                    event['direction'],
                    event['move'],
                )
                moves.append(event['move'])
                if internal_cube:
                    internal_cube.rotate(event['move'])
                    show_cube(internal_cube)
                    algo = parse_moves(moves)
                    recon = algo.transform(
                        reslice_moves,
                        degrip_full_moves,
                        remove_final_rotations,
                        optimize_double_moves,
                        to_fixpoint=True,
                    )
                    logger.info('MOVES: %s', algo)
                    logger.info('RECON: %s', recon)


async def client_cb(queue):

    async with BluetoothInterface(queue) as bi:

        # Initialize/reset the cube
        await bi.send_command('REQUEST_HARDWARE')
        await bi.send_command('REQUEST_BATTERY')
        await bi.send_command('REQUEST_FACELETS')

        logger.info('Free play for 10s')
        await asyncio.sleep(10.0)

    logger.warning('Interface disconnected')


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
