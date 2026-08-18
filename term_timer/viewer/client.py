"""Translation of the event stream into what the viewer shows."""
import logging
from typing import TYPE_CHECKING
from typing import Any

from cubing_algs.display.gl import OrientationTracker
from cubing_algs.display.gl import Viewer
from cubing_algs.exceptions import CubingAlgsError
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.translate import translate_moves
from cubing_algs.vcube import VCube

from term_timer.constants import PROTOCOL_VERSION
from term_timer.orientation import get_orientation_moves

if TYPE_CHECKING:
    from collections.abc import Callable

    from cubing_algs.algorithm import Algorithm

logger = logging.getLogger(__name__)

# Title of a window that has heard nothing yet, and the pieces the rest
# of it is assembled from as the cube introduces itself
WINDOW_TITLE = 'Cube View'
WINDOW_SEPARATOR = ' · '
WINDOW_OFFLINE = 'offline'


class CubeView:
    """
    What the event stream does to the viewer, topic by topic.

    The whole client is here, and none of it touches a socket or a
    window: an envelope comes in, and a cube is reposed, a move is
    queued or a quaternion is fed to the tracker. The viewer plays the
    moves at the cadence of their arrival, so a move is pushed the very
    moment it is heard and never held back for the next frame.

    The envelope is read before its payload: a session identifier that
    changes means term-timer restarted, and everything told before
    belongs to a cube that is no longer the one talking.
    """

    def __init__(
            self,
            viewer: Viewer,
            tracker: OrientationTracker | None = None,
            orientation: str = '',
    ) -> None:
        """
        Bind a viewer to the stream that will feed it.

        Args:
            viewer: The viewer to drive.
            tracker: The tracker the gyroscope feeds, when the viewer is
                oriented by the cube itself.
            orientation: The two faces the cube is shown by, empty for
                the frame the hardware reports in.

        """
        self.viewer = viewer
        self.tracker = tracker
        self.orientation = orientation

        self.orientation_moves: Algorithm = (
            get_orientation_moves(orientation) if orientation
            else parse_moves('')
        )
        self.translator = translate_moves(self.orientation_moves)

        self.session_id = ''
        self.hardware = ''
        self.battery = ''
        self.connected = True
        # Starts on the version this viewer speaks, so that a foreign
        # stream is reported once and not on every message it sends
        self.version_seen: Any = PROTOCOL_VERSION

        self.handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            'cube.facelets': self.show_facelets,
            'cube.move': self.play_move,
            'cube.history': self.play_move,
            'cube.gyro': self.turn_cube,
            'cube.hardware': self.name_cube,
            'cube.battery': self.charge_cube,
            'cube.link': self.link_cube,
        }

    @property
    def title(self) -> str:
        """
        Tell what the window is called, as the cube introduces itself.

        Returns:
            The title of the window, the plain name until a cube says
            anything about itself.

        """
        parts = [
            part
            for part in (self.hardware, self.battery)
            if part
        ]

        if not self.connected:
            parts.append(WINDOW_OFFLINE)

        return WINDOW_SEPARATOR.join([WINDOW_TITLE, *parts])

    def restart(self, session_id: str) -> None:
        """
        Forget the session that was being watched, and follow a new one.

        A publisher that restarted starts over from a cube nobody
        described yet, so the viewer goes back to a solved one and the
        tracker to no reference at all: keeping the old one would show
        the new cube turned by the drift of the last session.

        Args:
            session_id: Identifier of the session now talking.

        """
        if self.session_id:
            logger.info('Following a new session, starting over')

        self.session_id = session_id
        self.hardware = ''
        self.battery = ''
        self.connected = True

        if self.tracker is not None:
            self.tracker.reset()

        self.viewer.cube = self.rebuild(VCube(size=self.viewer.cube.size))

    def rebuild(self, cube: VCube) -> VCube:
        """
        Turn a cube into the way it is looked at.

        Args:
            cube: The cube as the hardware reports it.

        Returns:
            The cube seen from the configured faces.

        """
        if not self.orientation:
            return cube

        return cube.oriented_copy(self.orientation, full=True)

    def dispatch(self, message: dict[str, Any]) -> None:
        """
        Act on one envelope of the stream.

        Args:
            message: The envelope, as the publisher wrote it.

        """
        version = message.get('v')
        if version != PROTOCOL_VERSION:
            if version != self.version_seen:
                logger.warning(
                    'Ignoring a stream speaking protocol %s, '
                    'this viewer speaks %s',
                    version, PROTOCOL_VERSION,
                )
                self.version_seen = version
            return

        session_id = str(message.get('sid', ''))
        if session_id != self.session_id:
            self.restart(session_id)

        handler = self.handlers.get(str(message.get('topic', '')))
        if handler is None:
            return

        data = message.get('data')
        handler(data if isinstance(data, dict) else {})

    def show_facelets(self, data: dict[str, Any]) -> None:
        """
        Repose the cube on the state the hardware just described.

        Assigning the cube is all it takes: the viewer notices at the
        next frame that it no longer holds the one its animation plays
        on, and reloads by itself.

        Args:
            data: Payload of a ``cube.facelets`` message.

        """
        facelets = data.get('facelets')
        if not isinstance(facelets, str):
            return

        try:
            # Read on the size of the window, which is built once and
            # never changes: a state of another size is one this window
            # cannot show, and it says so rather than guessing
            cube = VCube(facelets, size=self.viewer.cube.size)
        except CubingAlgsError as error:
            logger.debug('Cannot read a cube state: %s', error)
            return

        self.viewer.cube = self.rebuild(cube)

    def play_move(self, data: dict[str, Any]) -> None:
        """
        Queue the move the cube just reported.

        Args:
            data: Payload of a ``cube.move`` or ``cube.history`` message.

        """
        move = data.get('move')
        if not isinstance(move, str) or not move:
            return

        self.viewer.push(self.translate(move))

    def translate(self, move: str) -> str:
        """
        Read a move in the frame the cube is looked at.

        The cube reports what it turns in its own frame, and the state
        it is shown in has been turned away from it: a move played as it
        arrives would turn the wrong face of the cube on the screen.

        Args:
            move: Notation of the move, in the frame of the hardware.

        Returns:
            The notation of the same move, seen from the display.

        """
        if not self.orientation_moves:
            return move

        try:
            return str(self.translator(parse_moves(move)))
        except CubingAlgsError as error:
            logger.debug('Cannot translate move %s: %s', move, error)
            return move

    def turn_cube(self, data: dict[str, Any]) -> None:
        """
        Feed the tracker the orientation the gyroscope reports.

        Nothing is drained and nothing is queued: the tracker holds one
        orientation, the loop reads it at every frame, and a quaternion
        that arrives between two frames is simply the one that is read.

        Args:
            data: Payload of a ``cube.gyro`` message.

        """
        tracker = self.tracker
        quaternion = data.get('quaternion')

        if tracker is None or not isinstance(quaternion, dict):
            return

        try:
            tracker.update(
                float(quaternion['w']),
                float(quaternion['x']),
                float(quaternion['y']),
                float(quaternion['z']),
            )
        except (KeyError, TypeError, ValueError) as error:
            logger.debug('Cannot read a quaternion: %s', error)

    def name_cube(self, data: dict[str, Any]) -> None:
        """
        Remember how the cube calls itself, for the title.

        Args:
            data: Payload of a ``cube.hardware`` message.

        """
        name = data.get('hardware_name')

        if isinstance(name, str) and name:
            self.hardware = name

    def charge_cube(self, data: dict[str, Any]) -> None:
        """
        Remember what the battery of the cube is at, for the title.

        Args:
            data: Payload of a ``cube.battery`` message.

        """
        level = data.get('level')

        if isinstance(level, int):
            self.battery = f'{ level }%'

    def link_cube(self, data: dict[str, Any]) -> None:
        """
        Follow the link with the cube, without ever closing the window.

        A cube that goes away leaves the picture where it was: it is the
        very state the next connection starts from, and a window that
        closed itself would take the session with it.

        Args:
            data: Payload of a ``cube.link`` message.

        """
        self.connected = bool(data.get('connected', True))
