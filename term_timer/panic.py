"""Panic keys writing a post-mortem at the end of the day's log."""
import asyncio
import faulthandler
import os
import signal
import sys
import time
import traceback
from datetime import UTC
from datetime import datetime
from pathlib import Path
from types import FrameType
from typing import Any
from typing import Final
from typing import TextIO

from term_timer.config import DEBUG

START_TIME: Final = time.monotonic()

# Last time each moving part was seen alive. Two entries only, and they
# are the two that matter: a cube still talking with nothing draining it
# looks exactly like a cube gone silent, once everything is stuck.
HEARTBEATS: Final[dict[str, float]] = {}

# Absent from Windows, hence looked up by name. SIGQUIT is the one
# within reach of a keyboard, SIGUSR1 the one reachable from another
# terminal; both carry the same two paths to a report.
PANIC_SIGNALS: Final = ('SIGQUIT', 'SIGUSR1')

panic_stream: TextIO | None = None


def beat(name: str) -> None:
    """
    Record that an activity is still alive, for the panic report.

    Args:
        name: Identifier of the activity, e.g. ``bluetooth-event``.

    """
    HEARTBEATS[name] = time.monotonic()


def dump_heartbeats(stream: TextIO) -> None:
    """
    Write how long each instrumented activity has been silent.

    Args:
        stream: Where the heartbeats are written.

    """
    if not HEARTBEATS:
        stream.write('No heartbeat recorded.\n')
        return

    now = time.monotonic()

    stream.writelines(
        f'{ name.ljust(24) } {now - stamp:8.2f}s ago\n'
        for name, stamp in sorted(HEARTBEATS.items())
    )


def dump_awaited_chain(stream: TextIO, task: asyncio.Task[Any]) -> None:
    """
    Write down what a task is waiting on, coroutine by coroutine.

    A suspended coroutine has no caller frame left to walk, so the stack
    asyncio offers holds the outermost frame only. Following the chain of
    awaited coroutines instead gives the whole path, down to the exact
    line where the task went to sleep.

    Args:
        stream: Where the chain is written.
        task: The task to follow.

    """
    frames: list[tuple[FrameType, int]] = []
    awaited: object = task.get_coro()

    while awaited is not None:
        frame = getattr(awaited, 'cr_frame', None)

        if frame is None:
            break

        frames.append((frame, frame.f_lineno))
        awaited = getattr(awaited, 'cr_await', None)

    stream.writelines(traceback.StackSummary.extract(iter(frames)).format())


def dump_tasks(stream: TextIO) -> None:
    """
    Write what every living asyncio task is waiting on.

    Args:
        stream: Where the tasks are written.

    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        stream.write('No running event loop.\n')
        return

    tasks = asyncio.all_tasks(loop)
    stream.write(f'{ len(tasks) } task(s) alive\n\n')

    for task in sorted(tasks, key=lambda task: task.get_name()):
        stream.write(f'* { task.get_name() }, awaiting:\n')
        dump_awaited_chain(stream, task)
        stream.write('\n')


def dump_header(stream: TextIO, reason: str) -> None:
    """
    Write what identifies this report.

    Args:
        stream: Where the header is written.
        reason: What triggered the report.

    """
    now = datetime.now(UTC).astimezone()

    stream.write(
        f'\n=== PANIC { reason } ===\n'
        f'date    : { now.isoformat(timespec="milliseconds") }\n'
        f'uptime  : {time.monotonic() - START_TIME:.1f}s\n'
        f'pid     : { os.getpid() }\n'
        f'command : { " ".join(sys.argv) }\n',
    )


def report(reason: str, error: BaseException | None = None) -> None:
    """
    Append everything known about the current situation to the log.

    The log says what happened up to the freeze; this says where the
    process is stuck right now. A frozen process writes nothing more:
    its last line is the last event before the block, and it does not
    say what is being waited for. The chain of awaits of every living
    task is only obtainable by asking the process while it is stuck.

    Args:
        reason: What triggered the report.
        error: The exception behind it, when there is one.

    """
    if panic_stream is None:
        return

    dump_header(panic_stream, reason)

    if error is not None:
        panic_stream.write('\n--- error ---\n')
        panic_stream.write(''.join(traceback.format_exception(error)))

    panic_stream.write('\n--- heartbeats ---\n')
    dump_heartbeats(panic_stream)

    panic_stream.write('\n--- asyncio tasks ---\n')
    dump_tasks(panic_stream)

    panic_stream.write('\n--- threads ---\n')
    # Written at file descriptor level, past the buffer of the stream
    panic_stream.flush()
    faulthandler.dump_traceback(file=panic_stream, all_threads=True)

    panic_stream.write('=== END PANIC ===\n')
    panic_stream.flush()


def panic_handler(signum: int, _frame: FrameType | None) -> None:
    """
    Write a report on demand, without disturbing the application.

    Args:
        signum: The signal asking for the report.
        _frame: The interrupted frame, unused.

    """
    report(signal.Signals(signum).name)


def install_panic(path: Path) -> None:
    r"""
    Arm the panic keys and the crash handler for the whole process.

    Two paths lead to a report, because a wedged application does not
    always answer. A Python handler only sets a flag the interpreter
    reads between two bytecodes, so it never runs on a process stuck at
    C level: faulthandler is registered first, dumps every thread stack
    whatever the interpreter is doing, then chains to our own handler
    for the complete report. Both keys carry both paths — Ctrl+\ within
    reach of a keyboard, SIGUSR1 from another terminal. Fatal errors are
    dumped too, as a crash otherwise leaves nothing behind.

    Args:
        path: The log file the reports are appended to.

    """
    global panic_stream  # noqa: PLW0603

    if not DEBUG:
        return

    # Held open for the life of the process: faulthandler writes to this
    # descriptor from contexts where opening a file is not an option,
    # which is the whole point of its C level path, and the listener
    # thread owning the other descriptor may itself be stuck
    panic_stream = path.open('a', encoding='utf-8')

    faulthandler.enable(file=panic_stream, all_threads=True)

    for name in PANIC_SIGNALS:
        number: signal.Signals | None = getattr(signal, name, None)

        if number is None:
            continue

        signal.signal(number, panic_handler)
        faulthandler.register(
            number,
            file=panic_stream,
            all_threads=True,
            chain=True,
        )
