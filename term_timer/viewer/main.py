"""Entry point of the ``cube-view`` client."""
import logging
import sys
from argparse import ArgumentTypeError
from argparse import Namespace

from cubing_algs.constants import ORIENTATIONS
from cubing_algs.display.gl import SENSOR_BASIS
from cubing_algs.display.gl import OrientationTracker
from cubing_algs.display.gl import Viewer
from cubing_algs.display.palettes import PALETTES
from cubing_algs.exceptions import CubingAlgsError
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.config import parse_endpoint
from term_timer.viewer.client import CubeView
from term_timer.viewer.host import CubeViewHost
from term_timer.viewer.stream import EventStream

logger = logging.getLogger(__name__)

LOG_FORMAT = '%(levelname)s: %(message)s'

DEFAULT_WINDOW_SIZE = (800, 600)

SIZE_SEPARATOR = 'x'


def parse_stream_endpoint(value: str) -> str:
    """
    Read the endpoint of the stream a ``--endpoint`` argument names.

    The endpoint goes through what the publisher reads its own with, so
    that a tilde written on the command line points at the same socket
    as the one written in the configuration.

    Args:
        value: The argument, as it was typed.

    Returns:
        The endpoint to connect to.

    Raises:
        ArgumentTypeError: When the argument names no transport. A
            subscriber given a broken endpoint would wait in silence
            forever, so it is refused here.

    """
    endpoint = parse_endpoint(value)

    if not endpoint:
        msg = (
            f'"{ value }" is not an endpoint, '
            f'expected TRANSPORT://ADDRESS'
        )
        raise ArgumentTypeError(msg)

    return endpoint


def parse_size(value: str) -> tuple[int, int]:
    """
    Read the size of the window a ``WIDTHxHEIGHT`` argument names.

    Args:
        value: The argument, as it was typed.

    Returns:
        The width and the height, in pixels.

    Raises:
        ArgumentTypeError: When the argument names no size.

    """
    width, separator, height = value.lower().partition(SIZE_SEPARATOR)

    if not separator or not width.isdigit() or not height.isdigit():
        msg = (
            f'"{ value }" is not a size, '
            f'expected WIDTH{ SIZE_SEPARATOR }HEIGHT'
        )
        raise ArgumentTypeError(msg)

    return int(width), int(height)


def build_parser() -> ArgumentParser:
    """
    Describe what the client takes on its command line.

    Returns:
        The parser of the ``cube-view`` arguments.

    """
    parser = ArgumentParser(
        description='Watch a cube in 3D, from the term-timer event stream.',
    )

    parser.add_argument(
        '-e', '--endpoint',
        required=True,
        type=parse_stream_endpoint,
        metavar='ENDPOINT',
        help=(
            'Connect to this ZeroMQ endpoint, one of those the\n'
            '[publisher] section of the configuration binds'
        ),
    )
    parser.add_argument(
        '-o', '--orientation',
        default=CUBE_ORIENTATION,
        choices=sorted(ORIENTATIONS),
        metavar='ORIENTATION',
        help=(
            'Set the cube orientation used.\n'
            f'Default: { CUBE_ORIENTATION }.'
        ),
    )
    parser.add_argument(
        '-p', '--palette',
        default=CUBE_PALETTE,
        choices=sorted(PALETTES),
        metavar='PALETTE',
        help=(
            'Set the colors of the cube.\n'
            f'Default: { CUBE_PALETTE }.'
        ),
    )
    parser.add_argument(
        '-s', '--size',
        type=parse_size,
        default=DEFAULT_WINDOW_SIZE,
        metavar='WIDTHxHEIGHT',
        help=(
            'Set the size of the window.\n'
            f'Default: { DEFAULT_WINDOW_SIZE[0] }'
            f'{ SIZE_SEPARATOR }{ DEFAULT_WINDOW_SIZE[1] }.'
        ),
    )
    parser.add_argument(
        '-a', '--axes',
        action='store_true',
        help=(
            'Show the XYZ axes in the scene.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help=(
            'Measure what a frame costs, and write it in the title.\n'
            'Default: False.'
        ),
    )

    return parser


def build_host(options: Namespace) -> CubeViewHost:
    """
    Assemble the window, the viewer and what translates the stream.

    Args:
        options: The arguments the client was called with.

    Returns:
        The host, ready to be opened.

    """
    tracker = OrientationTracker(basis=SENSOR_BASIS)

    viewer = Viewer(
        cube=VCube(),
        palette=options.palette,
        window_size=options.size,
        debug=options.debug,
        show_axes=options.axes,
        orientation=tracker,
    )

    view = CubeView(viewer, tracker, options.orientation)

    return CubeViewHost(viewer=viewer, title=view.title, view=view)


def main() -> int:
    """
    Open a window on the event stream, and draw the cube it describes.

    Returns:
        Exit code, 1 when no window could be opened.

    """
    options = build_parser().parse_args(sys.argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if options.debug else logging.INFO,
        format=LOG_FORMAT,
    )

    host = build_host(options)
    stream = EventStream(options.endpoint)

    # Read before the window opens: a subscriber connects to a publisher
    # that may not be there yet, and misses nothing while it waits
    stream.start(host.view.dispatch)

    try:
        host.run()
    except CubingAlgsError as error:
        logger.error('Cannot open a window: %s', error)  # noqa: TRY400
        return 1
    except KeyboardInterrupt:
        logger.info('Closing the window')
    finally:
        stream.stop()

    return 0
