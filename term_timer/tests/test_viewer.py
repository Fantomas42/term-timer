"""
Tests for the ``cube-view`` client.

Nothing here opens a window: the client only translates a stream into
calls on a viewer, so a mocked one - or a real one, which needs no GPU
until a stage is attached to it - is enough. The captures of
``tests/replays/gan_gen2/`` play the part of the cube.
"""
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import create_autospec
from unittest.mock import patch

import zmq
from cubing_algs.display.gl import SENSOR_BASIS
from cubing_algs.display.gl import OrientationTracker
from cubing_algs.display.gl import Viewer
from cubing_algs.display.gl.context import GLContextError
from cubing_algs.vcube import VCube

from term_timer.constants import PROTOCOL_VERSION
from term_timer.viewer import main as entry
from term_timer.viewer.client import WINDOW_TITLE
from term_timer.viewer.client import CubeView
from term_timer.viewer.host import CubeViewHost
from term_timer.viewer.stream import EventStream

REPLAYS = Path(__file__).parent / 'replays' / 'gan_gen2'

# Time left to a subscription to reach the publisher, the "slow joiner"
# of ZeroMQ biting the test before anything else
HANDSHAKE_DELAY = 0.3

# Time given to the reader thread to hear a message
DELIVERY_TIMEOUT = 2.0

ENDPOINT = 'tcp://127.0.0.1:5333'

# Topic of every driver event the viewer listens to
TOPICS = {
    'facelets': 'cube.facelets',
    'move': 'cube.move',
    'move_history': 'cube.history',
    'gyro': 'cube.gyro',
    'hardware': 'cube.hardware',
    'battery': 'cube.battery',
}


def envelope(
        topic: str,
        data: dict[str, Any] | None = None,
        session_id: str = 'a3f1c8d2',
        version: int = PROTOCOL_VERSION,
) -> dict[str, Any]:
    """
    Build an envelope as the publisher writes it.

    Args:
        topic: Topic of the message.
        data: Payload of the message.
        session_id: Identifier of the emitting session.
        version: Version of the protocol spoken.

    Returns:
        The envelope, ready to be dispatched.

    """
    return {
        'v': version,
        'seq': 0,
        'ts': 1755500000.0,
        'src': 'solve',
        'sid': session_id,
        'topic': topic,
        'data': data if data is not None else {},
    }


def capture(name: str) -> list[dict[str, Any]]:
    """
    Read a recorded stream of driver events.

    Args:
        name: Name of the capture file.

    Returns:
        The events, as the driver produced them.

    """
    events: list[dict[str, Any]] = json.loads(
        (REPLAYS / name).read_text(),
    )

    return events


def replay(view: CubeView, name: str) -> None:
    """
    Play a capture through the client, event by event.

    Args:
        view: The client the capture is played into.
        name: Name of the capture file.

    """
    for event in capture(name):
        topic = TOPICS.get(event['event'])

        if topic is None:
            continue

        view.dispatch(
            envelope(
                topic,
                {
                    key: value
                    for key, value in event.items()
                    if key != 'event'
                },
            ),
        )


def run_main(host: MagicMock, stream: MagicMock) -> int:
    """
    Run the entry point on a mocked window and a mocked stream.

    Args:
        host: The host standing in for the window.
        stream: The object standing in for the subscription.

    Returns:
        The exit code of the entry point.

    """
    argv = ['cube-view', '-e', ENDPOINT]

    with (
        patch.object(sys, 'argv', argv),
        patch.object(entry, 'build_host', return_value=host),
        patch.object(entry, 'EventStream', return_value=stream),
    ):
        return entry.main()


class ClientTestCase(unittest.TestCase):
    """Base case wiring a client on a mocked viewer."""

    def setUp(self) -> None:
        """Wire a client on a viewer holding a solved 3x3x3."""
        self.viewer = create_autospec(Viewer, instance=True)
        self.viewer.cube = VCube()
        self.tracker = OrientationTracker(basis=SENSOR_BASIS)
        self.view = CubeView(self.viewer, self.tracker)


class EnvelopeTestCase(ClientTestCase):
    """What the client reads before the payload of a message."""

    def test_unknown_protocol_is_ignored(self) -> None:
        """A message of another protocol version does nothing."""
        self.view.dispatch(envelope('cube.move', {'move': 'R'}, version=2))

        self.viewer.push.assert_not_called()

    def test_unknown_protocol_is_reported_once(self) -> None:
        """A foreign stream is named once, not on every message."""
        with self.assertLogs('term_timer.viewer.client', 'WARNING') as logs:
            self.view.dispatch(envelope('cube.move', version=2))
            self.view.dispatch(envelope('cube.move', version=2))

        self.assertEqual(len(logs.output), 1)

    def test_unknown_topic_is_ignored(self) -> None:
        """A topic the client knows nothing about does nothing."""
        self.view.dispatch(envelope('session.record', {'kind': 'single'}))

        self.viewer.push.assert_not_called()

    def test_session_is_followed(self) -> None:
        """The session identifier of the stream is remembered."""
        self.view.dispatch(envelope('cube.move', {'move': 'R'}))

        self.assertEqual(self.view.session_id, 'a3f1c8d2')

    def test_new_session_starts_over(self) -> None:
        """A publisher that restarted resets the cube and the tracker."""
        self.view.dispatch(envelope('cube.battery', {'level': 80}))
        self.tracker.update(1.0, 0.0, 0.0, 0.0)

        self.view.dispatch(
            envelope('cube.move', {'move': 'R'}, session_id='ffffffff'),
        )

        self.assertEqual(self.view.session_id, 'ffffffff')
        self.assertEqual(self.view.battery, '')
        self.assertIsNone(self.tracker.reference)
        self.assertEqual(self.viewer.cube.state, VCube().state)

    def test_data_that_is_not_an_object_is_ignored(self) -> None:
        """A payload that is not an object is handed over as an empty one."""
        message = envelope('cube.move')
        message['data'] = ['R']

        self.view.dispatch(message)

        self.viewer.push.assert_not_called()


class CubeStateTestCase(ClientTestCase):
    """What the client does with the state the hardware describes."""

    def test_facelets_repose_the_cube(self) -> None:
        """A described state becomes the cube the viewer holds."""
        cube = VCube()
        cube.rotate("R U R' U'")

        self.view.dispatch(
            envelope('cube.facelets', {'facelets': cube.state}),
        )

        self.assertEqual(self.viewer.cube.state, cube.state)

    def test_facelets_are_oriented(self) -> None:
        """A described state is turned the way the cube is looked at."""
        view = CubeView(self.viewer, self.tracker, 'DF')
        cube = VCube()
        cube.rotate("R U R' U'")

        view.dispatch(envelope('cube.facelets', {'facelets': cube.state}))

        self.assertEqual(
            self.viewer.cube.state,
            cube.oriented_copy('DF').state,
        )

    def test_facelets_without_state_are_ignored(self) -> None:
        """A message carrying no state leaves the cube alone."""
        self.view.dispatch(envelope('cube.facelets', {'serial': 1}))

        self.assertEqual(self.viewer.cube.state, VCube().state)

    def test_broken_facelets_are_ignored(self) -> None:
        """A state no cube can be built from leaves the cube alone."""
        self.view.dispatch(envelope('cube.facelets', {'facelets': 'UUU'}))

        self.assertEqual(self.viewer.cube.state, VCube().state)

    def test_another_cube_size_is_ignored(self) -> None:
        """A state of another size is not one this window can show."""
        self.view.dispatch(
            envelope('cube.facelets', {'facelets': VCube(size=2).state}),
        )

        self.assertEqual(self.viewer.cube.size, 3)
        self.assertEqual(self.viewer.cube.state, VCube().state)


class CubeMoveTestCase(ClientTestCase):
    """What the client does with the moves the cube reports."""

    def test_move_is_pushed_as_it_arrives(self) -> None:
        """A move reaches the viewer the moment it is heard."""
        self.view.dispatch(envelope('cube.move', {'move': "R'"}))

        self.viewer.push.assert_called_once_with("R'")

    def test_history_is_pushed_too(self) -> None:
        """A move caught up on is played like any other."""
        self.view.dispatch(envelope('cube.history', {'move': 'U2'}))

        self.viewer.push.assert_called_once_with('U2')

    def test_move_is_read_in_the_display_frame(self) -> None:
        """A move is turned the way the cube is looked at."""
        view = CubeView(self.viewer, self.tracker, 'DF')

        view.dispatch(envelope('cube.move', {'move': 'L'}))

        self.viewer.push.assert_called_once_with('R')

    def test_empty_move_is_ignored(self) -> None:
        """A message carrying no move plays nothing."""
        self.view.dispatch(envelope('cube.move', {'move': ''}))
        self.view.dispatch(envelope('cube.move', {'serial': 3}))

        self.viewer.push.assert_not_called()

    def test_untranslatable_move_is_pushed_as_it_is(self) -> None:
        """A notation nothing can read is handed over untouched."""
        view = CubeView(self.viewer, self.tracker, 'DF')

        view.dispatch(envelope('cube.move', {'move': '[R,'}))

        self.viewer.push.assert_called_once_with('[R,')


class CubeSensorTestCase(ClientTestCase):
    """The gyroscope, and what the cube says about itself."""

    def test_gyro_feeds_the_tracker(self) -> None:
        """A quaternion reaches the tracker the viewer reads."""
        self.view.dispatch(
            envelope(
                'cube.gyro',
                {'quaternion': {'w': 1.0, 'x': 0.0, 'y': 0.0, 'z': 0.0}},
            ),
        )

        self.assertIsNotNone(self.tracker.reference)

    def test_broken_gyro_is_ignored(self) -> None:
        """An incomplete quaternion leaves the tracker alone."""
        self.view.dispatch(envelope('cube.gyro', {'quaternion': {'w': 1.0}}))
        self.view.dispatch(envelope('cube.gyro', {'velocity': {}}))

        self.assertIsNone(self.tracker.reference)

    def test_gyro_without_tracker_is_ignored(self) -> None:
        """A client with no tracker simply drops the quaternions."""
        view = CubeView(self.viewer)

        view.dispatch(
            envelope(
                'cube.gyro',
                {'quaternion': {'w': 1.0, 'x': 0.0, 'y': 0.0, 'z': 0.0}},
            ),
        )

        self.assertIsNone(view.tracker)

    def test_title_names_the_cube(self) -> None:
        """The hardware and the battery are written in the title."""
        self.assertEqual(self.view.title, WINDOW_TITLE)

        self.view.dispatch(
            envelope('cube.hardware', {'hardware_name': 'GANi3'}),
        )
        self.view.dispatch(envelope('cube.battery', {'level': 80}))

        self.assertEqual(self.view.title, f'{ WINDOW_TITLE } · GANi3 · 80%')

    def test_title_says_the_cube_left(self) -> None:
        """A link that drops is told in the title, and told back."""
        self.view.dispatch(
            envelope('cube.link', {'connected': False, 'reason': 'lost'}),
        )

        self.assertEqual(self.view.title, f'{ WINDOW_TITLE } · offline')

        self.view.dispatch(
            envelope('cube.link', {'connected': True, 'reason': 'opened'}),
        )

        self.assertEqual(self.view.title, WINDOW_TITLE)

    def test_nameless_hardware_is_ignored(self) -> None:
        """What says nothing about the cube leaves the title alone."""
        self.view.dispatch(envelope('cube.hardware', {'hardware_name': ''}))
        self.view.dispatch(envelope('cube.battery', {'level': 'high'}))

        self.assertEqual(self.view.title, WINDOW_TITLE)


class CaptureTestCase(unittest.TestCase):
    """The client fed by real captures, into a real viewer."""

    @staticmethod
    def build(orientation: str = '') -> tuple[Viewer, CubeView]:
        """
        Wire a real viewer, which needs no GPU until it is attached.

        Args:
            orientation: The two faces the cube is shown by.

        Returns:
            The viewer and the client driving it.

        """
        tracker = OrientationTracker(basis=SENSOR_BASIS)
        viewer = Viewer(cube=VCube(), orientation=tracker)

        return viewer, CubeView(viewer, tracker, orientation)

    def test_sexy_move_upright(self) -> None:
        """A sexy move done upright is played as a sexy move."""
        viewer, view = self.build('UF')

        replay(view, 'sexy-move-UF.json')

        self.assertEqual(
            [notation for notation, _ in viewer.pending],
            ['R', 'U', "R'", "U'"],
        )

    def test_sexy_move_upside_down(self) -> None:
        """A sexy move done upside down is played as a sexy move."""
        viewer, view = self.build('DF')

        replay(view, 'sexy-move-DF.json')

        self.assertEqual(
            [notation for notation, _ in viewer.pending],
            ['R', 'U', "R'", "U'"],
        )

    def test_moves_keep_the_cadence_they_arrived_at(self) -> None:
        """Every move is stamped, in the order it was heard."""
        viewer, view = self.build('UF')

        replay(view, 'sexy-move-UF.json')

        arrivals = [arrival for _, arrival in viewer.pending]

        self.assertEqual(sorted(arrivals), arrivals)

    def test_rotation_only_capture_pushes_nothing(self) -> None:
        """A capture of a pure rotation only turns the cube."""
        viewer, view = self.build('UF')

        replay(view, 'Y-UF.json')

        self.assertEqual(list(viewer.pending), [])
        self.assertIsNotNone(view.tracker)
        self.assertIsNotNone(view.tracker.reference)  # type: ignore[union-attr]


class CubeViewHostTestCase(unittest.TestCase):
    """The window, and the title the stream writes in it."""

    def setUp(self) -> None:
        """Wire a host on a mocked viewer and a client."""
        self.viewer = create_autospec(Viewer, instance=True)
        self.viewer.cube = VCube()
        self.view = CubeView(self.viewer)
        self.host = CubeViewHost(
            viewer=self.viewer, title=self.view.title, view=self.view,
        )

    def test_frame_is_drawn_by_the_viewer(self) -> None:
        """The frame of the host is the frame of the viewer."""
        self.host.frame(0.016)

        self.viewer.frame.assert_called_once_with(0.016)

    def test_unchanged_title_is_not_written(self) -> None:
        """A title that did not move is not written again."""
        glfw = MagicMock()
        self.host.window = object()

        with patch.dict(sys.modules, {'glfw': glfw}):
            self.host.retitle()

        glfw.set_window_title.assert_not_called()

    def test_new_title_reaches_the_window(self) -> None:
        """A title the stream changed reaches the window bar."""
        glfw = MagicMock()
        self.host.window = object()
        self.view.hardware = 'GANi3'

        with patch.dict(sys.modules, {'glfw': glfw}):
            self.host.retitle()

        glfw.set_window_title.assert_called_once_with(
            self.host.window, f'{ WINDOW_TITLE } · GANi3',
        )

    def test_title_without_a_window_is_only_remembered(self) -> None:
        """A host with no window keeps the title for when it opens."""
        self.view.hardware = 'GANi3'

        self.host.retitle()

        self.assertEqual(self.host.title, f'{ WINDOW_TITLE } · GANi3')


class EventStreamDecodeTestCase(unittest.TestCase):
    """What a pair of frames has to look like to be read."""

    def test_decode_reads_an_envelope(self) -> None:
        """A well formed message gives its envelope back."""
        message = EventStream.decode(
            [b'cube.move', json.dumps(envelope('cube.move')).encode('utf-8')],
        )

        self.assertIsNotNone(message)
        self.assertEqual(message['topic'], 'cube.move')  # type: ignore[index]

    def test_decode_drops_a_lone_frame(self) -> None:
        """A message that is not a topic and a payload is dropped."""
        self.assertIsNone(EventStream.decode([b'cube.move']))

    def test_decode_drops_broken_json(self) -> None:
        """A payload that is not JSON is dropped."""
        self.assertIsNone(EventStream.decode([b'cube.move', b'{']))

    def test_decode_drops_what_is_not_an_object(self) -> None:
        """A payload that is not an envelope is dropped."""
        self.assertIsNone(EventStream.decode([b'cube.move', b'[1]']))


class EventStreamTestCase(unittest.TestCase):
    """The subscription, on real sockets and a real thread."""

    def setUp(self) -> None:
        """Prepare an endpoint of its own and a publisher on it."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        self.endpoint = f'ipc://{ Path(directory.name) / "cube.ipc" }'

        self.context = zmq.Context.instance()
        self.publisher: zmq.Socket[bytes] = self.context.socket(zmq.PUB)
        self.publisher.setsockopt(zmq.LINGER, 0)
        self.publisher.bind(self.endpoint)
        self.addCleanup(self.publisher.close)

        self.stream = EventStream(self.endpoint)
        self.addCleanup(self.stream.stop)

        self.received: list[dict[str, Any]] = []
        self.heard = threading.Event()

    def collect(self, message: dict[str, Any]) -> None:
        """
        Keep a message, and tell the test one arrived.

        Args:
            message: The envelope that was read.

        """
        self.received.append(message)
        self.heard.set()

    def send(self, topic: str) -> None:
        """
        Publish one well formed message on the endpoint under test.

        Args:
            topic: Topic of the message.

        """
        payload = json.dumps(envelope(topic))

        self.publisher.send_multipart(
            [topic.encode('utf-8'), payload.encode('utf-8')],
        )

    def test_receive_without_a_socket(self) -> None:
        """A stream that was never opened reads nothing."""
        self.assertFalse(self.stream.receive(self.collect))

    def test_receive_times_out_on_a_silent_stream(self) -> None:
        """A stream nobody talks on gives the loop its hand back."""
        self.stream.open()

        self.assertFalse(self.stream.receive(self.collect))

    def test_opening_twice_keeps_the_socket(self) -> None:
        """An open stream is not opened a second time."""
        self.stream.open()
        socket = self.stream.socket

        self.stream.open()

        self.assertIs(self.stream.socket, socket)

    def test_messages_reach_the_handler(self) -> None:
        """What is published reaches the handler of the stream."""
        self.stream.start(self.collect)
        time.sleep(HANDSHAKE_DELAY)

        self.send('cube.move')

        self.assertTrue(self.heard.wait(DELIVERY_TIMEOUT))
        self.assertEqual(self.received[0]['topic'], 'cube.move')

    def test_session_topics_are_left_on_the_wire(self) -> None:
        """The subscription filters on the hardware plane alone."""
        self.stream.start(self.collect)
        time.sleep(HANDSHAKE_DELAY)

        self.send('session.record')
        self.send('cube.move')

        self.assertTrue(self.heard.wait(DELIVERY_TIMEOUT))
        self.assertEqual(
            [message['topic'] for message in self.received],
            ['cube.move'],
        )

    def test_a_handler_that_raises_does_not_end_the_stream(self) -> None:
        """A message that cannot be handled costs only that message."""
        calls: list[str] = []

        def handler(message: dict[str, Any]) -> None:
            calls.append(message['topic'])
            self.heard.set()
            msg = 'broken handler'
            raise RuntimeError(msg)

        self.stream.start(handler)
        time.sleep(HANDSHAKE_DELAY)

        with self.assertLogs('term_timer.viewer.stream', 'ERROR'):
            self.send('cube.move')
            self.assertTrue(self.heard.wait(DELIVERY_TIMEOUT))
            self.heard.clear()

            self.send('cube.facelets')
            self.assertTrue(self.heard.wait(DELIVERY_TIMEOUT))

        self.assertEqual(len(calls), 2)

    def test_a_broken_message_is_dropped(self) -> None:
        """What cannot be read never reaches the handler."""
        self.stream.start(self.collect)
        time.sleep(HANDSHAKE_DELAY)

        self.publisher.send_multipart([b'cube.move', b'{'])
        self.send('cube.facelets')

        self.assertTrue(self.heard.wait(DELIVERY_TIMEOUT))
        self.assertEqual(
            [message['topic'] for message in self.received],
            ['cube.facelets'],
        )

    def test_a_socket_error_ends_the_loop(self) -> None:
        """A socket that gives up under the reader ends its loop."""
        self.stream.open()
        self.stream.running = True

        with (
            patch.object(self.stream, 'receive', side_effect=zmq.ZMQError),
            self.assertLogs('term_timer.viewer.stream', 'DEBUG'),
        ):
            self.stream.listen(self.collect)

        self.assertEqual(self.received, [])

    def test_a_closed_socket_ends_the_loop(self) -> None:
        """A socket closed under the reader ends its loop."""
        self.stream.open()
        self.stream.running = True
        self.stream.close()

        self.stream.listen(self.collect)

        self.assertEqual(self.received, [])

    def test_stopping_an_idle_stream(self) -> None:
        """Stopping what was never started is a no-op."""
        self.stream.stop()

        self.assertIsNone(self.stream.socket)
        self.assertIsNone(self.stream.thread)


class MainTestCase(unittest.TestCase):
    """The command line of the client, and what it assembles."""

    def test_parse_size(self) -> None:
        """A size is read whatever the case of its separator."""
        self.assertEqual(entry.parse_size('1024X768'), (1024, 768))

    def test_parse_size_rejects_what_is_not_one(self) -> None:
        """An argument naming no size stops the client."""
        for value in ('1024', '1024x', 'wide x tall', ''):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                entry.build_parser().parse_args(['-e', ENDPOINT, '-s', value])

    def test_endpoint_is_required(self) -> None:
        """A client with no endpoint has nothing to listen to."""
        with self.assertRaises(SystemExit):
            entry.build_parser().parse_args([])

    def test_endpoint_ipc_path_expanded(self) -> None:
        """A tilde on the command line is the home the publisher binds."""
        options = entry.build_parser().parse_args(
            ['-e', 'ipc://~/.term_timer/cube.ipc'],
        )

        self.assertEqual(
            options.endpoint,
            f'ipc://{ Path.home() }/.term_timer/cube.ipc',
        )

    def test_endpoint_rejects_what_is_not_one(self) -> None:
        """An endpoint naming no transport stops the client."""
        for value in ('cube.ipc', '~/.term_timer/cube.ipc', 'ipc://', ''):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                entry.build_parser().parse_args(['-e', value])

    def test_build_host(self) -> None:
        """The options of the client reach the viewer it builds."""
        options = entry.build_parser().parse_args(
            ['-e', ENDPOINT, '-o', 'DF', '-s', '640x480', '-a'],
        )

        host = entry.build_host(options)

        self.assertEqual(host.view.orientation, 'DF')
        self.assertEqual(host.viewer.window_size, (640, 480))
        self.assertTrue(host.viewer.show_axes)
        self.assertIs(host.viewer.orientation, host.view.tracker)
        self.assertEqual(host.title, WINDOW_TITLE)

    def test_main_reads_the_stream_while_the_window_is_open(self) -> None:
        """The stream is read from before the window opens to after."""
        host = MagicMock()
        stream = MagicMock()

        self.assertEqual(run_main(host, stream), 0)

        stream.start.assert_called_once_with(host.view.dispatch)
        host.run.assert_called_once_with()
        stream.stop.assert_called_once_with()

    def test_main_without_a_window(self) -> None:
        """A window that cannot open is reported, not raised."""
        host = MagicMock()
        host.run.side_effect = GLContextError('no context')
        stream = MagicMock()

        with self.assertLogs('term_timer.viewer.main', 'ERROR'):
            self.assertEqual(run_main(host, stream), 1)

        stream.stop.assert_called_once_with()

    def test_main_interrupted(self) -> None:
        """An interruption from the keyboard closes the stream."""
        host = MagicMock()
        host.run.side_effect = KeyboardInterrupt
        stream = MagicMock()

        self.assertEqual(run_main(host, stream), 0)

        stream.stop.assert_called_once_with()
