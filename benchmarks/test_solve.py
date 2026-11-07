"""
Benchmarks of what runs between the stop of the timer and the prompt.

Every round analyses a fresh solve, the analyses being cached on it.
Run them with:

    pytest benchmarks --benchmark-autosave
    pytest benchmarks --benchmark-compare
"""
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture
from rich.console import Console as RichConsole

from benchmarks.harness import SOLUTION_TIME
from benchmarks.harness import build_solve
from benchmarks.harness import build_timer
from term_timer.constants import SECOND
from term_timer.solve import Solve
from term_timer.timer import Timer

ROUNDS = 30

# Solves of the session before the one just done, as in a daily stack
HISTORY = 300


def fresh_solve() -> tuple[tuple[Solve], dict[str, object]]:
    """
    Build the recorded solve, not analysed yet.

    Returns:
        The arguments of one round.

    """
    return (build_solve(SOLUTION_TIME, HISTORY + 1),), {}


def finished_attempt() -> tuple[tuple[Timer, Solve], dict[str, object]]:
    """
    Build a timer with its session history, and the solve just done.

    Returns:
        The arguments of one round.

    """
    timer = build_timer()
    timer.stack = [
        build_solve(SOLUTION_TIME + (index % 17 - 8) * SECOND, index + 1)
        for index in range(HISTORY)
    ]
    timer.counter = HISTORY + 1
    timer.elapsed_time = SOLUTION_TIME
    return (timer, build_solve(SOLUTION_TIME, HISTORY + 1)), {}


def test_analysis(benchmark: BenchmarkFixture) -> None:
    """The CFOP analysis of the 70 moves solve."""

    def analyse(solve: Solve) -> None:
        if solve.method_applied is None:
            pytest.fail('the solve is not analysed')

    benchmark.pedantic(analyse, setup=fresh_solve, rounds=ROUNDS)


def test_solve_line(benchmark: BenchmarkFixture) -> None:
    """The whole report: analysis, doctor, highlights and statistics."""
    with (
        Path(os.devnull).open('w', encoding='utf-8') as null,
        redirect_stdout(null),
    ):
        console = RichConsole(file=null, force_terminal=True, width=120)

        def report(timer: Timer, solve: Solve) -> None:
            timer.console = console
            timer.solve_line(solve)

        benchmark.pedantic(report, setup=finished_attempt, rounds=ROUNDS)
