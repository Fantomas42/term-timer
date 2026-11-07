"""
Benchmark of a whole Bluetooth solve, replayed in a real session.

Plays ``replay.json`` through ``term-timer solve --replay``, in a pseudo
terminal and a throwaway home configured by ``config.toml``, publishing
on a socket of that home, and measures what a micro benchmark cannot:

- the CPU load of the running stopwatch, and its cost per frame,
- the queue latency, from the emission of a move to its handling,
- the delay from the stop of the timer to the save prompt,
- the startup, up to the scramble prompt, and the CPU of the process.

The replay keeps the pacing of the recording, so a run lasts the 27s of
the solve. Run it with:

    python -m benchmarks.replay_session
    python -m benchmarks.replay_session --runs 5 --asyncio-debug

The parent drives the pseudo terminal, the child runs the application
with measuring probes wrapped around a few of its methods.
"""
import argparse
import json
import os
import pty
import resource
import select
import statistics
import subprocess  # noqa: S404
import sys
import tempfile
import termios
import time
from pathlib import Path
from unittest.mock import patch

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.annotations import RotationEventDict
from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.interface.bluetooth import Bluetooth
from term_timer.interface.state import State
from term_timer.interface.stopwatch import StopWatch
from term_timer.scripts.timer import main as term_timer_main

ROOT = Path(__file__).parent.parent
REPLAY_PATH = Path(__file__).with_name('replay.json')
CONFIG_PATH = Path(__file__).with_name('config.toml')

# Rows and columns of the pseudo terminal, so that Rich wraps the same way
TERMINAL_SIZE = (40, 120)

# A replayed solve lasts 27s: past this delay, the child is stuck
TIMEOUT = 120.0

METRICS = (
    ('solve_load', 'Stopwatch load', '{:.1f}%'),
    ('frame_cpu', 'CPU per frame', '{:.0f}us'),
    ('frames', 'Frames drawn', '{:.0f}'),
    ('latency_p50', 'Queue latency p50', '{:.0f}us'),
    ('latency_p95', 'Queue latency p95', '{:.0f}us'),
    ('latency_max', 'Queue latency max', '{:.0f}us'),
    ('stop_to_prompt', 'Stop to save prompt', '{:.1f}ms'),
    ('startup', 'Startup to scramble', '{:.0f}ms'),
    ('process_cpu', 'Process CPU', '{:.2f}s'),
)


class Probes:
    """
    Measures taken in the child, wrapped around the application.

    Moments are read on the monotonic clock, shared by every process of
    the machine: the startup is measured from the spawn by the parent.
    """

    def __init__(self) -> None:
        """Start with nothing measured."""
        self.solve_cpu = 0.0
        self.solve_wall = 0.0
        self.frames = 0
        self.emitted: dict[int, int] = {}
        self.latencies: list[int] = []
        self.transitions: list[tuple[str, float]] = []

    def install(self) -> None:
        """Wrap the measured methods of the application."""
        self.install_stopwatch()
        self.install_queue()
        self.install_states()

    def install_stopwatch(self) -> None:
        """Measure the CPU of the running stopwatch and count its frames."""
        stopwatch = StopWatch.stopwatch
        print_timer = StopWatch.print_timer

        async def measured_stopwatch(watch: StopWatch) -> None:
            cpu = time.thread_time()
            wall = time.monotonic()
            await stopwatch(watch)
            self.solve_cpu += time.thread_time() - cpu
            self.solve_wall += time.monotonic() - wall

        def counted_print_timer(
                watch: StopWatch, elapsed_time: int, style: str,
        ) -> None:
            self.frames += 1
            print_timer(watch, elapsed_time, style)

        patch.object(StopWatch, 'stopwatch', measured_stopwatch).start()
        patch.object(StopWatch, 'print_timer', counted_print_timer).start()

    def install_queue(self) -> None:
        """Time the moves from their emission to their handling."""
        emit = BluetoothInterface.emit
        handle_move = Bluetooth.handle_bluetooth_move

        async def stamped_emit(
                interface: BluetoothInterface, events: list[EventDict],
        ) -> None:
            now = time.perf_counter_ns()
            for event in events:
                self.emitted[id(event)] = now
            await emit(interface, events)

        def timed_handle_move(
                bluetooth: Bluetooth,
                event: MoveEventDict | RotationEventDict,
        ) -> None:
            sent = self.emitted.pop(id(event), None)
            if sent is not None and bluetooth.state == 'solving':
                self.latencies.append(time.perf_counter_ns() - sent)
            handle_move(bluetooth, event)

        patch.object(BluetoothInterface, 'emit', stamped_emit).start()
        patch.object(
            Bluetooth, 'handle_bluetooth_move', timed_handle_move,
        ).start()

    def install_states(self) -> None:
        """Record the moment of every state transition."""
        set_state = State.set_state

        def logged_set_state(
                state: State, name: str, timestamp: int | None = None,
        ) -> None:
            self.transitions.append((name, time.monotonic()))
            set_state(state, name, timestamp)

        patch.object(State, 'set_state', logged_set_state).start()

    def first(self, state: str) -> float:
        """
        Give the moment of the first transition to a state.

        Returns:
            The monotonic moment of the transition, NaN when never reached.

        """
        return next(
            (moment for name, moment in self.transitions if name == state),
            float('nan'),
        )

    def results(self, spawned: float) -> dict[str, float]:
        """
        Summarize the measures of the session.

        Args:
            spawned: Monotonic moment the parent spawned the child.

        Returns:
            One value per metric, in the units of METRICS.

        """
        usage = resource.getrusage(resource.RUSAGE_SELF)
        latencies = sorted(self.latencies) or [0]

        return {
            'solve_load': self.solve_cpu / (self.solve_wall or 1) * 100,
            'frame_cpu': self.solve_cpu / (self.frames or 1) * 1e6,
            'frames': self.frames,
            'latency_p50': latencies[len(latencies) // 2] / 1e3,
            'latency_p95': latencies[int(len(latencies) * 0.95)] / 1e3,
            'latency_max': latencies[-1] / 1e3,
            'stop_to_prompt': (
                self.first('saving') - self.first('stop')
            ) * 1e3,
            'startup': (self.first('scrambling') - spawned) * 1e3,
            'process_cpu': usage.ru_utime + usage.ru_stime,
        }


def run_child(result_path: Path, spawned: float) -> int:
    """
    Run the replayed session with the probes installed.

    Returns:
        The exit code of the application.

    """
    probes = Probes()
    probes.install()

    sys.argv = ['term-timer', 'solve', '1', '--replay', str(REPLAY_PATH)]
    code = term_timer_main()

    result_path.write_text(
        json.dumps(probes.results(spawned)), encoding='utf-8',
    )

    return code


def session_environment(home: Path, *, asyncio_debug: bool) -> dict[str, str]:
    """
    Build the environment of a session isolated in a throwaway home.

    Returns:
        The environment of the child.

    """
    config = home / 'config.toml'
    config.write_text(
        CONFIG_PATH.read_text(encoding='utf-8')
        + '\n[publisher]\nactive = true\n'
        + f'endpoints = ["ipc://{ home / "cube.ipc" }"]\n',
        encoding='utf-8',
    )

    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith('TERM_TIMER_')
        and key != 'OPENBLAS_NUM_THREADS'
    }
    environment.update({
        'TERM_TIMER_HOME': str(home),
        'TERM_TIMER_CONFIG': str(config),
        'TERM_TIMER_NO_BANNER': '1',
        'TERM_TIMER_DEBUG': '1',
        'TERM_TIMER_ASYNCIO_DEBUG': '1' if asyncio_debug else '0',
        'TERM_TIMER_SOUND': 'off',
        'TERM_TIMER_PUBLISH': '1',
        'TERM': 'xterm-256color',
        'COLORTERM': 'truecolor',
    })

    return environment


def run_session(*, asyncio_debug: bool) -> dict[str, float]:
    """
    Run one replayed session in a pseudo terminal, its output discarded.

    Returns:
        The measures of the session.

    Raises:
        RuntimeError: The session failed, or never ended.

    """
    with tempfile.TemporaryDirectory(prefix='term-timer-bench-') as tmp:
        home = Path(tmp)
        result_path = home / 'result.json'

        master, slave = pty.openpty()
        termios.tcsetwinsize(slave, TERMINAL_SIZE)

        child = subprocess.Popen(  # noqa: S603
            [
                sys.executable, '-m', 'benchmarks.replay_session',
                '--child', str(result_path),
                '--spawned', repr(time.monotonic()),
            ],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=session_environment(home, asyncio_debug=asyncio_debug),
            cwd=ROOT,
            start_new_session=True,
        )
        os.close(slave)

        output = bytearray()
        deadline = time.monotonic() + TIMEOUT
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 1.0)
                if not ready:
                    continue
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                output.extend(data)
        finally:
            os.close(master)

        try:
            code = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            msg = f'The session never ended within { TIMEOUT:.0f}s'
            raise RuntimeError(msg) from None

        if code or not result_path.exists():
            tail = output[-2000:].decode('utf-8', errors='replace')
            msg = f'The session failed with code { code }:\n{ tail }'
            raise RuntimeError(msg)

        results: dict[str, float] = json.loads(
            result_path.read_text(encoding='utf-8'),
        )
        return results


def print_report(runs: list[dict[str, float]], *, asyncio_debug: bool) -> None:
    """Print each run and the median of the runs, one metric per line."""
    mode = 'on' if asyncio_debug else 'off'
    header = f'{ "Metric":<22}' + ''.join(
        f'{ f"run {index}":>12}' for index in range(1, len(runs) + 1)
    ) + f'{ "median":>12}'

    lines = [f'Replayed solve, asyncio debug { mode }', header]
    for key, label, spec in METRICS:
        values = [run[key] for run in runs]
        lines.append(
            f'{ label:<22}'
            + ''.join(f'{ spec.format(value):>12}' for value in values)
            + f'{ spec.format(statistics.median(values)):>12}',
        )

    sys.stdout.write('\n'.join(lines) + '\n')


def get_parser() -> argparse.ArgumentParser:
    """
    Build the command line parser.

    Returns:
        The configured parser.

    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '-r', '--runs',
        type=int,
        default=3,
        help='Number of replayed sessions. Default: 3.',
    )
    parser.add_argument(
        '-a', '--asyncio-debug',
        action='store_true',
        help='Run the sessions with the asyncio debug mode on.',
    )
    parser.add_argument(
        '--child',
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--spawned',
        type=float,
        default=0.0,
        help=argparse.SUPPRESS,
    )
    return parser


def main() -> int:
    """
    Run the benchmark, or the measured session when called as its child.

    Returns:
        The exit code.

    """
    options = get_parser().parse_args()

    if options.child:
        return run_child(options.child, options.spawned)

    runs: list[dict[str, float]] = []
    for index in range(options.runs):
        sys.stderr.write(
            f'Replaying session { index + 1 }/{ options.runs }...\n',
        )
        runs.append(run_session(asyncio_debug=options.asyncio_debug))

    print_report(runs, asyncio_debug=options.asyncio_debug)

    return 0


if __name__ == '__main__':
    sys.exit(main())
