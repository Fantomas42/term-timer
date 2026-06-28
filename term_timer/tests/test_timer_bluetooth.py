"""
Bluetooth Timer scenario tests.

Drives Timer.start() with a simulated Bluetooth cube, reusing the fake
BT helpers from test_trainer_bluetooth. Focuses on the interaction
between keyboard start/stop and the Bluetooth cube state.
"""
import asyncio
import unittest
from random import Random
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import patch

from cubing_algs.vcube import VCube

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.constants import SolveFlag
from term_timer.solve import Solve
from term_timer.tests.test_trainer_bluetooth import FakeBluetoothInterface
from term_timer.tests.test_trainer_bluetooth import make_move_event
from term_timer.tests.test_trainer_bluetooth import wait_until
from term_timer.timer import Timer

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import EventDict


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
