"""
Benchmarks of the moves received from a Bluetooth cube.

Each benchmark feeds the moves of the recorded solve to the handlers the
consumer of the Bluetooth queue dispatches them to, the queue itself
being measured by the session benchmark. Run them with:

    pytest benchmarks --benchmark-autosave
    pytest benchmarks --benchmark-compare
"""
import math
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from cubing_algs.vcube import VCube
from pytest_benchmark.fixture import BenchmarkFixture

from benchmarks.harness import SCRAMBLE
from benchmarks.harness import SOLUTION
from benchmarks.harness import build_timer
from benchmarks.harness import move_event
from term_timer.bluetooth.annotations import QuaternionDict
from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.timer import Timer

ROUNDS = 50

GYRO_EVENTS = 1_000

# Fractional steps of an additive recurrence, irrational and independent
SEQUENCE_STEPS = (math.sqrt(2), math.sqrt(3), math.sqrt(5))


def feed(timer: Timer, moves: list[tuple[str, int]]) -> None:
    """Hand moves to the handlers, as the Bluetooth consumer does."""
    for move, milliseconds in moves:
        timer.handle_bluetooth_cube_move(move)
        timer.handle_bluetooth_move(
            move_event(move, milliseconds * MS_TO_NS_FACTOR),
        )


def solving_timer() -> tuple[tuple[Timer], dict[str, object]]:
    """
    Build a timer solving the recorded scramble, its first move received.

    Returns:
        The arguments of one round.

    """
    timer = build_timer()
    timer.set_state('solving')
    return (timer,), {}


def scrambling_timer() -> tuple[tuple[Timer], dict[str, object]]:
    """
    Build a timer whose solved cube waits for the scramble moves.

    Returns:
        The arguments of one round.

    """
    timer = build_timer()
    timer.bluetooth_cube = VCube(size=3)
    timer.set_state('scrambling')
    return (timer,), {}


def test_solving_moves(benchmark: BenchmarkFixture) -> None:
    """The 70 moves of the solve, until the cube is solved."""

    def solve(timer: Timer) -> None:
        feed(timer, SOLUTION)
        if not timer.solve_completed_event.is_set():
            pytest.fail('the recorded solution never solves the cube')

    benchmark.pedantic(solve, setup=solving_timer, rounds=ROUNDS)


def test_scramble_moves(benchmark: BenchmarkFixture) -> None:
    """The 20 moves of the scramble, its progress redrawn at every move."""
    moves = [(move, index * 300) for index, move in enumerate(
        SCRAMBLE.split(),
    )]

    def scramble(timer: Timer) -> None:
        with (
            Path(os.devnull).open('w', encoding='utf-8') as null,
            redirect_stdout(null),
        ):
            feed(timer, moves)
        if not timer.scramble_completed_event.is_set():
            pytest.fail('the scramble is never completed')

    benchmark.pedantic(scramble, setup=scrambling_timer, rounds=ROUNDS)


def spread_quaternion(index: int) -> QuaternionDict:
    """
    Give the index-th of unit quaternions spread over all orientations.

    The uniform sampling of a random quaternion, fed with a fixed low
    discrepancy sequence instead of random draws, so that every run
    replays the same samples.

    Returns:
        The quaternion, as decoded from a gyroscope message.

    """
    u1, u2, u3 = (
        math.modf(index * step)[0] for step in SEQUENCE_STEPS
    )
    return {
        'w': math.sqrt(1 - u1) * math.sin(2 * math.pi * u2),
        'x': math.sqrt(1 - u1) * math.cos(2 * math.pi * u2),
        'y': math.sqrt(u1) * math.sin(2 * math.pi * u3),
        'z': math.sqrt(u1) * math.cos(2 * math.pi * u3),
    }


def test_gyroscope_events(benchmark: BenchmarkFixture) -> None:
    """A thousand orientation samples, 40s of a GAN12 with -g."""
    samples = [spread_quaternion(index) for index in range(GYRO_EVENTS)]

    def detect() -> None:
        detector = RotationDetector()
        for sample in samples:
            detector.process_gyro_event(sample)

    benchmark(detect)
