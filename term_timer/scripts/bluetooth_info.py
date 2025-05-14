import asyncio
import logging
import logging.config
import os
import sys
from contextlib import suppress
from pprint import pformat

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.bluetooth.facelets import to_magiccube_facelets
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.interface import CubeNotFoundError
from term_timer.console import console
from term_timer.magic_cube import Cube

logger = logging.getLogger(__name__)

LOGGING_CONF = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simpleFormatter': {
            'class': 'logging.Formatter',
            'format': '[PID %(process)s@%(asctime)s] '
                      '%(levelname)-7s %(message)s',
        },
        'consoleFormatter': {
            'class': 'logging.Formatter',
            'format': '%(levelname)-7s %(message)s',
        },
    },
    'handlers': {
        'fileHandler': {
            'formatter': 'simpleFormatter',
            'level': 'DEBUG',
            'backupCount': 5,
            'maxBytes': 50000000,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join('/tmp/', 'term-timer-debug.log'),
        },
        'consoleHandler': {
            'formatter': 'consoleFormatter',
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'bleak': {
            'level': 'DEBUG',
            'handlers': [
                'fileHandler',
            ],
        },
        'term_timer': {
            'level': 'DEBUG',
            'handlers': [
                'consoleHandler',
                'fileHandler',
            ],
        },
    },
}


async def consumer_cb(queue, show_cube):
    visual_cube = None
    virtual_cube = None
    moves = []

    def print_cube(cube):
        if show_cube:
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
            elif event_name == 'gyro':
                logger.info(
                    'CONSUMER: Gyroscope event',
                )
            elif event_name == 'facelets':
                logger.info(
                    'CONSUMER: Facelets received',
                )
                if virtual_cube:
                    if virtual_cube.state != event['facelets']:
                        logger.warning('FACELETS DESYNCHRONISED')
                else:
                    virtual_cube = VCube(event['facelets'])

                visual_cube = Cube(
                    3,
                    to_magiccube_facelets(event['facelets']),
                )
                print_cube(visual_cube)

            elif event_name == 'move':
                logger.info(
                    'CONSUMER: Face: %s, Direction: %s, Move: %s',
                    event['face'],
                    event['direction'],
                    event['move'],
                )
                moves.append(event['move'])

                if virtual_cube:
                    virtual_cube.rotate(event['move'])

                if visual_cube:
                    visual_cube.rotate(event['move'])
                    print_cube(visual_cube)

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
            else:
                logger.info(
                    'CONSUMER: UNKNOWN\n%s',
                    pformat(event),
                )


async def client_cb(queue, time):

    bluetooth_interface = BluetoothInterface(
        queue,
    )

    await bluetooth_interface.__aenter__()  # noqa: PLC2801

    # Initialize/reset the cube
    await bluetooth_interface.send_command('REQUEST_HARDWARE')
    await bluetooth_interface.send_command('REQUEST_BATTERY')
    await bluetooth_interface.send_command('REQUEST_FACELETS')

    logger.info('Free play for %ss', time)
    await asyncio.sleep(time)

    await bluetooth_interface.__aexit__(None, None, None)
    logger.warning('Interface disconnected')


async def run(options):
    queue = asyncio.Queue()

    client = client_cb(queue, options.time)
    consumer = consumer_cb(queue, options.show_cube)

    with suppress(CubeNotFoundError):
        await asyncio.gather(client, consumer)

    logger.info('Bye bye')


def main():
    logging.config.dictConfig(LOGGING_CONF)

    parser = ArgumentParser(
        description='Debug bluetooth devices.',
    )

    parser.add_argument(
        '-t', '--time',
        type=int,
        default=10,
        metavar='SECONDS',
        help=(
            'Set the countdown before disconnecting.\n'
            'Default: 10.'
        ),
    )
    parser.add_argument(
        '-p', '--show-cube',
        action='store_true',
        help=(
            'Display the cube state.\n'
            'Default: False.'
        ),
    )

    args = parser.parse_args(sys.argv[1:])

    asyncio.run(run(args), debug=True)
