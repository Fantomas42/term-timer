"""
Tests for the Bluetooth replay interface.

Covers the file loader/validator, the move-timing helpers, the schedule
event sequence, and a full Timer.start() run driven end to end by a
ReplayInterface (no hardware).
"""
import asyncio
import json
import os
import tempfile
import unittest
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from random import Random
from typing import Any
from typing import cast
from unittest.mock import patch

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.replay import HUMAN_SCRAMBLE_PACE_MS
from term_timer.bluetooth.replay import ReplayFileDict
from term_timer.bluetooth.replay import ReplayInterface
from term_timer.bluetooth.replay import ReplaySolveDict
from term_timer.bluetooth.replay import load_replay
from term_timer.bluetooth.replay import load_scramble_replay
from term_timer.bluetooth.replay import parse_timed_moves
from term_timer.bluetooth.replay import scramble_moves_reach_state
from term_timer.bluetooth.replay import validate_replay
from term_timer.exceptions import ReplayError
from term_timer.tests.test_trainer_bluetooth import wait_until
from term_timer.timer import Timer

EventQueue = asyncio.Queue[list[EventDict] | None]

VALID_REPLAY: dict[str, Any] = {
    'device': {
        'name': 'GAN12 ui Replay',
        'hardware_version': '1.0',
        'software_version': '1.0',
        'battery': 87,
    },
    'solves': [
        {
            'scramble': "R U R' U'",
            'scramble_moves': "R@0 U@10 R'@20 U'@30",
            'inspection': 0.0,
            'start_delay': 0.0,
            'solution': "U@0 R@10 U'@20 R'@30",
        },
    ],
}


def write_replay(data: object) -> str:
    """
    Write a replay payload to a temp file and return its path.

    Args:
        data: The payload to serialize as JSON.

    Returns:
        Path to the written temporary file.

    """
    descriptor, path = tempfile.mkstemp(suffix='.json')
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(data, handle)
    return path


class TestReplayLoader(unittest.TestCase):
    """Validation of the replay file loader."""

    def test_load_valid(self) -> None:
        """A well-formed file loads and keeps its solves."""
        path = write_replay(VALID_REPLAY)
        self.addCleanup(Path(path).unlink)

        replay = load_replay(path)

        self.assertEqual(len(replay['solves']), 1)
        self.assertEqual(replay['device']['name'], 'GAN12 ui Replay')

    def test_missing_file(self) -> None:
        """A missing path raises ReplayError."""
        with self.assertRaises(ReplayError):
            load_replay('/nonexistent/replay.json')

    def test_bad_json(self) -> None:
        """A file that is not valid JSON raises ReplayError."""
        path = write_replay(VALID_REPLAY)
        Path(path).write_text('{not json', encoding='utf-8')
        self.addCleanup(Path(path).unlink)

        with self.assertRaises(ReplayError):
            load_replay(path)

    def test_not_an_object(self) -> None:
        """A top-level JSON array is rejected."""
        with self.assertRaises(ReplayError):
            validate_replay([1, 2, 3])

    def test_missing_device(self) -> None:
        """A payload without a device object is rejected."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        del data['device']

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_missing_battery(self) -> None:
        """A device without an integer battery is rejected."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        del data['device']['battery']

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_empty_solves(self) -> None:
        """An empty solves list is rejected."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'] = []

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_missing_scramble(self) -> None:
        """A solve without a scramble is rejected."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        del data['solves'][0]['scramble']

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_missing_solution(self) -> None:
        """A solve without a solution is rejected."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        del data['solves'][0]['solution']

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_inconsistent_scramble_moves(self) -> None:
        """Scramble moves that miss the scrambled state are rejected."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'][0]['scramble_moves'] = 'R@0 U@10'

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_scramble_moves_optional(self) -> None:
        """A solve without scramble_moves is accepted (synthesized later)."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        del data['solves'][0]['scramble_moves']

        replay = validate_replay(data)

        self.assertNotIn('scramble_moves', replay['solves'][0])

    def test_finish_moves_optional_on_last_solve(self) -> None:
        """The last solve does not need a finish_moves save gesture."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)

        replay = validate_replay(data)

        self.assertNotIn('finish_moves', replay['solves'][0])

    def test_finish_moves_must_be_string(self) -> None:
        """A non-string finish_moves is rejected."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'][0]['finish_moves'] = 42

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_finish_moves_required_to_chain(self) -> None:
        """Every solve but the last needs finish_moves to chain."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'].append(deepcopy(data['solves'][0]))

        with self.assertRaises(ReplayError):
            validate_replay(data)

    def test_multi_solves_chained_by_finish_moves(self) -> None:
        """A multi-solve file is valid when chained by finish_moves."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'].append(deepcopy(data['solves'][0]))
        data['solves'][0]['finish_moves'] = "U@0 U'@250"

        replay = validate_replay(data)

        self.assertEqual(len(replay['solves']), 2)


class TestScrambleReplayLoader(unittest.TestCase):
    """Loading a replay for a command whose scramble is imposed."""

    def load(self, scramble: str, imposed: str) -> ReplayFileDict | None:
        """
        Load a replay racing a scramble against an imposed one.

        Returns:
            The validated payload, or None when no path is given.

        """
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'][0]['scramble'] = scramble
        del data['solves'][0]['scramble_moves']

        path = write_replay(data)
        self.addCleanup(Path(path).unlink)

        return load_scramble_replay(path, imposed)

    def test_no_path(self) -> None:
        """Without a path, no replay drives the command."""
        self.assertIsNone(load_scramble_replay('', "R U R' U'"))

    def test_matching_scramble(self) -> None:
        """A replay on the imposed scramble is loaded."""
        replay = self.load("R U R' U'", "R U R' U'")

        self.assertIsNotNone(replay)

    def test_equivalent_scramble(self) -> None:
        """A replay reaching the imposed state otherwise is loaded."""
        replay = self.load("R U R' U' U U U U", "R U R' U'")

        self.assertIsNotNone(replay)

    def test_other_scramble_refused(self) -> None:
        """A replay scrambling elsewhere would hang the timer."""
        with self.assertRaises(ReplayError) as context:
            self.load("R U R'", "R U R' U'")

        self.assertIn('never start', str(context.exception))

    def test_every_solve_checked(self) -> None:
        """A diverging solve is refused wherever it sits in the file."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'][0]['finish_moves'] = "U@0 U'@250"
        data['solves'].append(deepcopy(data['solves'][0]))
        data['solves'][1]['scramble'] = "R U R'"
        del data['solves'][1]['scramble_moves']

        path = write_replay(data)
        self.addCleanup(Path(path).unlink)

        with self.assertRaises(ReplayError) as context:
            load_scramble_replay(path, "R U R' U'")

        self.assertIn('#2', str(context.exception))


class TestReplayMoveTiming(unittest.TestCase):
    """Move-timing helpers used to build the replay schedule."""

    def test_parse_timed_moves(self) -> None:
        """Timed moves keep their explicit millisecond offsets."""
        moves = parse_timed_moves("R@0 U'@329 L@989")

        self.assertEqual(moves, [('R', 0), ("U'", 329), ('L', 989)])

    def test_parse_untimed_moves_pace(self) -> None:
        """Untimed moves fall back to the human scramble pace."""
        moves = parse_timed_moves("R U R'")

        self.assertEqual(
            moves,
            [
                ('R', 0),
                ('U', HUMAN_SCRAMBLE_PACE_MS),
                ("R'", 2 * HUMAN_SCRAMBLE_PACE_MS),
            ],
        )

    def test_scramble_moves_reach_state_true(self) -> None:
        """Consistent scramble moves reach the scrambled state."""
        self.assertTrue(
            scramble_moves_reach_state("R@0 U@10 R'@20 U'@30", "R U R' U'"),
        )

    def test_scramble_moves_reach_state_false(self) -> None:
        """Truncated scramble moves do not reach the scrambled state."""
        self.assertFalse(
            scramble_moves_reach_state('R@0 U@10', "R U R' U'"),
        )


def build_replay_timer(replay: ReplayFileDict) -> Timer:
    """
    Build a Timer wired with a ReplayInterface and a solved BT cube.

    Mirrors what bluetooth_connect() sets up, but without running the
    schedule so the solve can be driven deterministically from the test.

    Args:
        replay: A validated replay payload.

    Returns:
        A Timer ready for a replay-driven start() run.

    """
    instance = Timer(
        cube_size=3,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble='',
        scrambles=[
            parse_moves(solve['scramble'])
            for solve in replay['solves']
        ],
        session='replay-test',
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

    queue: EventQueue = asyncio.Queue()
    instance.bluetooth_queue = queue
    instance.bluetooth_replay = replay
    instance.bluetooth_interface = ReplayInterface(queue, replay, instance)
    instance.bluetooth_cube = VCube(size=3)
    instance.facelets_received_event.set()
    instance.hardware_received_event.set()

    return instance


async def getch_blocked(*_: object) -> str:
    """
    Getch stub that never answers, so gestures drive every transition.

    Returns:
        Never returns; blocks until the surrounding task is cancelled.

    """
    await asyncio.sleep(3600)
    return ''


def make_getch_save(char: str = '') -> Callable[..., Awaitable[str]]:
    """
    Build a getch stub that only answers the save prompt.

    Every other prompt blocks so the replay events drive the transitions.

    Args:
        char: The key the save prompt answers with.

    Returns:
        A getch stub returning char at the save prompt, never otherwise.

    """
    async def getch(mode: str, *_: object) -> str:
        if mode == 'save':
            return char
        await asyncio.sleep(3600)
        return ''

    return getch


@asynccontextmanager
async def replay_consumer_running(timer: Timer) -> AsyncIterator[None]:
    """Run the BT event consumer for the duration of the block."""
    queue = cast('EventQueue', timer.bluetooth_queue)
    consumer = asyncio.create_task(timer.bluetooth_consumer())
    timer.bluetooth_consumer_ref = consumer

    try:
        yield
    finally:
        await queue.put(None)
        await consumer


class StateStub:
    """Minimal timer state surface, driven by hand instead of a real Timer."""

    def __init__(self) -> None:
        """Initialize with an empty state."""
        self.state = ''
        self.state_event = asyncio.Event()

    def goto(self, state: str) -> None:
        """Move to a new state and wake anyone waiting on it."""
        self.state = state
        self.state_event.set()


class TestReplayScheduleEvents(unittest.IsolatedAsyncioTestCase):
    """The schedule emits the expected event sequence, no timer involved."""

    @staticmethod
    def drain(queue: EventQueue) -> list[str]:
        """
        Collect event names from the queue until the sentinel or empty.

        Args:
            queue: The replay event queue to drain.

        Returns:
            The ordered event names read from the queue.

        """
        names: list[str] = []
        while not queue.empty():
            batch = queue.get_nowait()
            if batch is None:
                break
            names.extend(event['event'] for event in batch)
        return names

    @staticmethod
    async def advance(
            stub: StateStub,
            queue: EventQueue,
            state: str,
            expected_qsize: int,
    ) -> None:
        """
        Move the stub to a state and wait for the resulting events to land.

        The schedule always finishes queuing a phase's events before it
        blocks on the next wait_for_state, so polling the queue size is a
        deterministic way to know the schedule reached that next wait.

        Args:
            stub: The state stub driving the schedule.
            queue: The replay event queue the schedule pushes to.
            state: The state to move the stub to.
            expected_qsize: Queue size reached once the schedule, now
                unblocked, has queued the phase's events and blocked again.

        """
        stub.goto(state)
        await wait_until(lambda: queue.qsize() >= expected_qsize)

    async def test_schedule_event_sequence(self) -> None:
        """Init events precede the scramble and solution move events."""
        replay = validate_replay(deepcopy(VALID_REPLAY))

        stub = StateStub()
        queue: EventQueue = asyncio.Queue()
        interface = ReplayInterface(queue, replay, stub)

        await interface.send_init_commands()

        await self.advance(stub, queue, 'scrambling', 7)
        await self.advance(stub, queue, 'scrambled', 11)

        await asyncio.wait_for(
            cast('asyncio.Task[None]', interface.schedule_task), timeout=5.0,
        )

        names = self.drain(queue)

        self.assertEqual(names[:3], ['hardware', 'battery', 'facelets'])
        self.assertEqual(names.count('move'), 8)

    async def test_schedule_synthesizes_scramble(self) -> None:
        """Without scramble_moves the scramble is synthesized from scramble."""
        replay = validate_replay(deepcopy(VALID_REPLAY))
        del replay['solves'][0]['scramble_moves']

        stub = StateStub()
        queue: EventQueue = asyncio.Queue()
        interface = ReplayInterface(queue, replay, stub)

        await interface.send_init_commands()

        await self.advance(stub, queue, 'scrambling', 7)
        await self.advance(stub, queue, 'scrambled', 11)

        await asyncio.wait_for(
            cast('asyncio.Task[None]', interface.schedule_task), timeout=5.0,
        )

        names = self.drain(queue)

        # 4 synthesized scramble moves + 4 solution moves.
        self.assertEqual(names.count('move'), 8)

    async def test_schedule_plays_all_solves_and_gestures(self) -> None:
        """Every solve is played, with its finish_moves save gesture."""
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'].append(deepcopy(data['solves'][0]))
        data['solves'][0]['finish_moves'] = "U@0 U'@10"
        data['solves'][0]['save_delay'] = 0.0
        replay = validate_replay(data)

        stub = StateStub()
        queue: EventQueue = asyncio.Queue()
        interface = ReplayInterface(queue, replay, stub)

        await interface.send_init_commands()

        await self.advance(stub, queue, 'scrambling', 7)
        await self.advance(stub, queue, 'scrambled', 11)
        await self.advance(stub, queue, 'saving', 13)
        await self.advance(stub, queue, 'scrambling', 17)
        await self.advance(stub, queue, 'scrambled', 21)

        await asyncio.wait_for(
            cast('asyncio.Task[None]', interface.schedule_task), timeout=5.0,
        )

        names = self.drain(queue)

        # 2 solves x (4 scramble + 4 solution moves) + 2 gesture moves.
        self.assertEqual(names.count('move'), 18)


class TestReplayInterfaceFlow(unittest.IsolatedAsyncioTestCase):
    """Full Timer.start() run driven deterministically by a ReplayInterface."""

    def setUp(self) -> None:
        """Patch solve persistence, sound playback and pacing."""
        save_patcher = patch('term_timer.interface.save_solves')
        self.save_solves_mock = save_patcher.start()
        self.addCleanup(save_patcher.stop)

        # The pause before the save gesture is cosmetic pacing, and the
        # phases are state-gated: waiting for it only costs wall-clock.
        delay_patcher = patch(
            'term_timer.bluetooth.replay.DEFAULT_SAVE_DELAY', 0.0,
        )
        delay_patcher.start()
        self.addCleanup(delay_patcher.stop)

        sound_patcher = patch(
            'term_timer.interface.sounds.sd', create=True,
        )
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    async def drive_solve(timer: Timer, solve: ReplaySolveDict) -> bool:
        """
        Drive one full solve end to end through the real replay schedule.

        The schedule now gates every phase on the timer's own state
        transitions (see ReplayInterface.wait_for_state), so this only
        starts the consumer, the timer, and the schedule, and waits for
        them to finish; no manual phase-by-phase gating is needed.

        Args:
            timer: A Timer wired with a ReplayInterface.
            solve: The replay solve; only used to pick the getch stub,
                since a solve without finish_moves needs the save prompt
                answered from the keyboard (no gesture will do it).

        Returns:
            The bool returned by Timer.start().

        """
        interface = cast('ReplayInterface', timer.bluetooth_interface)

        getch_stub = (
            getch_blocked if solve.get('finish_moves') else make_getch_save()
        )

        async with replay_consumer_running(timer):
            with patch.object(timer, 'getch', side_effect=getch_stub):
                run_task = asyncio.create_task(timer.start())
                await interface.send_init_commands()

                return await asyncio.wait_for(run_task, timeout=5.0)

    @staticmethod
    async def drive_attempt(
            timer: Timer, save_char: str,
    ) -> tuple[bool, Algorithm | None]:
        """
        Drive a single run_attempt(), without the retry loop of start().

        A retry asks start() for a second attempt, but the replay schedule
        only holds the events of one solve, so the loop would wait
        forever: the retry is observed on run_attempt() instead.

        Args:
            timer:     A Timer wired with a ReplayInterface.
            save_char: The key answering the save prompt.

        Returns:
            The (keep going, scramble to replay) pair run_attempt()
            returned.

        """
        interface = cast('ReplayInterface', timer.bluetooth_interface)

        async with replay_consumer_running(timer):
            with patch.object(
                    timer, 'getch', side_effect=make_getch_save(save_char),
            ):
                run_task = asyncio.create_task(timer.run_attempt())
                await interface.send_init_commands()

                return await asyncio.wait_for(run_task, timeout=5.0)

    async def test_full_replay_records_solve(self) -> None:
        """A replay drives scramble, solve and save without hardware."""
        replay = validate_replay(deepcopy(VALID_REPLAY))
        timer = build_replay_timer(replay)

        result = await self.drive_solve(timer, replay['solves'][0])

        self.assertTrue(result)
        self.assertEqual(len(timer.moves), 4)
        self.assertEqual(len(timer.stack_done), 1)
        self.assertEqual(timer.stack_done[0].flag, '')
        self.assertTrue(timer.bluetooth_scramble_is_completed)
        self.save_solves_mock.assert_called()

    async def test_retry_replays_the_same_scramble(self) -> None:
        """Pressing 'r' at the save prompt asks to replay the scramble."""
        replay = validate_replay(deepcopy(VALID_REPLAY))
        timer = build_replay_timer(replay)
        counter = timer.counter

        keep_going, pending = await self.drive_attempt(timer, 'r')

        self.assertTrue(keep_going)
        self.assertIsNotNone(pending)
        self.assertEqual(str(pending), str(timer.scramble))

        # The attempt is forgotten: nothing recorded, nothing counted
        self.assertEqual(timer.stack, [])
        self.assertEqual(timer.stack_done, [])
        self.assertEqual(timer.counter, counter)

    async def test_save_closes_the_attempt(self) -> None:
        """Without a retry, run_attempt() asks for no replay at all."""
        replay = validate_replay(deepcopy(VALID_REPLAY))
        timer = build_replay_timer(replay)
        counter = timer.counter

        keep_going, pending = await self.drive_attempt(timer, '')

        self.assertTrue(keep_going)
        self.assertIsNone(pending)
        self.assertEqual(len(timer.stack_done), 1)
        self.assertEqual(timer.counter, counter + 1)
        self.save_solves_mock.assert_called()

    async def test_full_replay_synthesized_scramble(self) -> None:
        """A replay without scramble_moves synthesizes them and still runs."""
        replay = validate_replay(deepcopy(VALID_REPLAY))
        del replay['solves'][0]['scramble_moves']
        timer = build_replay_timer(replay)

        result = await self.drive_solve(timer, replay['solves'][0])

        self.assertTrue(result)
        self.assertEqual(len(timer.stack_done), 1)
        self.assertEqual(timer.stack_done[0].flag, '')

    async def test_save_gesture_saves_and_quits(self) -> None:
        """A D D' finish gesture answers the save prompt with save & quit."""
        replay = validate_replay(deepcopy(VALID_REPLAY))
        replay['solves'][0]['finish_moves'] = "D@0 D'@250"
        timer = build_replay_timer(replay)

        result = await self.drive_solve(timer, replay['solves'][0])

        self.assertFalse(result)
        self.assertEqual(len(timer.stack_done), 1)
        self.assertEqual(timer.stack_done[0].flag, '')
        self.save_solves_mock.assert_called()

    async def test_save_gesture_saves_and_continues(self) -> None:
        """A U U' finish gesture saves and moves on to the next solve."""
        replay = validate_replay(deepcopy(VALID_REPLAY))
        replay['solves'][0]['finish_moves'] = "U@0 U'@250"
        timer = build_replay_timer(replay)

        result = await self.drive_solve(timer, replay['solves'][0])

        self.assertTrue(result)
        self.assertEqual(len(timer.stack_done), 1)
        self.assertEqual(timer.stack_done[0].flag, '')
        self.save_solves_mock.assert_called()

    async def test_zero_delay_no_leaked_moves(self) -> None:
        """
        Explicit 0.0 delays don't leak moves once phases are state-gated.

        In v1 this raced: the first scramble or solution move could be
        consumed before the timer reached the expected state. v2 gates
        each phase on the real state transition instead, so 0 is safe.
        """
        replay = validate_replay(deepcopy(VALID_REPLAY))
        replay['solves'][0]['finish_moves'] = "U@0 U'@10"
        replay['solves'][0]['save_delay'] = 0.0
        timer = build_replay_timer(replay)

        result = await self.drive_solve(timer, replay['solves'][0])

        self.assertTrue(result)
        self.assertEqual(len(timer.moves), 4)
        self.assertEqual(len(timer.stack_done), 1)
        self.assertEqual(timer.stack_done[0].flag, '')

    async def test_multi_solve_end_to_end(self) -> None:
        """
        Two solves chained by finish_moves both complete via the schedule.

        Deterministic in v2 only: the schedule waits for the timer to be
        back in 'scrambling' for the second solve instead of racing it.
        """
        data: dict[str, Any] = deepcopy(VALID_REPLAY)
        data['solves'].append(deepcopy(data['solves'][0]))
        data['solves'][0]['finish_moves'] = "U@0 U'@250"
        replay = validate_replay(data)
        timer = build_replay_timer(replay)

        interface = cast('ReplayInterface', timer.bluetooth_interface)
        queue = cast('EventQueue', timer.bluetooth_queue)

        consumer = asyncio.create_task(timer.bluetooth_consumer())
        timer.bluetooth_consumer_ref = consumer

        async def getch_stub(mode: str, *_: object) -> str:
            # Only the last solve's save prompt has no gesture to answer
            # it; every other prompt blocks and lets the schedule drive.
            # 'q' mirrors the D D' gesture used elsewhere: save & quit.
            if mode == 'save' and timer.scramble_index >= len(
                    timer.scrambles,
            ):
                return 'q'
            await asyncio.sleep(3600)
            return ''

        try:
            with patch.object(timer, 'getch', side_effect=getch_stub):
                await interface.send_init_commands()

                first_result = await asyncio.wait_for(
                    timer.start(), timeout=5.0,
                )
                second_result = await asyncio.wait_for(
                    timer.start(), timeout=5.0,
                )
        finally:
            await queue.put(None)
            await consumer

        self.assertTrue(first_result)
        self.assertFalse(second_result)
        self.assertEqual(len(timer.stack_done), 2)
        self.assertEqual(timer.stack_done[0].flag, '')
        self.assertEqual(timer.stack_done[1].flag, '')
        self.save_solves_mock.assert_called()
