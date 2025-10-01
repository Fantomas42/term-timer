import asyncio
import logging
import logging.config
import sys
import threading
from argparse import Namespace
from contextlib import suppress
from pprint import pformat
from typing import Any

from cubing_algs.parsing import parse_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.config import CUBE_ORIENTATION
from term_timer.exceptions import CubeNotFoundError
from term_timer.logger import LOGGING_DIR
from term_timer.opengl.thread import CubeGLThread
from term_timer.orientation import get_orientation_moves
from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves
from term_timer.transform import reorient_moves

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
            'filename': LOGGING_DIR / 'bt-info.log',
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


def print_cube(cube: VCube) -> None:
    cube.show(
        orientation=CUBE_ORIENTATION,
        mode='linear',
        facelet='compact',
    )


async def consumer_cb(queue: asyncio.Queue[list[dict[str, object]] | None],
                      cube_ready: threading.Event,
                      gl_thread: CubeGLThread | None,
                      event_collector: list[dict[str, object]],
                      *, show_cube: bool) -> None:
    virtual_cube = None
    moves = []
    hardware = ''
    battery = ''

    orientation_moves = get_orientation_moves(CUBE_ORIENTATION)

    logger.info(
        'CONSUMER: Use "%s" as orientation and "%s" as rotation moves',
        CUBE_ORIENTATION,
        str(orientation_moves),
    )

    while True:
        events = await queue.get()

        if events is None:
            print('\a', end='', flush=True)
            logger.info(
                'CONSUMER: Got message from client about disconnection. '
                'Exiting consumer loop...',
            )
            break

        for event in events:
            event_collector.append(event)
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
                hardware = (
                    f'{ event["hardware_name"] } '
                    f'{ event["hardware_version"] } '
                    f'{ event["software_version"] }'
                )
                if gl_thread and gl_thread.is_alive():
                    gl_thread.set_title(f'{ hardware } { battery }')

            elif event_name == 'battery':
                logger.info(
                    'CONSUMER: Battery: %s%%',
                    event['level'],
                )
                battery = f'{ event["level"]}%'
                if gl_thread and gl_thread.is_alive():
                    gl_thread.set_title(f'{ hardware } { battery }')

            elif event_name == 'gyro':
                logger.info(
                    'CONSUMER: Gyroscope event',
                )
                if gl_thread and gl_thread.is_alive():
                    gl_thread.add_quaternion(
                        event['quaternion'],
                    )
            elif event_name == 'facelets':
                logger.info(
                    'CONSUMER: Facelets received',
                )

                if gl_thread:
                    cube_ready.set()

                if virtual_cube:
                    if virtual_cube.state != event['facelets']:
                        logger.warning('FACELETS DESYNCHRONISED')
                else:
                    virtual_cube = VCube(event['facelets'])

                if show_cube:
                    print_cube(virtual_cube)

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
                    if show_cube:
                        print_cube(virtual_cube)

                if gl_thread and gl_thread.is_alive():
                    direction = 3 if "'" in event['move'] else 1
                    face = event['move'][0]
                    gl_thread.add_move(face, direction)

                algo = parse_moves(moves)
                recon = prettify_moves(
                    humanize_moves(
                        reorient_moves(
                            orientation_moves,
                            algo,
                        ),
                    ),
                )

                logger.info('MOVES: %s', algo)
                logger.info('RECON: %s', recon)

            else:
                logger.info(
                    'CONSUMER: UNKNOWN\n%s',
                    pformat(event),
                )


async def client_cb(queue: asyncio.Queue[Any], time: int, *,
                    use_opengl: bool,
                    cube_reset: bool,
                    gyroscope_enable: bool,
                    gyroscope_disable: bool) -> None:
    bluetooth_interface = BluetoothInterface(queue)

    await bluetooth_interface.__aenter__()  # noqa: PLC2801

    if use_opengl:
        assert bluetooth_interface is not None  # noqa: S101
        assert bluetooth_interface.driver is not None  # noqa: S101

        bluetooth_interface.driver.disable_gyro = False

    await bluetooth_interface.send_command('REQUEST_HARDWARE')
    await bluetooth_interface.send_command('REQUEST_FACELETS')
    await bluetooth_interface.send_command('REQUEST_BATTERY')

    if gyroscope_disable:
        await bluetooth_interface.send_command('REQUEST_DISABLE_GYRO')
    if gyroscope_enable:
        await bluetooth_interface.send_command('REQUEST_ENABLE_GYRO')
    if cube_reset:
        await bluetooth_interface.send_command('REQUEST_RESET')

    logger.info('Free play for %ss', time)
    print('\a', end='', flush=True)
    await asyncio.sleep(time)

    await bluetooth_interface.__aexit__(None, None, None)
    logger.warning('Interface disconnected')


def linear_regression(x_values: list[float],
                      y_values: list[float]) -> tuple[float, float]:
    sum_x = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    sum_xx = 0.0
    sum_yy = 0.0
    n = 0

    for i in range(len(x_values)):
        x = x_values[i]
        y = y_values[i]
        if x is None or y is None:
            continue

        n += 1
        sum_x += x
        sum_y += y
        sum_xy += x * y
        sum_xx += x * x
        sum_yy += y * y

    var_x = n * sum_xx - sum_x * sum_x
    cov_xy = n * sum_xy - sum_x * sum_y

    slope = 1.0 if var_x < 1e-3 else cov_xy / var_x  # noqa: PLR2004
    intercept = 0.0 if n < 1 else sum_y / n - slope * sum_x / n

    return (slope, intercept)


def resume(events: list[dict[str, object]]) -> None:
    cube_timestamps = []
    local_timestamps = []

    for event in events:
        if event['event'] != 'move':
            continue
        cube_timestamps.append(
            event['cube_timestamp'],
        )
        local_timestamps.append(
            event['local_timestamp'].timestamp() * 1000,
        )

    if len(cube_timestamps) < 2:
        return

    # Linear regression: local_timestamps vs cube_timestamps
    # This gives us the mapping from cube time to local time
    # slope ≈ 1.0 means clocks run at same rate
    # If slope > 1.0, cube clock is slower than local clock
    # If slope < 1.0, cube clock is faster than local clock
    slope, _intercept = linear_regression(
        cube_timestamps,
        local_timestamps,
    )

    skew_percent = (slope - 1) * 100
    logger.info('Clock skew: %.4f%%', skew_percent)
    logger.info('Slope: %.6f (1.0 = perfect sync)', slope)


async def run(options: Namespace) -> None:
    event_collector: list[dict[str, object]] = []
    queue: asyncio.Queue[list[dict[str, object]] | None] = asyncio.Queue()
    cube_ready = threading.Event()

    gl_thread = None
    if options.use_opengl:
        gl_thread = CubeGLThread(cube_ready, 800, 600, daemon=True)

    client = client_cb(
        queue, options.time,
        use_opengl=options.use_opengl,
        cube_reset=options.cube_reset,
        gyroscope_enable=options.gyroscope_enable,
        gyroscope_disable=options.gyroscope_disable,
    )
    consumer = consumer_cb(
        queue, cube_ready, gl_thread, event_collector,
        show_cube=options.show_cube,
    )

    try:
        bluetooth_tasks = asyncio.gather(client, consumer)

        if options.use_opengl and gl_thread:
            gl_thread.start()

        with suppress(CubeNotFoundError):
            await bluetooth_tasks
    finally:
        if gl_thread and gl_thread.is_alive():
            gl_thread.stop()
            gl_thread.join(timeout=2)

    resume(event_collector)

    logger.info('Bye bye')


def main() -> None:
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
    parser.add_argument(
        '-g', '--use-opengl',
        action='store_true',
        help=(
            'Enable OpenGL visualization.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '--cube-reset',
        action='store_true',
        help=(
            'Request reset of the cube.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '--gyroscope-enable',
        action='store_true',
        help=(
            'Enable the gyroscope of the cube.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '--gyroscope-disable',
        action='store_true',
        help=(
            'Disable the gyroscope of the cube.\n'
            'Default: False.'
        ),
    )

    args = parser.parse_args(sys.argv[1:])

    asyncio.run(run(args), debug=True)
