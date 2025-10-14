import asyncio
import logging
import logging.config
import math
import sys
import threading
from argparse import Namespace
from contextlib import suppress
from dataclasses import dataclass
from pprint import pformat
from typing import TypedDict
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.bluetooth.types import BatteryEventDict
from term_timer.bluetooth.types import EventDict
from term_timer.bluetooth.types import FaceletsEventDict
from term_timer.bluetooth.types import GyroEventDict
from term_timer.bluetooth.types import HardwareEventDict
from term_timer.bluetooth.types import MoveEventDict
from term_timer.bluetooth.types import QuaternionDict
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

# Quaternion math constants for rotation detection
QUATERNION_EPSILON = 1e-10
NO_ROTATION_THRESHOLD = 0.9999


class RotationResult(TypedDict):
    """Result of rotation detection."""
    rotation: str
    angle_deg: float
    confidence: float


@dataclass
class Quaternion:
    w: float
    x: float
    y: float
    z: float

    @classmethod
    def from_dict(cls, q: QuaternionDict) -> 'Quaternion':
        """Create quaternion from dict with coordinate transform.

        Applies the same Y↔Z swap and Y negation used in the OpenGL cube
        visualization to ensure detected rotations match the display.
        """
        qw, qx, qy, qz = q['w'], q['x'], q['y'], q['z']
        # Apply coordinate system transformation matching OpenGL cube
        # This swaps Y and Z axes and negates Y to match display orientation
        return cls(w=qw, x=qx, y=qz, z=-qy)

    def conjugate(self) -> 'Quaternion':
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def multiply(self, other: 'Quaternion') -> 'Quaternion':
        w = (
            self.w * other.w
            - self.x * other.x
            - self.y * other.y
            - self.z * other.z
        )
        x = (
            self.w * other.x
            + self.x * other.w
            + self.y * other.z
            - self.z * other.y
        )
        y = (
            self.w * other.y
            - self.x * other.z
            + self.y * other.w
            + self.z * other.x
        )
        z = (
            self.w * other.z
            + self.x * other.y
            - self.y * other.x
            + self.z * other.w
        )
        return Quaternion(w, x, y, z)

    def normalize(self) -> 'Quaternion':
        norm = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if norm < QUATERNION_EPSILON:
            return Quaternion(1.0, 0.0, 0.0, 0.0)
        return Quaternion(
            self.w / norm,
            self.x / norm,
            self.y / norm,
            self.z / norm,
        )

    def to_axis_angle(self) -> tuple[tuple[float, float, float], float]:
        """Convert quaternion to axis-angle representation."""
        # Normalize first
        q = self.normalize()

        # Handle the case where w is very close to 1 (no rotation)
        if abs(q.w) > NO_ROTATION_THRESHOLD:
            return ((1.0, 0.0, 0.0), 0.0)

        # Calculate angle
        angle = 2 * math.acos(max(-1.0, min(1.0, q.w)))

        # Calculate axis
        s = math.sqrt(1 - q.w * q.w)
        if s < QUATERNION_EPSILON:
            # Axis is arbitrary for no rotation
            return ((1.0, 0.0, 0.0), 0.0)

        axis = (q.x / s, q.y / s, q.z / s)
        return (axis, angle)


class RotationDetector:
    """Detects cube rotations from gyroscope quaternion data."""

    def __init__(
        self,
        rotation_threshold: float = 70.0,
        time_window: float = 0.5,
    ) -> None:
        self.rotation_threshold = rotation_threshold
        self.time_window = time_window
        self.last_quaternion: Quaternion | None = None
        self.last_timestamp: float = 0.0
        self.rotations: list[str] = []

    def process_gyro_event(
        self,
        quaternion_dict: QuaternionDict,
        timestamp: float,
    ) -> RotationResult | None:
        """Process a gyro event and return detected rotation if any."""
        current_quat = Quaternion.from_dict(quaternion_dict)

        if self.last_quaternion is None:
            self.last_quaternion = current_quat
            self.last_timestamp = timestamp
            return None

        # Check if enough time has passed
        time_delta = timestamp - self.last_timestamp
        if time_delta < self.time_window:
            return None

        # Calculate rotation between last and current quaternion
        rotation_result = self.calculate_rotation(
            self.last_quaternion,
            current_quat,
        )

        # Update state
        self.last_quaternion = current_quat
        self.last_timestamp = timestamp

        if rotation_result:
            self.rotations.append(rotation_result['rotation'])

        return rotation_result

    def calculate_rotation(
        self,
        q1: Quaternion,
        q2: Quaternion,
    ) -> RotationResult | None:
        """Calculate rotation between two quaternions."""
        # Calculate relative rotation: q_rel = q2 * q1^-1
        q_rel = q2.multiply(q1.conjugate()).normalize()

        # Convert to axis-angle
        axis, angle = q_rel.to_axis_angle()
        angle_deg = math.degrees(angle)

        # Check if rotation exceeds threshold
        if abs(angle_deg) < self.rotation_threshold:
            return None

        # Determine which axis is dominant
        ax, ay, az = axis
        abs_x, abs_y, abs_z = abs(ax), abs(ay), abs(az)

        # Determine rotation type based on dominant axis
        rotation_type = None
        confidence = 0.0

        if abs_x > abs_y and abs_x > abs_z:
            # X-axis rotation
            rotation_type = 'x' if ax > 0 else "x'"
            confidence = abs_x
        elif abs_y > abs_x and abs_y > abs_z:
            # Y-axis rotation
            rotation_type = 'y' if ay > 0 else "y'"
            confidence = abs_y
        elif abs_z > abs_x and abs_z > abs_y:
            # Z-axis rotation
            rotation_type = 'z' if az > 0 else "z'"
            confidence = abs_z

        if rotation_type is None:
            return None

        # Check if it's a double rotation (close to 180 degrees)
        if abs(abs(angle_deg) - 180) < 30:
            if rotation_type.endswith("'"):
                rotation_type = rotation_type[0] + '2'
            else:
                rotation_type += '2'

        return {
            'rotation': rotation_type,
            'angle_deg': angle_deg,
            'confidence': confidence,
        }


def print_cube(cube: VCube) -> None:
    cube.show(
        orientation=CUBE_ORIENTATION,
        mode='linear',
        facelet='compact',
    )


def print_moves(moves: list[str], orientation_moves: Algorithm) -> None:
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


async def consumer_cb(queue: asyncio.Queue[list[EventDict] | None],
                      cube_ready: threading.Event,
                      gl_thread: CubeGLThread | None,
                      event_collector: list[EventDict],
                      *, show_cube: bool,
                      rotation_threshold: float = 70.0,
                      time_window: float = 0.5) -> None:
    virtual_cube: VCube | None = None
    moves: list[str] = []
    hardware = ''
    battery = ''

    orientation_moves = get_orientation_moves(CUBE_ORIENTATION)

    # Initialize rotation detector
    rotation_detector = RotationDetector(
        rotation_threshold=rotation_threshold,
        time_window=time_window,
    )

    logger.info(
        'CONSUMER: Use "%s" as orientation faces and "%s" as orientation moves',
        CUBE_ORIENTATION,
        str(orientation_moves),
    )
    logger.info(
        'CONSUMER: Use threshold: %.1f° and time window: %.1fs '
        'for rotation detection',
        rotation_threshold,
        time_window,
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
                event = cast(HardwareEventDict, event)
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
                event = cast(BatteryEventDict, event)
                logger.info(
                    'CONSUMER: Battery: %s%%',
                    event['level'],
                )
                battery = f'{ event["level"] }%'
                if gl_thread and gl_thread.is_alive():
                    gl_thread.set_title(f'{ hardware } { battery }')

            elif event_name == 'facelets':
                event = cast(FaceletsEventDict, event)
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

            elif event_name == 'gyro':
                event = cast(GyroEventDict, event)

                timestamp = event['timestamp'].timestamp()
                rotation_result = rotation_detector.process_gyro_event(
                    event['quaternion'],
                    timestamp,
                )

                if rotation_result:
                    logger.info(
                        'CONSUMER: Rotation: %s, Angle: %.1f°, '
                        'Confidence: %.2f%%',
                        rotation_result['rotation'],
                        rotation_result['angle_deg'],
                        rotation_result['confidence'] * 100,
                    )

                    # Apply rotation
                    moves.append(rotation_result['rotation'])
                    print_moves(moves, orientation_moves)

                    if virtual_cube:
                        virtual_cube.rotate(rotation_result['rotation'])
                        if show_cube:
                            print_cube(virtual_cube)

                if gl_thread and gl_thread.is_alive():
                    gl_thread.add_quaternion(
                        event['quaternion'],
                    )

            elif event_name == 'move':
                event = cast(MoveEventDict, event)
                logger.info(
                    'CONSUMER: Face: %s, Direction: %s, Move: %s',
                    event['face'],
                    event['direction'],
                    event['move'],
                )
                moves.append(event['move'])
                print_moves(moves, orientation_moves)

                if virtual_cube:
                    virtual_cube.rotate(event['move'])
                    if show_cube:
                        print_cube(virtual_cube)

                if gl_thread and gl_thread.is_alive():
                    direction = 3 if "'" in event['move'] else 1
                    face = event['move'][0]
                    gl_thread.add_move(face, direction)

            else:
                logger.info(
                    'CONSUMER: UNKNOWN\n%s',
                    pformat(event),
                )


async def client_cb(queue: asyncio.Queue[list[EventDict] | None], time: int, *,
                    cube_reset: bool,
                    gyroscope_enable: bool,
                    gyroscope_disable: bool) -> None:
    bluetooth_interface = BluetoothInterface(queue)

    await bluetooth_interface.__aenter__()  # noqa: PLC2801

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


def resume(events: list[EventDict]) -> None:
    cube_timestamps: list[float] = []
    local_timestamps: list[float] = []

    for event in events:
        if event['event'] != 'move':
            continue

        event = cast(MoveEventDict, event)
        if event['cube_timestamp'] is None or event['local_timestamp'] is None:
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
    event_collector: list[EventDict] = []
    queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()
    cube_ready = threading.Event()

    gl_thread = None
    if options.use_opengl:
        gl_thread = CubeGLThread(cube_ready, 800, 600, daemon=True)

    client = client_cb(
        queue,
        options.time,
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
        rotation_threshold=options.rotation_threshold,
        time_window=options.rotation_window,
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
    parser.add_argument(
        '--rotation-threshold',
        type=float,
        default=70.0,
        metavar='DEGREES',
        help=('Rotation detection threshold in degrees.\nDefault: 70.0.'),
    )
    parser.add_argument(
        '--rotation-window',
        type=float,
        default=0.5,
        metavar='SECONDS',
        help=('Time window for rotation detection in seconds.\nDefault: 0.5.'),
    )

    args = parser.parse_args(sys.argv[1:])

    asyncio.run(run(args), debug=True)
