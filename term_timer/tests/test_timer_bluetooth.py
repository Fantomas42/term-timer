"""
Bluetooth Timer scenario tests.

Drives Timer.start() with a simulated Bluetooth cube, reusing the fake
BT helpers from test_trainer_bluetooth. Focuses on the interaction
between keyboard start/stop and the Bluetooth cube state.
"""
import asyncio
import logging
import unittest
from datetime import UTC
from datetime import datetime
from random import Random
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import patch

from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import BatteryEventDict
from term_timer.bluetooth.annotations import DisconnectEventDict
from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import GyroConfigEventDict
from term_timer.bluetooth.annotations import HardwareEventNameOnlyDict
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.config import CubeDevice
from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.constants import SolveFlag
from term_timer.exceptions import CubeDisconnectedError
from term_timer.exceptions import CubeNotFoundError
from term_timer.logger import spawn
from term_timer.solve import Solve
from term_timer.tests.test_trainer_bluetooth import FakeBluetoothClient
from term_timer.tests.test_trainer_bluetooth import FakeBluetoothInterface
from term_timer.tests.test_trainer_bluetooth import make_move_event
from term_timer.tests.test_trainer_bluetooth import wait_until
from term_timer.timer import Timer

if TYPE_CHECKING:
    from bleak import BleakClient


def build_timer(scramble: str) -> Timer:
    """
    Build a Timer with a fake Bluetooth cube and a fixed raw scramble.

    Mirrors what bluetooth_connect() wires up in production: a real
    asyncio.Queue, a solved BT cube and a truthy interface stub.

    Args:
        scramble: Raw scramble string used instead of a generated one.

    Returns:
        Configured Timer ready for testing.

    """
    instance = Timer(
        cube_size=3,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble=scramble,
        scrambles=[],
        session='test',
        free_play=False,
        show_cube=False,
        show_highlights=False,
        show_doctor=False,
        show_reconstruction=False,
        show_time_graph=False,
        show_tps_graph=False,
        show_fluency_graph=False,
        show_recognition_graph=False,
        show_steps=False,
        countdown=0,
        metronome=0,
        orientation='UF',
        method='raw',
        stack=[],
        rng=Random(42),  # noqa: S311
    )

    instance.bluetooth_queue = asyncio.Queue()
    instance.bluetooth_cube = VCube(size=3)
    instance.bluetooth_interface = FakeBluetoothInterface()  # type: ignore[assignment]
    instance.facelets_received_event.set()
    instance.hardware_received_event.set()

    return instance


async def inject_timer_moves(
        timer: Timer,
        moves: list[str],
        *,
        clock_start: int = 0,
        clock_step: int = 100 * MS_TO_NS_FACTOR,
) -> None:
    """
    Feed a sequence of BT move events into the timer queue.

    Yields to the event loop after each move so the BT consumer can
    process it before the next one arrives.

    Args:
        timer: Target Timer instance (must have bluetooth_queue set).
        moves: Ordered list of move strings, e.g. ['R', 'U', "R'"].
        clock_start: Nanosecond clock value for the first move.
        clock_step: Nanosecond increment between consecutive moves.

    """
    queue = cast(
        'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
    )
    for i, move_str in enumerate(moves):
        clock = clock_start + i * clock_step
        await queue.put(make_move_event(move_str, clock))
        await asyncio.sleep(0)


class TestTimerKeyboardStopBluetooth(unittest.IsolatedAsyncioTestCase):
    """Timer behavior when keyboard start/stop is used with a BT cube."""

    def setUp(self) -> None:
        """Patch solve persistence and sound playback for each test."""
        save_patcher = patch('term_timer.interface.save_solves')
        self.save_solves_mock = save_patcher.start()
        self.addCleanup(save_patcher.stop)

        sound_patcher = patch('term_timer.interface.sounds.sd', create=True)
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    async def run_keyboard_cycle(
            timer: Timer,
            solve_moves: list[str],
            getch_modes: list[str],
    ) -> bool:
        """
        Run one cycle where the timer is started and stopped by keyboard.

        The scramble is applied on the BT cube, then the timer is
        started with a key press, solve_moves (possibly none) are
        injected, and the timer is stopped with another key press.

        Args:
            timer: Target Timer instance with fake BT attached.
            solve_moves: Cube moves injected during the solving phase.
            getch_modes: Output list collecting the getch modes requested.

        Returns:
            The bool returned by start() (True = continue, False = quit).

        """
        stop_event = asyncio.Event()

        async def getch_keyboard(mode: str, *_: object) -> str:
            getch_modes.append(mode)
            if mode == 'start':
                return ' '
            if mode == 'stop':
                await stop_event.wait()
                return ' '
            if mode == 'save':
                return ''
            await asyncio.sleep(3600)
            return ''

        consumer = asyncio.create_task(timer.bluetooth_consumer())
        timer.bluetooth_consumer_ref = consumer
        try:
            with patch.object(timer, 'getch', side_effect=getch_keyboard):
                run_task = asyncio.create_task(timer.start())
                await wait_until(lambda: timer.state == 'scrambling')

                s_moves = [str(m) for m in timer.scramble]
                await inject_timer_moves(timer, s_moves, clock_start=0)
                await asyncio.wait_for(
                    timer.scramble_completed_event.wait(),
                    timeout=2.0,
                )
                await wait_until(lambda: timer.state == 'scrambled')

                if solve_moves:
                    solve_clock = (
                        len(s_moves) * (100 * MS_TO_NS_FACTOR) + SECOND
                    )
                    await inject_timer_moves(
                        timer,
                        solve_moves,
                        clock_start=solve_clock,
                    )
                    await wait_until(
                        lambda: not timer.bluetooth_queue
                        or timer.bluetooth_queue.empty(),
                    )

                stop_event.set()
                return await asyncio.wait_for(run_task, timeout=2.0)
        finally:
            queue = cast(
                'asyncio.Queue[list[EventDict] | None]',
                timer.bluetooth_queue,
            )
            await queue.put(None)
            await consumer

    async def test_keyboard_start_stop_without_moves_discards(self) -> None:
        """
        Keyboard start + stop with zero cube moves discards the attempt.

        The scramble is applied on the BT cube, then the timer is
        started and stopped from the keyboard without any cube move.
        The cube is still scrambled: this is a misfire, not a solve.
        Nothing must be recorded - no solve in the stack, no save - and
        the save prompt must not be shown.
        """
        t = build_timer("R U R' U'")
        getch_modes: list[str] = []

        result = await self.run_keyboard_cycle(t, [], getch_modes)

        self.assertTrue(result, 'timing must continue after a misfire')
        self.assertEqual(len(t.moves), 0)
        self.assertFalse(t.bluetooth_scramble_is_completed)
        self.assertEqual(
            t.stack_done, [],
            'a keyboard-only attempt with no cube move must not '
            'record a solve',
        )
        self.assertEqual(t.stack, [])
        self.save_solves_mock.assert_not_called()
        self.assertNotIn(
            'save', getch_modes,
            'a discarded misfire must not show the save prompt',
        )

    @staticmethod
    async def run_save_solve(
            char: str,
            *,
            flag: SolveFlag = '',
            bluetooth: bool = True,
    ) -> Timer:
        """
        Run save_solve() on a Timer holding one solve with the given flag.

        Args:
            char: Character returned by the mocked getch at the prompt.
            flag: Initial flag of the solve in the stack.
            bluetooth: Keep the fake BT interface attached or strip it
                to emulate manual mode.

        Returns:
            The Timer after save_solve() has returned.

        """
        t = build_timer("R U R' U'")
        if not bluetooth:
            t.bluetooth_interface = None
            t.bluetooth_cube = None
            t.bluetooth_queue = None

        solve = Solve(1000000000, 1012345678, "R U R'", flag=flag)
        t.stack = [solve]
        t.stack_done = [solve]

        with patch.object(t, 'getch', new=AsyncMock(return_value=char)):
            await t.save_solve()

        return t

    async def test_bluetooth_dnf_cannot_be_marked_ok(self) -> None:
        """
        In bluetooth mode 'o' is a plain save key, the DNF flag stays.

        With a BT cube the flag is derived from the cube state: a DNF
        cannot be whitewashed into a valid solve at the save prompt.
        """
        t = await self.run_save_solve('o', flag=DNF)

        self.assertEqual(t.stack[-1].flag, DNF)
        self.assertEqual(t.stack_done[-1].flag, DNF)
        self.save_solves_mock.assert_called()

    async def test_bluetooth_ignores_manual_flag_keys(self) -> None:
        """In bluetooth mode 'd' and '2' are plain save keys, no flag set."""
        for char in ('d', '2'):
            with self.subTest(char=char):
                t = await self.run_save_solve(char)

                self.assertEqual(t.stack[-1].flag, '')
                self.assertEqual(len(t.stack), 1, 'solve must be saved')

    async def test_manual_flag_keys_still_work(self) -> None:
        """In manual mode 'd' and '2' still set the DNF and +2 flags."""
        for char, expected in (('d', DNF), ('2', PLUS_TWO)):
            with self.subTest(char=char):
                t = await self.run_save_solve(char, bluetooth=False)

                self.assertEqual(t.stack[-1].flag, expected)
                self.assertEqual(t.stack_done[-1].flag, expected)

    async def test_manual_o_is_a_plain_save_key(self) -> None:
        """
        The 'o' override is gone: in manual mode it is a plain save key.

        A manual solve is never DNF before the prompt, so there is no
        flag left to clear - 'o' saves like any other key.
        """
        t = await self.run_save_solve('o', bluetooth=False)

        self.assertEqual(t.stack[-1].flag, '')
        self.assertEqual(len(t.stack), 1, 'solve must be saved')

    async def test_keyboard_stop_with_moves_is_dnf(self) -> None:
        """
        Keyboard stop after real cube moves flags the solve as DNF.

        The scramble is applied on the BT cube, the user makes moves
        without solving the cube, then stops the timer from the
        keyboard. This is a genuine failed attempt: the solve is
        recorded and flagged DNF.
        """
        t = build_timer("R U R' U'")
        getch_modes: list[str] = []

        result = await self.run_keyboard_cycle(
            t, ['F', 'B'], getch_modes,
        )

        self.assertTrue(result)
        self.assertGreater(len(t.moves), 0)
        self.assertFalse(t.bluetooth_scramble_is_completed)
        self.assertEqual(len(t.stack_done), 1)
        self.assertEqual(
            t.stack_done[0].flag, DNF,
            'an interrupted attempt with cube moves must be a DNF',
        )
        self.save_solves_mock.assert_called()


class TestBluetoothScanFilter(unittest.IsolatedAsyncioTestCase):
    """What narrows the scan looking for a cube to connect to."""

    def setUp(self) -> None:
        """Patch sound playback so the failed connection stays silent."""
        sound_patcher = patch('term_timer.interface.sounds.sd', create=True)
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    async def scan_arguments(device: CubeDevice) -> tuple[Any, ...]:
        """
        Connect to a cube left to be scanned, reporting the scan call.

        Args:
            device: Cube to connect to, carrying no address.

        Returns:
            The positional arguments the scan was called with.

        """
        timer = build_timer("R U R' U'")
        interface = FakeBluetoothInterface()
        interface.scan_timeout = 0  # type: ignore[attr-defined]
        scan_mock = AsyncMock(return_value=None)
        interface.scan = scan_mock  # type: ignore[attr-defined]
        # Finding nothing is enough, the scan call is what is watched
        interface.__aenter__ = AsyncMock(  # type: ignore[attr-defined]
            side_effect=CubeNotFoundError,
        )

        with patch(
                'term_timer.interface.bluetooth.BluetoothInterface',
                return_value=interface,
        ):
            await timer.bluetooth_connect(device)

        return cast('tuple[Any, ...]', scan_mock.call_args.args)

    async def test_display_name_does_not_filter_the_scan(self) -> None:
        """A cube named in the configuration is not looked up by name."""
        device = CubeDevice(
            label='gan12',
            name='GAN 12 ui FreePlay',
        )

        arguments = await self.scan_arguments(device)

        self.assertIsNone(arguments[0])


class TestBluetoothDisconnect(unittest.IsolatedAsyncioTestCase):
    """Stopping the Bluetooth consumer whatever the state of the link."""

    def setUp(self) -> None:
        """Patch sound playback for each test."""
        sound_patcher = patch('term_timer.interface.sounds.sd', create=True)
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    def start_consumer(timer: Timer) -> asyncio.Task[None]:
        """
        Run the Bluetooth consumer of a timer, parked on its queue.

        Args:
            timer: Timer whose consumer is started.

        Returns:
            The consumer task, referenced by the timer as in production.

        """
        consumer = asyncio.create_task(timer.bluetooth_consumer())
        timer.bluetooth_consumer_ref = consumer
        return consumer

    @staticmethod
    def disconnect_interface() -> FakeBluetoothInterface:
        """
        Build a Bluetooth interface whose link is already down.

        The client is a fresh instance, its state being set on it and
        not on the class shared by every other test.

        Returns:
            The interface, reporting a disconnected client.

        """
        interface = FakeBluetoothInterface()
        client = FakeBluetoothClient()
        client.is_connected = False
        interface.client = client

        return interface

    async def test_disconnect_stops_consumer_when_link_is_down(self) -> None:
        """A cube gone before the exit does not hold the application."""
        timer = build_timer("R U R' U'")
        timer.bluetooth_interface = self.disconnect_interface()  # type: ignore[assignment]
        consumer = self.start_consumer(timer)
        await asyncio.sleep(0)

        await asyncio.wait_for(timer.bluetooth_disconnect(), timeout=1.0)

        self.assertTrue(consumer.done())

    async def test_disconnect_stops_consumer_when_connected(self) -> None:
        """The normal exit still stops the consumer."""
        timer = build_timer("R U R' U'")
        exit_mock = AsyncMock()
        timer.bluetooth_interface.__aexit__ = (  # type: ignore[method-assign,union-attr]
            exit_mock
        )
        consumer = self.start_consumer(timer)
        await asyncio.sleep(0)

        await asyncio.wait_for(timer.bluetooth_disconnect(), timeout=1.0)

        self.assertTrue(consumer.done())
        exit_mock.assert_awaited_once()

    async def test_disconnect_cancels_a_consumer_that_does_not_stop(
            self,
    ) -> None:
        """A consumer deaf to the sentinel is cancelled, not awaited."""
        timer = build_timer("R U R' U'")
        timer.bluetooth_interface = self.disconnect_interface()  # type: ignore[assignment]
        deaf: asyncio.Task[None] = asyncio.create_task(asyncio.sleep(3600))
        timer.bluetooth_consumer_ref = deaf

        with patch(
                'term_timer.interface.bluetooth.'
                'BLUETOOTH_CONSUMER_STOP_TIMEOUT',
                0.01,
        ):
            await asyncio.wait_for(timer.bluetooth_disconnect(), timeout=1.0)

        self.assertTrue(deaf.cancelled())

    async def test_disconnect_leaves_no_sentinel_behind(self) -> None:
        """
        A normal exit posts one sentinel, and it is the consumer's.

        The interface exit used to post one of its own, so a plain
        session exit left a second one in the queue.
        """
        timer = build_timer("R U R' U'")
        timer.bluetooth_interface.__aexit__ = AsyncMock()  # type: ignore[method-assign,union-attr]
        consumer = self.start_consumer(timer)
        await asyncio.sleep(0)

        await asyncio.wait_for(timer.bluetooth_disconnect(), timeout=1.0)

        self.assertTrue(consumer.done())
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )
        self.assertTrue(queue.empty())


def make_battery_event(level: int) -> list[EventDict]:
    """
    Build a BT queue payload for a battery report.

    A state free event: whatever the timer is doing, consuming it is
    visible on bluetooth_hardware and nowhere else.

    Args:
        level: Battery percentage carried by the event.

    Returns:
        A one-element list ready to put into timer.bluetooth_queue.

    """
    event: BatteryEventDict = {
        'event': 'battery',
        'clock': 0,
        'timestamp': datetime.now(tz=UTC),
        'level': level,
        'charging_state': 0,
    }
    result: list[EventDict] = [event]
    return result


class TestBluetoothHandoff(unittest.IsolatedAsyncioTestCase):
    """Passing a live connection from one session to the next."""

    logger_name = 'term_timer.interface.bluetooth'

    def setUp(self) -> None:
        """Patch sound playback for each test."""
        sound_patcher = patch('term_timer.interface.sounds.sd', create=True)
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    def start_consumer(timer: Timer) -> asyncio.Task[None]:
        """
        Run the Bluetooth consumer of a timer, parked on its queue.

        Args:
            timer: Timer whose consumer is started.

        Returns:
            The consumer task, referenced by the timer as in production.

        """
        consumer = asyncio.create_task(timer.bluetooth_consumer())
        timer.bluetooth_consumer_ref = consumer
        return consumer

    async def assert_target_consumes(self, target: Timer) -> None:
        """
        Check that the consumer of the target is alive and draining.

        Args:
            target: The instance the connection was handed off to.

        """
        consumer = target.bluetooth_consumer_ref
        self.assertIsNotNone(consumer)
        self.assertFalse(cast('asyncio.Task[None]', consumer).done())

        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', target.bluetooth_queue,
        )
        await queue.put(make_battery_event(42))
        await wait_until(lambda: target.bluetooth_hardware.get(
            'battery_level',
        ) == 42)

        await asyncio.wait_for(
            target.stop_bluetooth_consumer(), timeout=1.0,
        )

    async def test_handoff_stops_the_consumer_and_starts_the_next(
            self,
    ) -> None:
        """The living consumer is stopped, the target one takes over."""
        source = build_timer("R U R' U'")
        target = build_timer("R U R' U'")
        consumer = self.start_consumer(source)
        await asyncio.sleep(0)

        await asyncio.wait_for(source.bluetooth_handoff(target), timeout=1.0)

        self.assertTrue(consumer.done())
        self.assertIsNone(source.bluetooth_consumer_ref)
        await self.assert_target_consumes(target)

    async def test_handoff_posts_nothing_for_a_dead_consumer(self) -> None:
        """
        A consumer that died before the handoff gets no sentinel.

        It would never read it: the sentinel stayed in the queue and the
        consumer started on the target read it at once and stopped, the
        cube events piling up in a queue nobody drained any more.
        """
        source = build_timer("R U R' U'")
        target = build_timer("R U R' U'")
        consumer = self.start_consumer(source)
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', source.bluetooth_queue,
        )
        await queue.put(None)
        await consumer

        with self.assertLogs(self.logger_name, level='WARNING') as logs:
            await asyncio.wait_for(
                source.bluetooth_handoff(target), timeout=1.0,
            )

        self.assertIn('already stopped', logs.output[0])
        self.assertTrue(queue.empty())
        await self.assert_target_consumes(target)

    async def test_handoff_takes_its_sentinel_back_from_a_deaf_consumer(
            self,
    ) -> None:
        """
        A consumer cancelled on timeout never read the sentinel.

        Left in the queue it is the very same orphan, one turn later:
        the consumer of the target would read it and stop.
        """
        source = build_timer("R U R' U'")
        target = build_timer("R U R' U'")
        deaf: asyncio.Task[None] = asyncio.create_task(asyncio.sleep(3600))
        source.bluetooth_consumer_ref = deaf

        with patch(
                'term_timer.interface.bluetooth.'
                'BLUETOOTH_CONSUMER_STOP_TIMEOUT',
                0.01,
        ), self.assertLogs(self.logger_name, level='WARNING') as logs:
            await asyncio.wait_for(
                source.bluetooth_handoff(target), timeout=1.0,
            )

        self.assertTrue(deaf.cancelled())
        self.assertIn('did not stop', logs.output[0])
        await self.assert_target_consumes(target)

    async def test_handoff_keeps_the_events_of_a_deaf_consumer(self) -> None:
        """Taking the sentinel back does not drop the cube events."""
        source = build_timer("R U R' U'")
        target = build_timer("R U R' U'")
        deaf: asyncio.Task[None] = asyncio.create_task(asyncio.sleep(3600))
        source.bluetooth_consumer_ref = deaf
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', source.bluetooth_queue,
        )
        await queue.put(make_battery_event(17))

        with patch(
                'term_timer.interface.bluetooth.'
                'BLUETOOTH_CONSUMER_STOP_TIMEOUT',
                0.01,
        ):
            await asyncio.wait_for(
                source.bluetooth_handoff(target), timeout=1.0,
            )

        await wait_until(lambda: target.bluetooth_hardware.get(
            'battery_level',
        ) == 17)
        self.assertEqual(target.bluetooth_hardware['battery_level'], 17)

        await asyncio.wait_for(
            target.stop_bluetooth_consumer(), timeout=1.0,
        )


def make_disconnect_event() -> list[EventDict]:
    """
    Build a BT queue payload for a cube announcing its disconnection.

    Returns:
        A one-element list ready to put into timer.bluetooth_queue.

    """
    event: DisconnectEventDict = {
        'event': 'disconnect',
        'clock': 0,
        'timestamp': datetime.now(tz=UTC),
    }
    result: list[EventDict] = [event]
    return result


class TestBluetoothDisconnectEvent(unittest.IsolatedAsyncioTestCase):
    """A cube announcing its own disconnection ends the session."""

    def setUp(self) -> None:
        """Patch sound playback for each test."""
        sound_patcher = patch('term_timer.interface.sounds.sd', create=True)
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    def start_consumer(timer: Timer) -> asyncio.Task[None]:
        """
        Run the Bluetooth consumer of a timer, parked on its queue.

        Args:
            timer: Timer whose consumer is started.

        Returns:
            The consumer task, referenced by the timer as in production.

        """
        consumer = asyncio.create_task(timer.bluetooth_consumer())
        timer.bluetooth_consumer_ref = consumer
        return consumer

    async def test_disconnect_event_stops_the_consumer(self) -> None:
        """Nothing more will come, the consumer does not wait for it."""
        timer = build_timer("R U R' U'")
        consumer = self.start_consumer(timer)
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )

        await queue.put(make_disconnect_event())

        await asyncio.wait_for(consumer, timeout=1.0)
        self.assertTrue(timer.bluetooth_lost_event.is_set())

    async def test_a_lost_link_ends_the_session_too(self) -> None:
        """
        A link dropping reaches the session, through the same path.

        The interface posts on the queue the consumer is parked on, so
        the cube going out of range ends the session exactly as the cube
        announcing itself does. This is the join between the two, the
        rest of the chain being the same from here on.
        """
        timer = build_timer("R U R' U'")
        consumer = self.start_consumer(timer)
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )
        interface = BluetoothInterface(queue)
        waiting: asyncio.Task[object] = spawn(
            asyncio.sleep(3600), 'getch-scrambled',
        )

        interface.handle_disconnection(cast('BleakClient', None))

        with self.assertRaises(CubeDisconnectedError):
            await asyncio.wait_for(
                timer.wait_control([waiting]), timeout=1.0,
            )

        await asyncio.wait_for(consumer, timeout=1.0)
        self.assertTrue(timer.bluetooth_lost_event.is_set())
        self.assertTrue(waiting.cancelled())

    async def test_disconnect_event_ends_the_waiting_phase(self) -> None:
        """The phase waiting for a move it will never get gives up."""
        timer = build_timer("R U R' U'")
        self.start_consumer(timer)
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )
        waiting: asyncio.Task[object] = spawn(
            asyncio.sleep(3600), 'getch-scrambled',
        )

        await queue.put(make_disconnect_event())

        with self.assertRaises(CubeDisconnectedError):
            await asyncio.wait_for(
                timer.wait_control([waiting]), timeout=1.0,
            )
        self.assertTrue(waiting.cancelled())

    async def test_unhandled_event_is_logged(self) -> None:
        """An event no branch claims leaves a trace and nothing else."""
        timer = build_timer("R U R' U'")
        consumer = self.start_consumer(timer)
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )
        reset: list[EventDict] = [
            cast('EventDict', {
                'event': 'reset',
                'clock': 0,
                'timestamp': datetime.now(tz=UTC),
            }),
        ]

        with self.assertLogs(
                'term_timer.interface.bluetooth', logging.DEBUG,
        ) as captured:
            await queue.put(reset)
            await wait_until(queue.empty)

        self.assertIn('Unhandled event reset', captured.output[0])
        self.assertFalse(consumer.done())

        consumer.cancel()

    async def test_disconnect_event_ends_a_running_solve(self) -> None:
        """The whole attempt gives up, through the real phases."""
        timer = build_timer("R U R' U'")
        self.start_consumer(timer)
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )

        async def getch_silent(*_: object) -> str:
            await asyncio.sleep(3600)
            return ''

        with patch.object(timer, 'getch', side_effect=getch_silent):
            run_task = asyncio.create_task(timer.start())
            await wait_until(lambda: timer.state == 'scrambling')

            await queue.put(make_disconnect_event())

            with self.assertRaises(CubeDisconnectedError):
                await asyncio.wait_for(run_task, timeout=2.0)


class FakeGyroscopeDriver:
    """Driver stub carrying only the gyroscope preference."""

    def __init__(self, *, use_gyroscope: bool) -> None:
        """
        Store the preference the reconciliation reads.

        Args:
            use_gyroscope: Whether the gyroscope data is wanted.

        """
        self.use_gyroscope = use_gyroscope


class RecordingBluetoothInterface(FakeBluetoothInterface):
    """Bluetooth interface stub recording the commands it is sent."""

    def __init__(self, *, use_gyroscope: bool) -> None:
        """
        Build an interface exposing a driver and an empty command log.

        Args:
            use_gyroscope: Preference carried by the fake driver.

        """
        self.client = FakeBluetoothClient()
        self.driver = FakeGyroscopeDriver(  # type: ignore[assignment]
            use_gyroscope=use_gyroscope,
        )
        self.commands: list[str] = []

    async def send_command(self, command: str) -> None:
        """
        Record the command instead of writing it on the link.

        Args:
            command: Command name the reconciliation sends.

        """
        self.commands.append(command)


def make_gen4_hardware_event() -> list[EventDict]:
    """
    Build the hardware event of a Gen4 cube.

    It carries the name and the gyroscope support, and nothing about
    the state of the gyroscope: that one comes later, in its own
    message.

    Returns:
        A one-element list ready to put into the queue.

    """
    event: HardwareEventNameOnlyDict = {
        'event': 'hardware',
        'clock': 0,
        'timestamp': datetime.now(tz=UTC),
        'hardware_name': 'GANi4',
        'gyroscope_supported': True,
    }
    result: list[EventDict] = [event]
    return result


def make_gyro_config_event(*, enabled: bool) -> list[EventDict]:
    """
    Build the gyroscope configuration event a cube reports.

    Args:
        enabled: Whether the cube says its gyroscope streams.

    Returns:
        A one-element list ready to put into the queue.

    """
    event: GyroConfigEventDict = {
        'event': 'gyro-config',
        'clock': 0,
        'timestamp': datetime.now(tz=UTC),
        'gyroscope_enabled': enabled,
        'gyroscope_ready': True,
        'gyroscope_supported': True,
    }
    result: list[EventDict] = [event]
    return result


class TestGyroscopeReconciliation(unittest.IsolatedAsyncioTestCase):
    """Aligning the cube gyroscope with the configured preference."""

    def setUp(self) -> None:
        """Patch sound playback for each test."""
        sound_patcher = patch('term_timer.interface.sounds.sd', create=True)
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    def build(self, *, use_gyroscope: bool) -> tuple[
            Timer, RecordingBluetoothInterface,
            'asyncio.Queue[list[EventDict] | None]',
    ]:
        """
        Build a timer whose consumer runs against a recording interface.

        Args:
            use_gyroscope: Preference carried by the fake driver.

        Returns:
            The timer, its interface and its queue.

        """
        timer = build_timer("R U R' U'")
        interface = RecordingBluetoothInterface(use_gyroscope=use_gyroscope)
        timer.bluetooth_interface = interface  # type: ignore[assignment]

        consumer = asyncio.create_task(timer.bluetooth_consumer())
        timer.bluetooth_consumer_ref = consumer
        self.addCleanup(consumer.cancel)

        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )

        return timer, interface, queue

    async def test_gen4_disables_a_gyroscope_announced_after_hardware(
            self,
    ) -> None:
        """The Gen4 states its gyroscope once the hardware event is past."""
        _timer, interface, queue = self.build(use_gyroscope=False)

        await queue.put(make_gen4_hardware_event())
        await wait_until(queue.empty)

        self.assertEqual(interface.commands, [])

        await queue.put(make_gyro_config_event(enabled=True))
        await wait_until(queue.empty)

        self.assertEqual(interface.commands, ['REQUEST_DISABLE_GYRO'])

    async def test_gyroscope_wanted_is_enabled_from_the_config_event(
            self,
    ) -> None:
        """A cube starting on a cut gyroscope is asked to stream again."""
        _timer, interface, queue = self.build(use_gyroscope=True)

        await queue.put(make_gyro_config_event(enabled=False))
        await wait_until(queue.empty)

        self.assertEqual(interface.commands, ['REQUEST_ENABLE_GYRO'])

    async def test_an_aligned_state_sends_nothing(self) -> None:
        """The answer of the cube to a command does not bounce back."""
        _timer, interface, queue = self.build(use_gyroscope=False)

        await queue.put(make_gyro_config_event(enabled=True))
        await wait_until(queue.empty)
        await queue.put(make_gyro_config_event(enabled=False))
        await wait_until(queue.empty)

        self.assertEqual(interface.commands, ['REQUEST_DISABLE_GYRO'])

    async def test_the_gyroscope_state_is_kept_on_the_timer(self) -> None:
        """The event feeds the hardware panel as much as the command."""
        timer, _interface, queue = self.build(use_gyroscope=True)

        await queue.put(make_gyro_config_event(enabled=True))
        await wait_until(queue.empty)

        self.assertTrue(timer.bluetooth_hardware['gyroscope_enabled'])
        self.assertTrue(timer.bluetooth_hardware['gyroscope_ready'])
