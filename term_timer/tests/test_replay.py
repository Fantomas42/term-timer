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
from copy import deepcopy
from pathlib import Path
from random import Random
from typing import Any
from typing import cast
from unittest.mock import patch

from cubing_algs.parsing import parse_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.replay import HUMAN_SCRAMBLE_PACE_MS
from term_timer.bluetooth.replay import ReplayFileDict
from term_timer.bluetooth.replay import ReplayInterface
from term_timer.bluetooth.replay import ReplaySolveDict
from term_timer.bluetooth.replay import load_replay
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
    instance.bluetooth_interface = ReplayInterface(queue, replay)
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


async def getch_only_save(mode: str, *_: object) -> str:
    """
    Getch stub that only answers the save prompt.

    Every other prompt blocks so the replay events drive the transitions.

    Args:
        mode: The prompt mode requested by the timer.

    Returns:
        An empty string at the save prompt, never returns otherwise.

    """
    if mode == 'save':
        return ''
    await asyncio.sleep(3600)
    return ''


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

    async def test_schedule_event_sequence(self) -> None:
        """Init events precede the scramble and solution move events."""
        replay = validate_replay(deepcopy(VALID_REPLAY))

        queue: EventQueue = asyncio.Queue()
        interface = ReplayInterface(queue, replay)

        await interface.send_init_commands()
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

        queue: EventQueue = asyncio.Queue()
        interface = ReplayInterface(queue, replay)

        await interface.send_init_commands()
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

        queue: EventQueue = asyncio.Queue()
        interface = ReplayInterface(queue, replay)

        await interface.send_init_commands()
        await asyncio.wait_for(
            cast('asyncio.Task[None]', interface.schedule_task), timeout=5.0,
        )

        names = self.drain(queue)

        # 2 solves x (4 scramble + 4 solution moves) + 2 gesture moves.
        self.assertEqual(names.count('move'), 18)


class TestReplayInterfaceFlow(unittest.IsolatedAsyncioTestCase):
    """Full Timer.start() run driven deterministically by a ReplayInterface."""

    def setUp(self) -> None:
        """Patch solve persistence and sound playback for each test."""
        save_patcher = patch('term_timer.interface.save_solves')
        self.save_solves_mock = save_patcher.start()
        self.addCleanup(save_patcher.stop)

        sound_patcher = patch(
            'term_timer.interface.sounds.sd', create=True,
        )
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    async def drive_solve(timer: Timer, solve: ReplaySolveDict) -> bool:
        """
        Drive one full solve, playing each phase once the state is ready.

        Waiting for the timer state before injecting each phase keeps the
        run deterministic, independent of the schedule's wall-clock pacing.

        Args:
            timer: A Timer wired with a ReplayInterface.
            solve: The replay solve providing scramble_moves, solution
                and the optional finish_moves save gesture.

        Returns:
            The bool returned by Timer.start().

        """
        interface = cast('ReplayInterface', timer.bluetooth_interface)
        queue = cast('EventQueue', timer.bluetooth_queue)

        consumer = asyncio.create_task(timer.bluetooth_consumer())
        timer.bluetooth_consumer_ref = consumer

        timed_scramble = parse_timed_moves(
            solve.get('scramble_moves') or solve['scramble'],
        )

        finish_moves = solve.get('finish_moves')
        getch_stub = getch_blocked if finish_moves else getch_only_save

        try:
            with patch.object(timer, 'getch', side_effect=getch_stub):
                run_task = asyncio.create_task(timer.start())

                await wait_until(lambda: timer.state == 'scrambling')
                await interface.play_moves(timed_scramble)
                await asyncio.wait_for(
                    timer.scramble_completed_event.wait(), timeout=2.0,
                )

                await wait_until(lambda: timer.state == 'scrambled')
                await interface.play_moves(
                    parse_timed_moves(solve['solution']),
                )

                if finish_moves:
                    await wait_until(lambda: timer.state == 'saving')
                    await interface.play_moves(
                        parse_timed_moves(finish_moves),
                    )

                return await asyncio.wait_for(run_task, timeout=5.0)
        finally:
            await queue.put(None)
            await consumer

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


if __name__ == '__main__':
    unittest.main()
