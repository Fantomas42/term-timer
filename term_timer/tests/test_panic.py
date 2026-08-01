"""Tests for the panic keys and the post-mortem they write."""
import asyncio
import faulthandler
import io
import os
import signal
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import cast
from unittest import mock

from term_timer import panic as panic_module
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.logger import spawn
from term_timer.panic import HEARTBEATS
from term_timer.panic import beat
from term_timer.panic import dump_awaited_chain
from term_timer.panic import dump_heartbeats
from term_timer.panic import dump_tasks
from term_timer.panic import install_panic
from term_timer.panic import panic_handler
from term_timer.panic import report
from term_timer.tests.test_bluetooth_interface import EventDriver
from term_timer.tests.test_timer_bluetooth import build_timer

if TYPE_CHECKING:
    from bleak.backends.characteristic import BleakGATTCharacteristic

    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import EventDict
    from term_timer.bluetooth.drivers.base import Driver

HAS_SIGNALS = hasattr(signal, 'SIGUSR1') and hasattr(signal, 'SIGQUIT')


class HeartbeatTestCase(unittest.TestCase):
    """Tests for the heartbeats and how they are written down."""

    def setUp(self) -> None:
        """Start from an empty table, the module one being global."""
        self.heartbeats = dict(HEARTBEATS)
        HEARTBEATS.clear()

    def tearDown(self) -> None:
        """Give the table of the module back what it held."""
        HEARTBEATS.clear()
        HEARTBEATS.update(self.heartbeats)

    def test_beat_records_the_activity(self) -> None:
        """A beat is a name and the instant it was last seen alive."""
        beat('bluetooth-event')

        self.assertIn('bluetooth-event', HEARTBEATS)

    def test_beat_moves_the_stamp_forward(self) -> None:
        """Beating again is what makes the age of a source meaningful."""
        beat('bluetooth-event')
        first = HEARTBEATS['bluetooth-event']

        beat('bluetooth-event')

        self.assertGreaterEqual(HEARTBEATS['bluetooth-event'], first)

    def test_dump_heartbeats_without_a_single_beat(self) -> None:
        """An empty table says so, rather than writing nothing at all."""
        stream = io.StringIO()

        dump_heartbeats(stream)

        self.assertEqual(stream.getvalue(), 'No heartbeat recorded.\n')

    def test_dump_heartbeats_writes_an_age(self) -> None:
        """
        The age is the point, not the stamp.

        A cube still talking with nothing draining it and a cube gone
        silent are the same picture once everything is stuck: only the
        two ages, read side by side, tell them apart.
        """
        beat('bluetooth-notification')
        beat('bluetooth-event')

        stream = io.StringIO()
        dump_heartbeats(stream)

        self.assertRegex(
            stream.getvalue(),
            r'bluetooth-event\s+\d+\.\d\ds ago\n'
            r'bluetooth-notification\s+\d+\.\d\ds ago\n',
        )


async def inner(event: asyncio.Event) -> None:
    """
    Go to sleep.

    Args:
        event: What this coroutine waits on.

    """
    await event.wait()


async def middle(event: asyncio.Event) -> None:
    """
    Call the coroutine actually going to sleep.

    Args:
        event: What the innermost coroutine waits on.

    """
    await inner(event)


async def parked(event: asyncio.Event) -> None:
    """
    Wait on an event, three coroutines deep.

    Args:
        event: What the innermost coroutine waits on.

    """
    await middle(event)


class AwaitedChainTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the chain of awaits of a suspended task."""

    async def test_dump_awaited_chain_walks_the_whole_path(self) -> None:
        """
        The chain holds every coroutine, down to the sleeping one.

        This is the reason the module exists: the stack asyncio offers
        for a suspended task holds its outermost frame only, because a
        suspended coroutine has no caller frame left to walk. Following
        cr_await gives the path that says what is being waited for.
        """
        event = asyncio.Event()
        task = spawn(parked(event), 'parked')

        await asyncio.sleep(0)

        chain = io.StringIO()
        dump_awaited_chain(chain, task)

        stack = io.StringIO()
        task.print_stack(file=stack)

        event.set()
        await task

        for name in ('in parked', 'in middle', 'in inner'):
            with self.subTest(coroutine=name):
                self.assertIn(name, chain.getvalue())

        self.assertIn('in parked', stack.getvalue())
        self.assertNotIn('in inner', stack.getvalue())

    async def test_dump_awaited_chain_of_a_finished_task(self) -> None:
        """A task that has returned has nothing left to be waiting on."""
        task = spawn(asyncio.sleep(0), 'over')

        await task

        chain = io.StringIO()
        dump_awaited_chain(chain, task)

        self.assertEqual(chain.getvalue(), '')


class DumpTasksTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the inventory of the living tasks."""

    def test_dump_tasks_without_a_running_loop(self) -> None:
        """A report taken after the loop is gone says so and moves on."""
        stream = io.StringIO()

        dump_tasks(stream)

        self.assertEqual(stream.getvalue(), 'No running event loop.\n')

    async def test_dump_tasks_names_every_task(self) -> None:
        """
        A task is named, and its absence from the list is a finding.

        The report never says a task died: the hole in the inventory
        does, along with the death line the log already holds.
        """
        event = asyncio.Event()
        task = spawn(event.wait(), 'bluetooth-consumer')

        await asyncio.sleep(0)

        stream = io.StringIO()
        dump_tasks(stream)

        event.set()
        await task

        self.assertIn('* bluetooth-consumer, awaiting:', stream.getvalue())
        self.assertRegex(stream.getvalue(), r'^\d+ task\(s\) alive')


class ReportTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the report itself."""

    def setUp(self) -> None:
        """Open a real file: faulthandler writes to a descriptor."""
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'term-timer.log'
        self.stream = self.path.open('w', encoding='utf-8')

    def tearDown(self) -> None:
        """Close the file and remove it."""
        self.stream.close()
        self.directory.cleanup()

    def test_report_without_an_installation(self) -> None:
        """
        Without the panic keys armed, a report is a silent no-op.

        Nothing is installed outside of debug mode, and bt-info has its
        own entry point: the death of a task must not raise there.
        """
        with mock.patch.object(panic_module, 'panic_stream', new=None):
            report('task-death')

            self.assertEqual(self.path.read_text(encoding='utf-8'), '')

    async def test_report_writes_every_section(self) -> None:
        """The report is self-contained: what, who, and where it is."""
        beat('bluetooth-event')

        with mock.patch.object(
                panic_module, 'panic_stream', new=self.stream,
        ):
            report('SIGUSR1')

        content = self.path.read_text(encoding='utf-8')

        for section in (
                '=== PANIC SIGUSR1 ===',
                'uptime  :',
                'command :',
                '--- heartbeats ---',
                'bluetooth-event',
                '--- asyncio tasks ---',
                '--- threads ---',
                '=== END PANIC ===',
        ):
            with self.subTest(section=section):
                self.assertIn(section, content)

    def test_report_writes_the_error_behind_it(self) -> None:
        """A report triggered by an exception carries its traceback."""
        error = RuntimeError('injected consumer failure')

        with mock.patch.object(
                panic_module, 'panic_stream', new=self.stream,
        ):
            report('task-death', error)

        content = self.path.read_text(encoding='utf-8')

        self.assertIn('--- error ---', content)
        self.assertIn('RuntimeError: injected consumer failure', content)

    async def test_a_dead_task_writes_a_report(self) -> None:
        """
        The one freeze that announces itself is caught unattended.

        A task held for the whole session is never collected, so asyncio
        never reports what killed it: the queue stops being drained and
        the application waits for a move that will never come.
        """
        async def dying() -> None:
            await asyncio.sleep(0)

            msg = 'injected consumer failure'
            raise RuntimeError(msg)

        with mock.patch.object(
                panic_module, 'panic_stream', new=self.stream,
        ):
            task = spawn(dying(), 'bluetooth-consumer')

            with self.assertLogs('term_timer.logger'):
                await asyncio.wait([task])

        content = self.path.read_text(encoding='utf-8')

        self.assertIn('=== PANIC task-death ===', content)
        self.assertIn('RuntimeError: injected consumer failure', content)


@unittest.skipUnless(HAS_SIGNALS, 'POSIX signals only')
class InstallPanicTestCase(unittest.TestCase):
    """Tests for arming the panic keys."""

    def setUp(self) -> None:
        """Remember the signal handlers of the test runner."""
        self.handlers = {
            number: signal.getsignal(number)
            for number in (signal.SIGQUIT, signal.SIGUSR1)
        }

        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'term-timer.log'

    def tearDown(self) -> None:
        """
        Give the process back the handlers it had.

        pytest arms faulthandler on its own descriptor, and this test
        case replaced it by one pointing at a file about to be removed.
        """
        for number in (signal.SIGQUIT, signal.SIGUSR1):
            faulthandler.unregister(number)

        faulthandler.enable()

        for number, handler in self.handlers.items():
            signal.signal(number, handler)

        if panic_module.panic_stream is not None:
            panic_module.panic_stream.close()
            panic_module.panic_stream = None

        self.directory.cleanup()

    def install(self, *, debug: bool) -> None:
        """
        Run install_panic with the debug switch in a known position.

        Args:
            debug: Value taken by DEBUG during the installation.

        """
        with mock.patch.object(panic_module, 'DEBUG', new=debug):
            install_panic(self.path)

    def test_install_panic_outside_debug_mode(self) -> None:
        """
        Nothing is opened outside of debug mode, not even the file.

        The descriptor is taken at installation, not at the first
        report: a session logging nothing would still touch the log of
        the day on every single command.
        """
        self.install(debug=False)

        self.assertIsNone(panic_module.panic_stream)
        self.assertFalse(self.path.exists())

    def test_install_panic_opens_the_log_of_the_day(self) -> None:
        """
        The descriptor is held for the life of the process.

        faulthandler writes to it from contexts where opening a file is
        not an option, which is the whole point of its C level path.
        """
        self.install(debug=True)

        self.assertIsNotNone(panic_module.panic_stream)
        self.assertTrue(self.path.exists())

    def test_install_panic_arms_the_keys(self) -> None:
        r"""Ctrl+\ and SIGUSR1 both lead to a report."""
        self.install(debug=True)

        for number in (signal.SIGQUIT, signal.SIGUSR1):
            with self.subTest(signal=signal.Signals(number).name):
                self.assertIs(signal.getsignal(number), panic_handler)

    def test_install_panic_arms_the_keys_at_c_level_too(self) -> None:
        """
        Both keys carry the C level path, not the keyboard one alone.

        A Python handler only sets a flag the interpreter reads between
        two bytecodes: on a process stuck at C level it never runs, and
        the thread stacks of faulthandler are all that comes out.
        """
        self.install(debug=True)

        for number in (signal.SIGQUIT, signal.SIGUSR1):
            with self.subTest(signal=signal.Signals(number).name):
                # Answers whether the signal was registered, and the
                # tear down unregisters both anyway. Typeshed declares
                # it as returning None, where CPython documents and
                # returns a bool
                registered = faulthandler.unregister(number)  # type: ignore[func-returns-value]

                self.assertTrue(registered)

    def test_a_panic_signal_writes_a_report(self) -> None:
        """
        The application survives the panic key, and answers it.

        A report that killed the process would answer the question once
        and remove any chance of asking it again.
        """
        self.install(debug=True)

        os.kill(os.getpid(), signal.SIGUSR1)

        content = self.path.read_text(encoding='utf-8')

        self.assertIn('=== PANIC SIGUSR1 ===', content)
        self.assertIn('=== END PANIC ===', content)


class HeartbeatCallSiteTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the two places the application beats from."""

    def setUp(self) -> None:
        """Start from an empty table, the module one being global."""
        self.heartbeats = dict(HEARTBEATS)
        HEARTBEATS.clear()

    def tearDown(self) -> None:
        """Give the table of the module back what it held."""
        HEARTBEATS.clear()
        HEARTBEATS.update(self.heartbeats)

    async def test_a_notification_beats(self) -> None:
        """
        A packet delivered by bleak is the first half of the pair.

        Beaten before the driver is awaited, so it says the link is
        alive whatever the driver then makes of the bytes.
        """
        queue: asyncio.Queue[list[EventDict] | None] = asyncio.Queue()
        interface = BluetoothInterface(queue)
        interface.driver = cast('Driver', EventDriver([]))

        await interface.notification_handler(
            cast('BleakGATTCharacteristic', None),
            bytearray(b'\x00'),
        )

        self.assertIn('bluetooth-notification', HEARTBEATS)

    async def test_a_consumed_event_beats(self) -> None:
        """
        An event drained by the consumer is the second half.

        A notification beating while this one goes stale is the whole
        point of the pair: the cube is still talking, and the pipeline
        behind it is dead.
        """
        battery: BatteryEventDict = {
            'event': 'battery',
            'clock': 12,
            'timestamp': datetime.now(),  # noqa: DTZ005
            'level': 87,
            'charging_state': 0,
        }

        timer = build_timer("R U R' U'")
        consumer = spawn(timer.bluetooth_consumer(), 'bluetooth-consumer')

        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', timer.bluetooth_queue,
        )
        await queue.put([battery])
        await queue.put(None)
        await consumer

        self.assertIn('bluetooth-event', HEARTBEATS)
