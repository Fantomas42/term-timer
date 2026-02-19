"""Bluetooth cube information utility script."""
import asyncio
import json
import logging
import logging.config
import sys
import threading
from argparse import Namespace
from contextlib import suppress
from pathlib import Path
from pprint import pformat
from typing import Any
from typing import Final
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.transform.translate import translate_moves
from cubing_algs.transform.translate import translate_pov_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.arguments import ORIENTATIONS_SORTED
from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDict
from term_timer.bluetooth.annotations import GyroEventDict
from term_timer.bluetooth.annotations import HardwareEventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import ROTATION_THRESHOLD
from term_timer.config import USE_GYROSCOPE
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND
from term_timer.constants import Face
from term_timer.exceptions import CubeNotFoundError
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_triggers
from term_timer.interface.console import console
from term_timer.interface.terminal import Terminal
from term_timer.logger import LOGGING_DIR
from term_timer.opengl.thread import CubeGLThread
from term_timer.orientation import get_orientation_moves
from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves
from term_timer.triggers import DEFAULT_TRIGGERS

logger = logging.getLogger(__name__)

Path(LOGGING_DIR).mkdir(parents=True, exist_ok=True)

LOGGING_CONF: Final = {
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


def show_cube(cube: VCube) -> None:
    """
    Display the virtual cube state in linear compact format.

    Args:
        cube: The virtual cube to display.

    """
    logger.info(
        'Virtual Cube:\n%s',
        cube.display(
            mode='linear',
            facelet='compact',
        )[:-1],
    )


def show_state(raw_moves: list[str], orientation_moves: Algorithm,
               cube: VCube | None) -> None:
    """
    Display the cube state after applying moves with timing and triggers.

    Parses raw moves, translates them based on orientation, and displays
    both the timed move sequence and the reconstructed solution with
    trigger highlighting. Updates the virtual cube state if provided.

    Args:
        raw_moves: List of moves in timed notation (e.g., ["R@100", "U@200"]).
        orientation_moves: Algorithm for orientation transformation.
        cube: Virtual cube to update, or None to skip cube display.

    """
    if not raw_moves:
        if cube:
            cube_rotated = cube.copy()
            cube_rotated.rotate(orientation_moves)
            show_cube(cube_rotated)
        return

    algo = parse_moves(raw_moves)
    algo_translated = translate_moves(orientation_moves)(algo)

    algo_timed_reformatted = ''
    first_time = algo[0].timed
    for move in algo:
        algo_timed_reformatted += (
            f'{ move.untimed }@{ move.timed - first_time } '
        )
    algo_timed_reformatted = algo_timed_reformatted.strip()

    moves = format_alg_moves(
        algo_timed_reformatted,
    )

    recon = format_alg_triggers(
        format_alg_moves(
            str(
                prettify_moves(
                    humanize_moves(
                        algo_translated,
                    ),
                ),
            ),
        ),
        DEFAULT_TRIGGERS,
    )

    with console.capture() as capture:
        console.print(moves, end='')
    moves = capture.get()

    logger.info('MOVES: %s', moves)

    with console.capture() as capture:
        console.print(recon, end='')
    recon = capture.get()

    logger.info('RECON: %s', recon)

    if cube:
        cube_rotated = cube.copy()
        cube_rotated.rotate(orientation_moves)
        cube_rotated.rotate(
            algo_translated.transform(
                untime_moves,
                translate_pov_moves,
            ),
        )
        show_cube(cube_rotated)


def check_state(raw_moves: list[str], facelets: str,
                cube: VCube) -> bool:
    """
    Verify cube state synchronization between moves and facelets.

    Applies the move sequence to a copy of the cube and compares the
    resulting state with the provided facelet string to detect
    desynchronization.

    Args:
        raw_moves: List of moves in timed notation to apply.
        facelets: Expected facelet string representation.
        cube: Virtual cube to verify against.

    Returns:
        True if states match, False if desynchronized.

    """
    algo = parse_moves(raw_moves)

    cube_rotated = cube.copy()
    cube_rotated.rotate(
        algo.transform(
            untime_moves,
            translate_pov_moves,
        ),
    )

    if cube_rotated.state != facelets:
        logger.warning('FACELETS DESYNCHRONISED !')
        logger.debug('MEM: %s', cube_rotated.state)
        logger.debug('BLE: %s', facelets)
        return False

    return True


async def consumer_cb(  # noqa: C901, PLR0912, PLR0913, PLR0915
        queue: asyncio.Queue[list[EventDict] | None],
        cube_ready: threading.Event,
        gl_thread: CubeGLThread | None,
        event_collector: list[EventDict],
        *, show_cube: bool,
        orientation_faces: str,
        rotation_threshold: float = 75.0) -> None:
    """
    Consumes Bluetooth events and processes cube state updates.

    Processes events from the Bluetooth interface queue including hardware
    information, battery status, facelet updates, gyroscope rotations, and
    move notifications. Updates the virtual cube state and OpenGL display
    as events are received.

    Args:
        queue: Event queue from Bluetooth interface. None signals disconnect.
        cube_ready: Event to signal when cube state is initialized.
        gl_thread: Optional OpenGL visualization thread.
        event_collector: List to accumulate all received events.
        show_cube: Whether to display cube state in console.
        orientation_faces: Two-character orientation specification (e.g., "UF").
        rotation_threshold: Minimum rotation angle in degrees for detection.
            Defaults to 75.0.

    """
    virtual_cube: VCube | None = None
    moves: list[str] = []
    hardware = ''
    battery = ''

    rotation_detector: RotationDetector | None = None
    orientation_moves = get_orientation_moves(orientation_faces)

    logger.info(
        'CONSUMER: Use "%s" as orientation faces and "%s" as orientation moves',
        orientation_faces,
        orientation_moves,
    )
    if USE_GYROSCOPE:
        rotation_detector = RotationDetector(
            rotation_threshold=rotation_threshold,
        )
        logger.info(
            'CONSUMER: Use %.1f° threshold for rotation detection',
            rotation_threshold,
        )

    while True:
        events = await queue.get()

        if events is None:
            Terminal.beep()
            logger.info(
                'CONSUMER: Got message from client about disconnection. '
                'Exiting consumer loop...',
            )
            break

        for event in events:
            event_collector.append(event)
            event_name = event['event']
            time = int(event['clock'] / MS_TO_NS_FACTOR)

            if event_name == 'hardware':
                event = cast('HardwareEventDict', event)
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
                event = cast('BatteryEventDict', event)
                logger.info(
                    'CONSUMER: Battery: %s%%%s',
                    event['level'],
                    ' (charging)' if event['charging_state'] else '',
                )
                battery = f'{ event["level"] }%'
                if gl_thread and gl_thread.is_alive():
                    gl_thread.set_title(f'{ hardware } { battery }')

            elif event_name == 'facelets':
                event = cast('FaceletsEventDict', event)
                logger.info(
                    'CONSUMER: Facelets received',
                )

                if gl_thread:
                    gl_thread.set_state(event['state'])
                    cube_ready.set()

                if virtual_cube:
                    check_state(
                        moves, event['facelets'],
                        virtual_cube,
                    )
                else:
                    virtual_cube = VCube(event['facelets'], size=3)
                    if not virtual_cube.is_solved:
                        logger.info(
                            'CONSUMER: Facelets are not in solved state',
                        )

                if show_cube:
                    show_state(moves, orientation_moves, virtual_cube)

            elif event_name == 'gyro':
                if not rotation_detector:
                    continue

                event = cast('GyroEventDict', event)

                rotation_result = rotation_detector.process_gyro_event(
                    event['quaternion'],
                )

                if rotation_result:
                    logger.info(
                        'CONSUMER: Rotation: %s, Angle: %.1f°',
                        rotation_result['rotation'],
                        rotation_result['angle_deg'],
                    )
                    moves.append(f"{ rotation_result['rotation'] }@{ time }")

                    show_state(moves, orientation_moves, virtual_cube)

                if gl_thread and gl_thread.is_alive():
                    gl_thread.add_quaternion(
                        event['quaternion'],
                    )

            elif event_name == 'move':
                event = cast('MoveEventDict', event)
                logger.info(
                    'CONSUMER: Face: %s, Direction: %s, Move: %s',
                    event['face'],
                    event['direction'],
                    event['move'],
                )
                moves.append(f"{ event['move'] }@{ time }")

                show_state(moves, orientation_moves, virtual_cube)

                if gl_thread and gl_thread.is_alive():
                    direction = 3 if "'" in event['move'] else 1
                    face = cast('Face', event['move'][0])
                    gl_thread.add_move(face, direction)

            else:
                logger.info(
                    'CONSUMER: %s UNHANDLED\n%s',
                    event_name,
                    pformat(event),
                )


async def client_cb(  # noqa: PLR0913
        queue: asyncio.Queue[list[EventDict] | None],
        time: int, filter_name: str, *,
        cube_reset: bool,
        gyroscope_enable: bool,
        gyroscope_disable: bool) -> None:
    """
    Manage Bluetooth connection and send commands to the smart cube.

    Establishes connection to a Bluetooth cube, sends initial information
    requests, applies configuration commands, and maintains the connection
    for the specified duration before disconnecting.

    Args:
        queue: Event queue for receiving Bluetooth events.
        time: Duration in seconds to maintain connection.
        filter_name: Device name filter for connection, or empty string.
        cube_reset: Whether to request cube reset.
        gyroscope_enable: Whether to enable gyroscope data streaming.
        gyroscope_disable: Whether to disable gyroscope data streaming.

    """
    bluetooth_interface = BluetoothInterface(queue)

    await bluetooth_interface.__aenter__(
        filter_name=filter_name,
        use_gyroscope=True,
    )

    await bluetooth_interface.send_command('REQUEST_FACELETS')
    await bluetooth_interface.send_command('REQUEST_HARDWARE')
    await bluetooth_interface.send_command('REQUEST_BATTERY')

    if gyroscope_disable:
        await bluetooth_interface.send_command('REQUEST_DISABLE_GYRO')
    if gyroscope_enable:
        await bluetooth_interface.send_command('REQUEST_ENABLE_GYRO')
    if cube_reset:
        await bluetooth_interface.send_command('REQUEST_RESET')
    else:
        logger.info('Free play for %ss', time)
        Terminal.beep()
        await asyncio.sleep(time)

    await bluetooth_interface.__aexit__(None, None, None)
    logger.warning('Interface disconnected')


def replay(options: Namespace) -> None:
    """
    Replays recorded Bluetooth events from a JSON file.

    Loads and processes events from a file, simulating the live event
    stream to analyze gyroscope rotations, moves, and facelet updates
    without requiring an active Bluetooth connection.

    Args:
        options: Command-line arguments containing input file path,
            orientation settings, and rotation threshold.

    """
    file_path = Path(options.input).resolve()
    with file_path.open(encoding='utf-8') as f:
        events = json.load(f)

    virtual_cube: VCube | None = None

    show_cube = options.show_cube
    orientation_moves = get_orientation_moves(options.orientation)
    rotation_detector = RotationDetector(
        rotation_threshold=options.rotation_threshold,
    )

    logger.info(
        'REPLAY: Use "%s" as orientation faces and "%s" as orientation moves',
        options.orientation,
        orientation_moves,
    )
    logger.info(
        'REPLAY: Use %.1f° threshold for rotation detection',
        options.rotation_threshold,
    )

    moves: list[str] = []

    for event in events:
        event_name = event['event']
        time = int(event['clock'] / MS_TO_NS_FACTOR)

        if event_name == 'gyro':
            event = cast('GyroEventDict', event)

            rotation_result = rotation_detector.process_gyro_event(
                event['quaternion'],
            )

            if rotation_result:
                logger.info(
                    'REPLAY: Rotation: %s, Angle: %.1f°',
                    rotation_result['rotation'],
                    rotation_result['angle_deg'],
                )
                moves.append(f"{ rotation_result['rotation'] }@{ time }")

                show_state(moves, orientation_moves, virtual_cube)

        elif event_name == 'move':
            event = cast('MoveEventDict', event)
            logger.info(
                'REPLAY: Face: %s, Direction: %s, Move: %s',
                event['face'],
                event['direction'],
                event['move'],
            )
            moves.append(f"{ event['move'] }@{ time }")

            show_state(moves, orientation_moves, virtual_cube)

        elif event_name == 'facelets':
            event = cast('FaceletsEventDict', event)
            logger.info(
                'REPLAY: Facelets: %s',
                event['facelets'],
            )

            if show_cube:
                virtual_cube = VCube(event['facelets'], size=3)
                show_state(moves, orientation_moves, virtual_cube)


def linear_regression(x_values: list[float],
                      y_values: list[float]) -> tuple[float, float]:
    """
    Calculate linear regression parameters for two data series.

    Computes the slope and intercept of the best-fit line through the
    provided data points using the least squares method. Handles None
    values by skipping them in the calculation.

    Args:
        x_values: Independent variable data points.
        y_values: Dependent variable data points.

    Returns:
        Tuple of (slope, intercept) for the linear regression line.

    """
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


def resume(events: list[EventDict], output: str) -> None:
    """
    Analyzes event timing and optionally exports to JSON.

    Processes collected events to compute clock skew between cube and local
    timestamps, calculates gyroscope sampling frequency, and exports events
    to a JSON file if an output path is provided.

    Args:
        events: List of all events collected during the session.
        output: Output file path for JSON export, or empty string to skip.

    """
    cube_timestamps: list[float] = []
    local_timestamps: list[float] = []
    gyro_clocks: list[int] = []

    replay = []

    for event in events:
        data: dict[str, Any] = {}

        if event['event'] == 'move':
            event = cast('MoveEventDict', event)
            if (
                event['cube_timestamp'] is None
                or event['local_timestamp'] is None
            ):
                continue

            cube_timestamps.append(
                event['cube_timestamp'],
            )
            local_timestamps.append(
                event['local_timestamp'].timestamp() * 1000,
            )

            data.update(event)
            data['timestamp'] = data['timestamp'].timestamp()
            data['local_timestamp'] = data['local_timestamp'].timestamp()
            replay.append(data)

        elif event['event'] == 'gyro':
            event = cast('GyroEventDict', event)
            gyro_clocks.append(event['clock'])

            data.update(event)
            data['timestamp'] = data['timestamp'].timestamp()
            replay.append(data)

        elif event['event'] == 'facelets':
            event = cast('FaceletsEventDict', event)
            data.update(event)
            data['timestamp'] = data['timestamp'].timestamp()
            replay.append(data)

    if len(cube_timestamps) > 2:
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

    if len(gyro_clocks) > 2:
        duration = gyro_clocks[-1] - gyro_clocks[0]
        frequency = len(gyro_clocks) / (duration / SECOND)
        logger.info('Gyro frequency: %.4fHz', frequency)

    if output:
        output_path = Path(output).resolve()
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(replay, f, indent=2)


async def run(
    options: Namespace,
    gl_thread: CubeGLThread | None,
    cube_ready: threading.Event,
) -> None:
    """
    Orchestrates the main event loop for Bluetooth monitoring or replay.

    Coordinates the client connection, event consumer, and optional OpenGL
    visualization. Handles both live Bluetooth sessions and replay mode
    from recorded event files.

    Args:
        options: Parsed command-line arguments.
        gl_thread: Optional OpenGL visualization thread.
        cube_ready: Event to synchronize cube state initialization.

    """
    if options.input:
        replay(options)
        return

    event_collector: list[EventDict] = []
    queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()

    client = client_cb(
        queue,
        options.time,
        options.filter_name,
        cube_reset=options.cube_reset,
        gyroscope_enable=options.gyroscope_enable,
        gyroscope_disable=options.gyroscope_disable,
    )
    consumer = consumer_cb(
        queue,
        cube_ready,
        gl_thread,
        event_collector,
        show_cube=options.show_cube,
        orientation_faces=options.orientation,
        rotation_threshold=options.rotation_threshold,
    )

    try:
        with suppress(CubeNotFoundError):
            await asyncio.gather(client, consumer)
    finally:
        if gl_thread and gl_thread.is_alive():
            gl_thread.stop()
            gl_thread.join(timeout=2)

    resume(event_collector, options.output)

    logger.info('Bye bye')


def main() -> None:
    """
    Entry point for the Bluetooth cube information utility.

    Configures logging, parses command-line arguments, initializes the
    optional OpenGL visualization thread, and launches the async event
    processing loop.
    """
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
        '-f', '--filter-name',
        type=str,
        metavar='FILTER',
        help='Filter device name to connect',
    )
    parser.add_argument(
        '-i', '--input',
        type=str,
        metavar='EVENTS_FILE',
        help='Input events file to replay (optional).',
    )
    parser.add_argument(
        '-r', '--output',
        type=str,
        metavar='EVENTS_FILE',
        help='Output events file (optional).',
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
        '-o', '--orientation',
        default=CUBE_ORIENTATION,
        choices=ORIENTATIONS_SORTED,
        metavar='ORIENTATION',
        help=(
            'Set the cube orientation used.\n'
            f'Default: { CUBE_ORIENTATION }.'
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
    parser.add_argument(
        '--rotation-threshold',
        type=float,
        default=ROTATION_THRESHOLD,
        metavar='DEGREES',
        help=(
            'Rotation detection threshold in degrees.\n'
            f'Default: { ROTATION_THRESHOLD }.'
        ),
    )

    args = parser.parse_args(sys.argv[1:])

    # Create and start GL thread before async loop to avoid blocking warnings
    gl_thread = None
    cube_ready = threading.Event()
    if args.use_opengl:
        gl_thread = CubeGLThread(
            cube_ready,
            args.orientation,
            800,
            600,
            daemon=True,
        )
        gl_thread.start()

    asyncio.run(run(args, gl_thread, cube_ready), debug=True)
