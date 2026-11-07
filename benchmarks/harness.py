"""
Shared data and builders of the benchmarks.

The recorded solve is ``replay.json``, the very file the session benchmark
replays, so that the micro benchmarks and the session measure the same
attempt. Its scramble and solution are both in the frame of the cube,
held in the DF orientation: the moves are fed as a cube sends them.
"""
import asyncio
import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from random import Random
from typing import Any

from cubing_algs.algorithm import Algorithm
from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.replay import parse_timed_moves
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.solve import Solve
from term_timer.timer import Timer

REPLAY_PATH = Path(__file__).with_name('replay.json')

REPLAY: dict[str, Any] = json.loads(REPLAY_PATH.read_text(encoding='utf-8'))

SCRAMBLE: str = REPLAY['solves'][0]['scramble']

# Recorded with this orientation and analysed with this method
ORIENTATION = 'DF'
METHOD = 'cf4op'

# (move, milliseconds since the first move) of the recorded solution
SOLUTION: list[tuple[str, int]] = parse_timed_moves(
    REPLAY['solves'][0]['solution'],
)

SOLUTION_TIME: int = (SOLUTION[-1][1] + 1) * MS_TO_NS_FACTOR


def build_timer(*, show_steps: bool = False) -> Timer:
    """
    Build a Timer wired like a Bluetooth session, the cube scrambled.

    Returns:
        A Timer whose Bluetooth cube holds the recorded scramble.

    """
    timer = Timer(
        cube_size=3,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble=SCRAMBLE,
        scrambles=[],
        session='benchmark',
        free_play=False,
        show_cube=False,
        show_highlights=True,
        show_doctor=True,
        show_reconstruction=True,
        show_time_graph=False,
        show_tps_graph=False,
        show_fluency_graph=False,
        show_recognition_graph=False,
        show_steps=show_steps,
        countdown=0,
        metronome=0,
        orientation=ORIENTATION,
        method=METHOD,
        stack=[],
        rng=Random(42),  # noqa: S311
    )

    timer.bluetooth_queue = asyncio.Queue()
    timer.bluetooth_cube = VCube(size=3)
    timer.bluetooth_cube.rotate(SCRAMBLE)

    timer.scramble = Algorithm.parse_moves(SCRAMBLE)
    timer.scramble_oriented = timer.reorient(timer.scramble)
    timer.facelets_scrambled = timer.bluetooth_cube.state

    return timer


def move_event(move: str, clock: int) -> MoveEventDict:
    """
    Build a move event the way a driver emits it.

    Returns:
        A move event at the given clock.

    """
    return {
        'event': 'move',
        'clock': clock,
        'timestamp': datetime.now(tz=UTC),
        'serial': 0,
        'local_timestamp': None,
        'cube_timestamp': None,
        'face': 0,
        'direction': 0,
        'move': move,
    }


def build_solve(time: int, solve_id: int) -> Solve:
    """
    Build the recorded solve, as saved at the end of the attempt.

    Returns:
        A fresh solve, none of its analyses computed yet.

    """
    solve = Solve(
        1_700_000_000 + solve_id * 60,
        time,
        SCRAMBLE,
        timer='Term-Timer',
        device=REPLAY['device']['name'],
        session='benchmark',
        solve_id=solve_id,
        cube_size=3,
        moves=' '.join(f'{ move }@{ ms }' for move, ms in SOLUTION),
    )
    solve.method_name = METHOD
    solve.orientation = ORIENTATION

    return solve
