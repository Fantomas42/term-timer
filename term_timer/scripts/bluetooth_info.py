"""Bluetooth cube information utility script."""
import asyncio
import json
import logging
import logging.config
import sys
from argparse import Namespace
from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from pprint import pformat
from time import perf_counter
from typing import Any
from typing import Final
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.transform.translate import translate_moves
from cubing_algs.transform.translate import translate_pov_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.arguments import ORIENTATIONS_SORTED
from term_timer.arguments import add_gyroscope_argument
from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import FaceletsEventDict
from term_timer.bluetooth.annotations import GyroConfigEventDict
from term_timer.bluetooth.annotations import GyroEventDict
from term_timer.bluetooth.annotations import HardwareEventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import ROTATION_THRESHOLD
from term_timer.config import USE_GYROSCOPE
from term_timer.constants import LOGGING_DIRECTORY
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND
from term_timer.exceptions import CubeNotFoundError
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_triggers
from term_timer.interface.console import console
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.interface.terminal import Terminal
from term_timer.orientation import get_orientation_moves
from term_timer.publisher import PUBLISHER
from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves
from term_timer.triggers import DEFAULT_TRIGGERS

logger = logging.getLogger(__name__)

LEVEL_COLORS: Final = {
    'DEBUG': '\033[36m',
    'INFO': '\033[32m',
    'WARNING': '\033[33m',
    'ERROR': '\033[31m',
    'CRITICAL': '\033[35m',
}
RESET: Final = '\033[0m'
BOLD: Final = '\x1b[1m'
FG_GREY: Final = '\x1b[38;5;244m'

# A render slower than this leaves the display behind the cube, since the
# consumer draining the event queue is the one paying for it
SHOW_STATE_SLOW_THRESHOLD: Final = 50.0  # In milliseconds

PATTERN_COLORS: Final[dict[str, str]] = {
    'state': '\x1b[38;5;77m',
    'orientation': '\x1b[38;5;80m',
    'permutation': '\x1b[38;5;75m',
    'first_layer': '\x1b[38;5;221m',
    'last_layer': '\x1b[38;5;177m',
    'scramble': '\x1b[38;5;203m',
    'cycle': '\x1b[38;5;255m',
}


class ColoredFormatter(logging.Formatter):
    """Formatter that colorizes the level name using ANSI escape codes."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record with a colorized level name.

        Returns:
            The formatted log string with ANSI color codes on the level name.

        """
        color = LEVEL_COLORS.get(record.levelname, '')
        record = logging.makeLogRecord(record.__dict__)
        record.levelname = f'{color}{record.levelname:<7}{RESET}'
        return super().format(record)


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
            '()': ColoredFormatter,
            'fmt': '%(levelname)s %(message)s',
        },
    },
    'handlers': {
        'fileHandler': {
            'formatter': 'simpleFormatter',
            'level': 'DEBUG',
            'backupCount': 5,
            'maxBytes': 50000000,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGGING_DIRECTORY / 'bt-info.log',
        },
        'consoleHandler': {
            'formatter': 'consoleFormatter',
            'class': 'logging.StreamHandler',
            'level': 'INFO',
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


@dataclass
class SessionReport:
    """
    What a bt-info session collected, logged on the way out.

    The events accumulate for the closing analysis and the JSON export,
    the counters answer the question the tool is launched for: did the
    cube and its reconstruction stay in step. A desynchronisation is
    already logged as a warning when it happens, drowned in the flow;
    counted here, it becomes a figure that can be read at the end.

    The duration is wall time from the session start, pairing included:
    a cube that takes ten seconds to answer is part of what is measured.
    """

    events: list[EventDict] = field(default_factory=list)
    facelets_checked: int = 0
    desynchronisations: int = 0
    started_at: float = field(default_factory=perf_counter)

    @staticmethod
    def summary_line(label: str, value: str) -> str:
        """
        Format a labelled line of the summary block.

        Args:
            label: The name of the figure.
            value: The already formatted figure.

        Returns:
            The line, indented and colorized like the other blocks.

        """
        return f'  {FG_GREY}{label:<14}{RESET} {value}'

    def log_summary(self) -> None:
        """Log the figures of the session as a single block."""
        counts = Counter(event['event'] for event in self.events)
        events = ', '.join(
            f'{BOLD}{count}{RESET} {name}'
            for name, count in counts.most_common()
        ) or 'none'

        lines = [
            self.summary_line(
                'Duration',
                f'{ perf_counter() - self.started_at:.1f}s',
            ),
            self.summary_line('Events', events),
        ]

        if self.facelets_checked:
            lines.append(
                self.summary_line(
                    'Desynchros',
                    f'{BOLD}{self.desynchronisations}{RESET} on '
                    f'{self.facelets_checked} facelets checked',
                ),
            )

        logger.info('Session summary:\n%s', '\n'.join(lines))


def show_cube(cube: VCube) -> None:
    """
    Display the virtual cube state in linear compact format.

    Args:
        cube: The virtual cube to display.

    """
    logger.info(
        'Virtual Cube:\n%s',
        cube.display(
            layout='linear',
            facelet='compact',
        )[:-1],
    )


def show_state(
        raw_moves: list[str],
        orientation_moves: Algorithm,
        cube: VCube | None,
) -> None:
    """
    Display the cube state, measuring how long the rendering takes.

    The whole move list is re-parsed and re-rendered on every call, so the
    cost grows with the session. The consumer is alone to drain the event
    queue: a rendering slower than the move rate makes the display drift
    from the cube without anything saying so. Every render is timed into
    the log file, and a render above SHOW_STATE_SLOW_THRESHOLD is raised
    to a warning.

    Args:
        raw_moves: List of moves in timed notation (e.g., ["R@100", "U@200"]).
        orientation_moves: Algorithm for orientation transformation.
        cube: Virtual cube to update, or None to skip cube display.

    """
    start = perf_counter()

    render_state(raw_moves, orientation_moves, cube)

    elapsed = (perf_counter() - start) * 1000
    logger.log(
        (
            logging.WARNING
            if elapsed > SHOW_STATE_SLOW_THRESHOLD
            else logging.DEBUG
        ),
        'SHOW STATE: %s moves rendered in %.1fms',
        len(raw_moves),
        elapsed,
    )


def render_state(
        raw_moves: list[str],
        orientation_moves: Algorithm,
        cube: VCube | None,
) -> None:
    """
    Render the cube state after applying moves with timing and triggers.

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

    first_time = algo[0].timed
    algo_timed_reformatted = ' '.join(
        f'[b]{ move.untimed }[/b]@{ move.timed - first_time }'
        for move in algo
    )

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
    move_parts = capture.get().replace('\n', '').split(' ')
    moves = '\n'.join(
        ' '.join(move_parts[i:i + 6])
        for i in range(0, len(move_parts), 6)
    )

    logger.info('Raw Moves:\n%s', moves)

    with console.capture() as capture:
        console.print(recon, end='')
    recon = capture.get()

    logger.info('Reconstructed:\n%s', recon)

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

    impacts = algo_translated.impacts()
    if impacts.cubies_patterns:
        category_patterns = impacts.cubies_patterns._asdict()
        lines: list[str] = []
        for category, patterns in category_patterns.items():
            if patterns:
                color = PATTERN_COLORS.get(category, '')
                cat_label = category.replace('_', ' ').title()
                label = f'{FG_GREY}{cat_label:<14}{RESET}'
                values = ', '.join(
                    f'{BOLD}{color}{p}{RESET}' for p in patterns
                )
                lines.append(f'  {label} {values}')
        if lines:
            logger.info('Classification:\n%s', '\n'.join(lines))


def check_state(
        raw_moves: list[str],
        facelets: str,
        cube: VCube,
) -> bool:
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
        report: SessionReport,
        *, show_cube: bool,
        use_gyroscope: bool,
        orientation_faces: CubeOrientation,
        rotation_threshold: float = 75.0) -> None:
    """
    Consumes Bluetooth events and processes cube state updates.

    Processes events from the Bluetooth interface queue including hardware
    information, battery status, facelet updates, gyroscope rotations, and
    move notifications. Updates the virtual cube state as events are
    received.

    Args:
        queue: Event queue from Bluetooth interface. None signals disconnect.
        report: Report accumulating the events and the counters of the
            session.
        show_cube: Whether to display cube state in console.
        use_gyroscope: Whether the gyroscope events are processed.
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
    if use_gyroscope:
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
            SOUND_PLAYER.cube_disconnected()
            logger.info(
                'CONSUMER: Got message from client about disconnection. '
                'Exiting consumer loop...',
            )
            break

        for event in events:
            report.events.append(event)
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
                Terminal.set_title(f'{ hardware } - { battery }')

            elif event_name == 'battery':
                event = cast('BatteryEventDict', event)
                logger.info(
                    'CONSUMER: Battery: %s%%%s',
                    event['level'],
                    ' (charging)' if event['charging_state'] else '',
                )
                battery = f'{ event["level"] }%'
                Terminal.set_title(f'{ hardware } - { battery }')

            elif event_name == 'facelets':
                event = cast('FaceletsEventDict', event)
                logger.info(
                    'CONSUMER: Facelets received',
                )

                if virtual_cube:
                    report.facelets_checked += 1
                    if not check_state(
                            moves, event['facelets'],
                            virtual_cube,
                    ):
                        report.desynchronisations += 1
                else:
                    virtual_cube = VCube(event['facelets'], size=3)
                    if not virtual_cube.is_solved:
                        logger.warning(
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

            elif event_name in {'move', 'move_history'}:
                event = cast('MoveEventDict', event)
                logger.debug(
                    'CONSUMER: Face: %s, Direction: %s, Move: %s%s',
                    event['face'],
                    event['direction'],
                    event['move'],
                    ' (recovered)' if event_name == 'move_history' else '',
                )
                moves.append(f"{ event['move'] }@{ time }")

                show_state(moves, orientation_moves, virtual_cube)

            elif event_name == 'gyro-config':
                event = cast('GyroConfigEventDict', event)
                logger.info(
                    'CONSUMER: Gyroscope configuration: '
                    'supported %s, enabled %s, ready %s',
                    event['gyroscope_supported'],
                    event['gyroscope_enabled'],
                    event['gyroscope_ready'],
                )

            elif event_name == 'disconnect':
                logger.warning('CONSUMER: Cube announced its disconnection')
                SOUND_PLAYER.cube_disconnected()
                return

            else:
                logger.warning(
                    'CONSUMER: %s UNHANDLED\n%s',
                    event_name,
                    pformat(event),
                )


async def client_cb(  # noqa: PLR0913
        queue: asyncio.Queue[list[EventDict] | None],
        time: int,
        filter_name: str,
        *,
        use_gyroscope: bool,
        send_gyro_enable: bool,
        send_gyro_disable: bool,
) -> None:
    """
    Manage Bluetooth connection and send commands to the smart cube.

    Establishes connection to a Bluetooth cube, sends initial information
    requests, applies configuration commands, and maintains the connection
    for the specified duration before disconnecting.

    Args:
        queue: Event queue for receiving Bluetooth events.
        time: Duration in seconds to maintain connection.
        filter_name: Device name filter for connection, or empty string.
        use_gyroscope: Whether the driver reports the gyroscope events.
        send_gyro_enable: Whether to send the cube the command enabling
            its gyroscope.
        send_gyro_disable: Whether to send the cube the command
            disabling its gyroscope.

    """
    bluetooth_interface = BluetoothInterface(queue)

    try:
        await bluetooth_interface.__aenter__(
            filter_name=filter_name,
            use_gyroscope=use_gyroscope,
        )
        SOUND_PLAYER.cube_connected()

        await bluetooth_interface.send_init_commands()

        if send_gyro_disable:
            await bluetooth_interface.send_command('REQUEST_DISABLE_GYRO')
        if send_gyro_enable:
            await bluetooth_interface.send_command('REQUEST_ENABLE_GYRO')
        logger.warning('Free play for %ss', time)
        await asyncio.sleep(time)

        await bluetooth_interface.__aexit__(None, None, None)
        logger.warning('Interface disconnected')
    finally:
        # The sentinel belongs here and not to the interface exit: no cube
        # found means no exit, and the consumer would wait for a cube that
        # never connected until the process ends
        await queue.put(None)


def replay(options: Namespace, *, use_gyroscope: bool) -> None:
    """
    Replays recorded Bluetooth events from a JSON file.

    Loads and processes events from a file, simulating the live event
    stream to analyze gyroscope rotations, moves, and facelet updates
    without requiring an active Bluetooth connection.

    Args:
        options: Command-line arguments containing input file path,
            orientation settings, and rotation threshold.
        use_gyroscope: Whether the recorded gyroscope events are
            processed.

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
            if not use_gyroscope:
                continue

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


def linear_regression(
        x_values: list[float],
        y_values: list[float],
) -> tuple[float, float]:
    """
    Calculate linear regression parameters for two data series.

    Computes the slope and intercept of the best-fit line through the
    provided data points using the least squares method.

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
    n = len(x_values)

    for x, y in zip(x_values, y_values, strict=True):
        sum_x += x
        sum_y += y
        sum_xy += x * y
        sum_xx += x * x

    var_x = n * sum_xx - sum_x * sum_x
    cov_xy = n * sum_xy - sum_x * sum_y

    slope = 1.0 if var_x < 1e-3 else cov_xy / var_x  # noqa: PLR2004
    intercept = 0.0 if n < 1 else sum_y / n - slope * sum_x / n

    return (slope, intercept)


def summarize_events(events: list[EventDict], output: str) -> None:
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


async def run(options: Namespace) -> int:
    """
    Orchestrates the main event loop for Bluetooth monitoring or replay.

    Coordinates the client connection and the event consumer. Handles
    both live Bluetooth sessions and replay mode from recorded event
    files.

    A session that never found a cube is not a session: it says so and
    reports a failure, so that a script calling bt-info can tell an
    inspected cube from an absent one. The closing summary and the
    farewell belong to a session that took place.

    Args:
        options: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 when no cube was found).

    Raises:
        KeyboardInterrupt: When the session is cut short at the
            keyboard, named here so that the farewell says so.
        CancelledError: When the event loop takes the session away,
            which a Ctrl+C looks like from inside a coroutine.

    """
    use_gyroscope = (
        USE_GYROSCOPE
        if options.use_gyroscope is None
        else options.use_gyroscope
    )

    if options.input:
        replay(options, use_gyroscope=use_gyroscope)
        return 0

    report = SessionReport()

    PUBLISHER.start('bt-info')

    queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()

    client = client_cb(
        queue,
        options.time,
        options.filter_name,
        use_gyroscope=use_gyroscope,
        send_gyro_enable=options.send_gyro_enable,
        send_gyro_disable=options.send_gyro_disable,
    )
    consumer = consumer_cb(
        queue,
        report,
        show_cube=options.show_cube,
        use_gyroscope=use_gyroscope,
        orientation_faces=options.orientation,
        rotation_threshold=options.rotation_threshold,
    )

    reason = 'closed'

    try:
        await asyncio.gather(client, consumer)
    except CubeNotFoundError:
        logger.exception(
            'No Bluetooth cube found. '
            'Make sure a cube is powered on and in pairing mode.',
        )
        return 1
    except (KeyboardInterrupt, asyncio.CancelledError):
        reason = 'interrupted'
        raise
    except Exception:
        reason = 'crashed'
        raise
    finally:
        PUBLISHER.stop(reason)

    report.log_summary()
    summarize_events(report.events, options.output)

    logger.info('Bye bye')

    return 0


def main() -> int:
    """
    Entry point for the Bluetooth cube information utility.

    Configures logging, parses command-line arguments, and launches the
    async event processing loop.

    Returns:
        Exit code (0 for success, 1 when no cube was found).

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
    add_gyroscope_argument(parser)
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
    parser.add_argument(
        '--send-gyro-enable',
        action='store_true',
        help=(
            'Send the cube the command enabling its gyroscope.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '--send-gyro-disable',
        action='store_true',
        help=(
            'Send the cube the command disabling its gyroscope.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help=(
            'Show hardware, battery and connection log events.\n'
            'Default: False.'
        ),
    )

    args = parser.parse_args(sys.argv[1:])

    if args.verbose:
        console_handler = next(
            h for h in logging.getLogger('term_timer').handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        )
        console_handler.setLevel(logging.DEBUG)

    return asyncio.run(run(args), debug=True)
