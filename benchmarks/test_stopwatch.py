"""
Benchmarks of the stopwatch display, redrawn a hundred times per second.

The frames are rendered in truecolor for a terminal, and written to
/dev/null so that the terminal emulator never enters the measure. Run
them with:

    pytest benchmarks --benchmark-autosave
    pytest benchmarks --benchmark-compare
"""
import os
from collections.abc import Iterator
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture
from rich.console import Console as RichConsole
from rich.theme import Theme

from benchmarks.harness import SOLUTION
from benchmarks.harness import build_timer
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.interface.console import theme
from term_timer.timer import Timer

ELAPSED = 12_345_000_000


@pytest.fixture
def terminal() -> Iterator[RichConsole]:
    """
    Send the terminal output, Rich's and the cursor moves, to /dev/null.

    Yields:
        A console rendering like the application one, in truecolor.

    """
    with (
        Path(os.devnull).open('w', encoding='utf-8') as null,
        redirect_stdout(null),
    ):
        yield RichConsole(
            file=null,
            force_terminal=True,
            color_system='truecolor',
            highlighter=None,
            theme=Theme(theme),
            width=120,
        )


def drawn_timer(console: RichConsole, *, show_steps: bool = False) -> Timer:
    """
    Build a timer whose stopwatch line is already drawn.

    Returns:
        The timer, one frame displayed.

    """
    timer = build_timer(show_steps=show_steps)
    timer.console = console
    timer.print_timer(ELAPSED, 'timer_10')
    return timer


def test_timer_frame(
        benchmark: BenchmarkFixture, terminal: RichConsole,
) -> None:
    """A frame of the running time, the cost paid every 10ms."""
    timer = drawn_timer(terminal)

    benchmark(timer.print_timer, ELAPSED, 'timer_10')


def test_timer_line(
        benchmark: BenchmarkFixture, terminal: RichConsole,
) -> None:
    """The whole line, redrawn through Rich when a threshold is crossed."""
    timer = drawn_timer(terminal)

    def redraw() -> None:
        timer.previous_style = ''
        timer.print_timer(ELAPSED, 'timer_10')

    benchmark(redraw)


def test_step_detection(
        benchmark: BenchmarkFixture, terminal: RichConsole,
) -> None:
    """The F2L slots checked on a new cube state, cross just solved."""
    timer = drawn_timer(terminal, show_steps=True)
    timer.init_step_tracking()

    for move, milliseconds in SOLUTION:
        timer.handle_bluetooth_cube_move(move)
        timer.moves.append(
            {'move': move, 'time': milliseconds * MS_TO_NS_FACTOR},
        )
        timer.check_and_print_steps(ELAPSED, 'timer_10')
        if timer.group_progress:
            break

    if timer.group_progress != 1:
        pytest.fail('the cross is never detected')

    def detect() -> None:
        timer.last_facelets = ''
        timer.check_and_print_steps(ELAPSED, 'timer_10')

    benchmark(detect)
