"""
Bluetooth Trainer scenario harness.

Infrastructure for testing Trainer with a simulated Bluetooth cube,
without a physical device.

Two usage patterns:

  1. Full start() runs
     Build a Trainer, run start() as a background task, inject BT move events
     progressively. Access trainer properties mid-run or after completion.

  2. Unit-level
     Build a Trainer, set state manually, call individual methods directly
     (bluetooth_scramble_is_completed, solve_line, …).
"""
import asyncio
import unittest
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from random import Random
from typing import ClassVar
from typing import cast
from unittest.mock import patch

from cubing_algs.cases import get_case
from cubing_algs.cases import get_collection
from cubing_algs.transform.degrip import degrip_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND
from term_timer.orientation import get_orientation_moves
from term_timer.trainer import Trainer
from term_timer.training import CaseTraining
from term_timer.training import Trainings


class FakeBluetoothClient:
    """Minimal BLE client stub that satisfies truthy checks and .client.name."""

    name: str = 'FakeCube'
    is_connected: bool = True


class FakeBluetoothInterface:
    """Truthy BT interface stub - no real BLE calls."""

    client: FakeBluetoothClient = FakeBluetoothClient()
    driver: None = None

    async def send_command(self, command: str) -> None:
        """Accept any command without side effects."""


def make_move_event(move: str, clock: int = 0) -> list[EventDict]:
    """
    Build a BT queue payload for a single face move.

    Args:
        move: Move string, e.g. 'R', "U'", 'F2'.
        clock: Nanosecond clock value (used for timing reconstruction).

    Returns:
        A one-element list ready to put into trainer.bluetooth_queue.

    """
    event: MoveEventDict = {
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
    result: list[EventDict] = [event]
    return result


def build_trainer(  # noqa: PLR0913
        step: str = 'oll',
        case_codes: list[str] | None = None,
        *,
        initial_cube: VCube | None = None,
        seed: int = 42,
        free_play: bool = False,
        orientation: str = 'UF',
) -> Trainer:
    """
    Build a Trainer with a fake Bluetooth cube and mocked training I/O.

    load_trainings returns an empty Trainings; save_trainings is a no-op.
    bluetooth_queue is a real asyncio.Queue, bluetooth_cube is set to a copy
    of initial_cube (default: solved 3x3x3).

    Note: Trainer.__init__ prints a summary line via Rich console. This is
    expected noise during tests. Redirect trainer.console to suppress it.

    Args:
        step: Training step ('oll', 'pll', 'f2l', 'cross', 'ecross', 'xcross').
        case_codes: Cases to include; empty list means all available cases.
        initial_cube: BT cube state at connection time. Defaults to solved.
        seed: RNG seed - use a fixed value for reproducible scramble selection.
        free_play: Skip the save-and-confirm phase at the end of each solve.
        orientation: The orientation of the cube.

    Returns:
        Configured Trainer ready for testing.

    """
    cube = (initial_cube or VCube(size=3)).copy()
    empty_trainings = Trainings(method='CFOP', step=step.upper(), cases={})

    with patch(
        'term_timer.trainer.load_trainings',
        return_value=empty_trainings,
    ):
        instance = Trainer(
            step=step,
            case_codes=case_codes or [],
            oldest=0,
            slowest=0,
            filters=[],
            free_play=free_play,
            show_solution=False,
            show_cube=False,
            orientation=orientation,
            metronome=0.0,
            rng=Random(seed),  # noqa: S311
        )

    # Mirror what bluetooth_connect() wires up in production
    instance.bluetooth_queue = asyncio.Queue()
    instance.bluetooth_cube = cube
    instance.bluetooth_interface = FakeBluetoothInterface()  # type: ignore[assignment]
    instance.facelets_received_event.set()
    instance.hardware_received_event.set()

    return instance


async def inject_moves(
        trainer: Trainer,
        moves: list[str],
        *,
        clock_start: int = 0,
        clock_step: int = 100 * MS_TO_NS_FACTOR,
) -> None:
    """
    Feed a sequence of BT move events into the trainer queue.

    Yields to the event loop after each move so the BT consumer can process
    it before the next one arrives.

    Args:
        trainer: Target Trainer instance (must have bluetooth_queue set).
        moves: Ordered list of move strings, e.g. ['R', 'U', "R'"].
        clock_start: Nanosecond clock value for the first move.
        clock_step: Nanosecond increment between consecutive moves.

    """
    queue = cast(
        'asyncio.Queue[list[EventDict] | None]', trainer.bluetooth_queue,
    )
    for i, move_str in enumerate(moves):
        clock = clock_start + i * clock_step
        await queue.put(make_move_event(move_str, clock))
        await asyncio.sleep(0)


def make_auto_getch(save_char: str = 'q') -> Callable[..., Awaitable[str]]:
    """
    Return an async getch() replacement for use with patch.object.

    Non-save phases sleep indefinitely and are cancelled by BT events.
    The save phase returns save_char immediately.

    Args:
        save_char: Character to return at the save prompt.
                   '' or any printable char = save the timing.
                   'z'                      = cancel (discard timing).
                   'q'                      = save and quit (returns False).

    Returns:
        Async callable usable as a getch() side_effect.

    """
    async def _getch(mode: str, *_args: object) -> str:
        if mode == 'save':
            return save_char
        await asyncio.sleep(3600)
        return ''

    return _getch


async def run_full_cycle(
        trainer: Trainer,
        solve_moves: list[str],
        *,
        save_char: str = 'q',
        scramble_moves: list[str] | None = None,
) -> Trainer:
    """
    Drive one complete start() cycle on an already-built Trainer.

    Reads t.scramble after start() has set it to derive the scramble-phase
    injection, then drives all four phases via BT event injection and the
    getch mock. Returns the Trainer after start() completes.

    Phase timing
    ------------
    Phase 1 - Scramble: inject moves that bring bluetooth_cube to
              facelets_scrambled. Defaults to t.scramble (the algorithm
              start() generated). Pass scramble_moves to override.

    Phase 2 - First solve move: fires solve_started_event (lands in
              'scrambled' state). A 50 ms sleep follows so wait_solve()
              and time_solve() run and state advances to 'solving'.

    Phase 3 - Remaining solve moves: processed in 'solving' state,
              each triggers bluetooth_scramble_is_completed check.

    Phase 4 - Save: getch mock returns save_char immediately.

    Args:
        trainer:        Trainer built with build_trainer().
        solve_moves:    Moves that make bluetooth_scramble_is_completed True.
        save_char:      '' / printable = save, 'z' = cancel, 'q' = quit.
        scramble_moves: Override for scramble-phase injection. Defaults to
                        the moves in t.scramble.

    Returns:
        The same Trainer instance after start() has returned.

    """
    consumer = asyncio.create_task(trainer.bluetooth_consumer())
    trainer.bluetooth_consumer_ref = consumer

    try:
        with patch.object(
                trainer, 'getch', side_effect=make_auto_getch(save_char),
        ):
            run_task = asyncio.create_task(trainer.start())

            # Let start() call trainer() and set scramble / facelets_scrambled
            await asyncio.sleep(0.05)

            # Phase 1: scramble
            s_moves = scramble_moves or [str(m) for m in trainer.scramble]
            await inject_moves(
                trainer,
                s_moves,
                clock_start=0,
            )
            await asyncio.wait_for(
                trainer.scramble_completed_event.wait(),
                timeout=2.0,
            )
            # wait_control() cancels the getch task asynchronously; wait for
            # scramble_solve() to call set_state('scrambled') before we inject
            # the first solve move (must land in 'scrambled', not
            # 'scrambling')
            await asyncio.sleep(0.05)

            # Phase 2: first solve move (starts the timer)
            solve_clock = len(s_moves) * (100 * MS_TO_NS_FACTOR) + SECOND
            await inject_moves(
                trainer,
                [solve_moves[0]],
                clock_start=solve_clock,
            )
            await asyncio.wait_for(
                trainer.solve_started_event.wait(),
                timeout=1.0,
            )
            # Let wait_solve() return and stopwatch() call set_state('solving')
            # before remaining moves land; only 'solving'-state moves trigger
            # the bluetooth_scramble_is_completed check
            await asyncio.sleep(0.05)

            # Phase 3: remaining solve moves (trigger completion)
            if len(solve_moves) > 1:
                await inject_moves(
                    trainer,
                    solve_moves[1:],
                    clock_start=solve_clock + 200 * MS_TO_NS_FACTOR,
                )
            await asyncio.wait_for(
                trainer.solve_completed_event.wait(),
                timeout=2.0,
            )

            # Phase 4: save prompt (handled by getch mock)
            await asyncio.wait_for(
                run_task,
                timeout=2.0,
            )
    finally:
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', trainer.bluetooth_queue,
        )
        await queue.put(None)
        await consumer

    return trainer


class SaveTrainingsPatchedTestCase(unittest.IsolatedAsyncioTestCase):
    """Base test case that patches save_trainings to prevent writes."""

    def setUp(self) -> None:
        """Patch save_trainings for the duration of each test."""
        patcher = patch('term_timer.trainer.save_trainings')
        patcher.start()
        self.addCleanup(patcher.stop)


class BluetoothTrainerTestCase(SaveTrainingsPatchedTestCase):
    """
    Base class for Trainer bluetooth scenario tests.

    Set step / case_codes / seed as class attributes. Each test gets a fresh
    Trainer via make_trainer(). Subclass and override as needed.

    Class attributes:
        step:       Training step for tests in this class.
        case_codes: Cases to include; empty list = all cases.
        seed:       RNG seed for reproducible scramble selection.

    """

    step: ClassVar[str] = 'oll'
    case_codes: ClassVar[list[str]] = []
    seed: ClassVar[int] = 42

    def make_trainer(
            self,
            *,
            initial_cube: VCube | None = None,
            seed: int | None = None,
            free_play: bool = False,
            orientation: str = 'UF',
    ) -> Trainer:
        """
        Create a fresh Trainer with fake BT for this test.

        Returns:
            Configured Trainer instance with mocked BT.

        """
        return build_trainer(
            step=self.step,
            case_codes=self.case_codes,
            initial_cube=initial_cube,
            seed=seed if seed is not None else self.seed,
            free_play=free_play,
            orientation=orientation,
        )


class TestTrainerOLL01(BluetoothTrainerTestCase):
    """Unit and integration tests for OLL case 01, UF/DF orientations."""

    step = 'oll'
    case_codes: ClassVar[list[str]] = ['01']
    seed = 42

    def test_cases_match_requested_codes(self) -> None:
        """Trainer exposes exactly the requested cases."""
        t = self.make_trainer()

        self.assertEqual(len(t.cases), 1)
        self.assertEqual(t.cases[0].case.code, '01')

    def test_bluetooth_cube_reflects_initial_state(self) -> None:
        """bluetooth_cube_state matches the initial_cube passed in."""
        oll_case = get_case('OLL', '01')
        setup = next(iter(oll_case.setup_algorithms))
        initial = VCube(size=3)
        initial.rotate(setup)

        t = self.make_trainer(initial_cube=initial)

        self.assertFalse(t.bluetooth_cube_is_solved)
        self.assertEqual(t.bluetooth_cube_state, initial.state)

    def test_select_oldest_cases_prioritises_unpractised(self) -> None:
        """Cases with no training data sort before practised ones."""
        t = self.make_trainer(seed=0)

        collection = get_collection('CFOP/OLL').cases
        valid_cases = {
            code: case
            for code, case in collection.items()
            if case.setup_algorithms
        }
        two_cases = dict(list(valid_cases.items())[:2])
        first_code, second_code = list(two_cases.keys())

        t.trainings.cases[first_code] = CaseTraining(
            code=first_code,
            last_date=1,
            timings=[1],
        )

        selected = t.select_oldest_cases(two_cases, count=1)

        self.assertEqual(selected, [second_code])

    async def test_scramble_properties_by_orientation(self) -> None:
        """
        Verify scramble/scramble_oriented/facelets_scrambled per orientation.

        UF: no reorientation - scramble == scramble_oriented, both in setups.
        DF: z2 reorientation - scramble uses D-face moves (not in raw setups),
            scramble_oriented translates back to canonical UF form.
        Solve moves must be expressed in the orientation frame so that
        bluetooth_scramble_is_completed can translate them back to UF.
        """
        oll_case = get_case('OLL', '01')
        solution = next(iter(oll_case.algorithms))
        valid_setups = {str(s) for s in oll_case.setup_algorithms}
        om_df = get_orientation_moves('DF')
        om_rd = get_orientation_moves('RD')

        scenarios = [
            ('UF', [str(m) for m in solution]),
            ('DF', [str(m) for m in degrip_moves(om_df + solution)]),
            ('RD', [str(m) for m in degrip_moves(om_rd + solution)]),
        ]

        for orientation, solve_moves in scenarios:
            with self.subTest(orientation=orientation):
                t = self.make_trainer(orientation=orientation)
                await run_full_cycle(t, solve_moves, save_char='q')

                # scramble_oriented is always the canonical UF form
                self.assertIn(str(t.scramble_oriented), valid_setups)

                # facelets_scrambled formula holds regardless of orientation
                expected = VCube(size=3)
                expected.rotate(t.scramble)
                self.assertEqual(t.facelets_scrambled, expected.state)

                if orientation == 'UF':
                    self.assertIn(str(t.scramble), valid_setups)
                    self.assertEqual(
                        str(t.scramble),
                        "L F' L' F U F2 R' F' R U' F'",
                    )
                    self.assertEqual(
                        str(t.scramble_oriented),
                        "L F' L' F U F2 R' F' R U' F'",
                    )
                elif orientation == 'DF':
                    self.assertNotIn(str(t.scramble), valid_setups)
                    self.assertEqual(
                        str(t.scramble),
                        "R F' R' F D F2 L' F' L D' F'",
                    )
                    self.assertEqual(
                        str(t.scramble_oriented),
                        "L F' L' F U F2 R' F' R U' F'",
                    )
                elif orientation == 'RD':
                    self.assertNotIn(str(t.scramble), valid_setups)
                    self.assertEqual(
                        str(t.scramble),
                        "F D' F' D R D2 B' D' B R' D'",
                    )
                    self.assertEqual(
                        str(t.scramble_oriented),
                        "L F' L' F U F2 R' F' R U' F'",
                    )


class TestConcreteScenarios(SaveTrainingsPatchedTestCase):
    """
    Concrete-value scenarios driven by run_scenario().

    Each test method calls run_scenario() with explicit values.  Add a new
    test method per scenario - no subclassing required.

    Example:
        async def test_oll_01_uf(self) -> None:
            await self.run_scenario(
                step='oll',
                case_code='01',
                scramble_moves=["R", "U", "R'"],
                solve_moves=["R", "U'", "R'"],
                expected_scramble="R U R'",
                expected_scramble_oriented="R U R'",
            )

    """

    async def run_scenario(  # noqa: PLR0913
            self,
            *,
            step: str,
            case_code: str,
            scramble_moves: list[str],
            solve_moves: list[str],
            expected_scramble: str | None = None,
            expected_scramble_oriented: str | None = None,
            initial_facelet_state: str | None = None,
            orientation: str = 'UF',
            seed: int = 42,
            save_char: str = '',
    ) -> Trainer:
        """
        Drive one complete Trainer cycle and assert all scenario properties.

        Args:
            step: Training step ('oll', 'pll', …).
            case_code: Single case code to train (e.g. '01').
            scramble_moves: Moves that bring the BT cube to facelets_scrambled.
            solve_moves: Moves that make bluetooth_scramble_is_completed True.
            expected_scramble: Expected str(t.scramble); skipped when None.
            expected_scramble_oriented: Expected str(t.scramble_oriented);
                skipped when None.
            initial_facelet_state: 54-char facelet string for the BT cube at
                connection time, or None for a solved cube.
            orientation: Cube orientation ('UF', 'DF', …).
            seed: RNG seed for scramble selection.
            save_char: '' = save, 'z' = cancel, 'q' = save-and-quit.

        Asserts:
            - BT cube initial state matches initial_facelet_state.
            - t.scramble == expected_scramble (when not None).
            - t.scramble_oriented == expected_scramble_oriented (when not None).
            - t.facelets_scrambled == VCube(initial).rotate(t.scramble).state.
            - elapsed_time > 0 and one timing entry recorded for case_code.

        Returns:
            The Trainer after start() completes (for extra per-test assertions).

        """
        initial: VCube | None = None
        if initial_facelet_state is not None:
            initial = VCube(initial_facelet_state, size=3, check=False)

        t = build_trainer(
            step=step,
            case_codes=[case_code],
            initial_cube=initial,
            seed=seed,
            orientation=orientation,
        )

        expected_initial = (initial or VCube(size=3)).state
        self.assertEqual(
            t.bluetooth_cube_state,
            expected_initial,
        )

        await run_full_cycle(
            t,
            solve_moves,
            save_char=save_char,
            scramble_moves=scramble_moves,
        )

        if expected_scramble is not None:
            self.assertEqual(
                str(t.scramble),
                expected_scramble,
            )
        if expected_scramble_oriented is not None:
            self.assertEqual(
                str(t.scramble_oriented),
                expected_scramble_oriented,
            )

        self.assertGreater(t.elapsed_time, 0)

        if save_char == 'z':
            case_entry = t.trainings.cases.get(case_code)
            if case_entry is not None:
                self.assertEqual(len(case_entry.timings), 0)
        else:
            self.assertIn(
                case_code,
                t.trainings.cases,
                f'case {case_code!r} missing from trainings after save',
            )
            self.assertEqual(len(t.trainings.cases[case_code].timings), 1)

        return t

    @staticmethod
    async def run_interrupted_solve_cycle(
            trainer: Trainer,
            bad_solve_moves: list[str],
    ) -> bool:
        """
        Run one DNF cycle: normal scramble, bad solve moves, keyboard interrupt.

        Args:
            trainer: Target Trainer instance with fake BT attached.
            bad_solve_moves: Moves to inject during the solve phase before
                the keyboard interrupt fires.

        Returns:
            The bool returned by start() (True = continue, False = quit).

        """
        stop_event = asyncio.Event()

        async def getch_with_stop(mode: str, *_: object) -> str:
            if mode == 'stop':
                await stop_event.wait()
                return ' '
            await asyncio.sleep(3600)
            return ''

        consumer = asyncio.create_task(trainer.bluetooth_consumer())
        trainer.bluetooth_consumer_ref = consumer
        try:
            with patch.object(trainer, 'getch', side_effect=getch_with_stop):
                run_task = asyncio.create_task(trainer.start())
                await asyncio.sleep(0.05)

                s_moves = [str(m) for m in trainer.scramble]
                await inject_moves(trainer, s_moves, clock_start=0)
                await asyncio.wait_for(
                    trainer.scramble_completed_event.wait(),
                    timeout=2.0,
                )
                await asyncio.sleep(0.05)

                solve_clock = len(s_moves) * (100 * MS_TO_NS_FACTOR) + SECOND
                await inject_moves(
                    trainer,
                    bad_solve_moves[:1],
                    clock_start=solve_clock,
                )
                await asyncio.wait_for(
                    trainer.solve_started_event.wait(),
                    timeout=1.0,
                )
                await asyncio.sleep(0.05)

                if len(bad_solve_moves) > 1:
                    await inject_moves(
                        trainer,
                        bad_solve_moves[1:],
                        clock_start=solve_clock + 200 * MS_TO_NS_FACTOR,
                    )
                await asyncio.sleep(0.05)

                stop_event.set()
                return await asyncio.wait_for(run_task, timeout=2.0)
        finally:
            queue = cast(
                'asyncio.Queue[list[EventDict] | None]',
                trainer.bluetooth_queue,
            )
            await queue.put(None)
            await consumer

    async def test_oll_01_elapsed_time_and_timing(self) -> None:
        """OLL case 01: elapsed_time and timing saved after a full solve."""
        solution = next(iter(get_case('OLL', '01').algorithms))
        solve_moves = [str(m) for m in solution]

        t = await self.run_scenario(
            step='oll',
            case_code='01',
            scramble_moves=[],
            solve_moves=solve_moves,
            save_char='',
            expected_scramble="L F' L' F U F2 R' F' R U' F'",
            expected_scramble_oriented="L F' L' F U F2 R' F' R U' F'",
        )

        self.assertGreater(len(t.moves), 0)

    async def test_oll_01_cancel_discards_timing(self) -> None:
        """Pressing 'z' at the save prompt cancels - timing is removed."""
        solution = next(iter(get_case('OLL', '01').algorithms))
        solve_moves = [str(m) for m in solution]

        await self.run_scenario(
            step='oll',
            case_code='01',
            scramble_moves=[],
            solve_moves=solve_moves,
            save_char='z',
            expected_scramble="L F' L' F U F2 R' F' R U' F'",
            expected_scramble_oriented="L F' L' F U F2 R' F' R U' F'",
        )

    async def test_oll_01_scramble_completed_bt_cube(self) -> None:
        """
        OLL case 01: full cycle completes when BT cube is unsolved at start,
        and the scramble is considered completed.

        facelets_scrambled is derived from the actual BT cube state, not a
        solved baseline - the extra assertion below confirms this.
        """
        oll_case = get_case('OLL', '01')
        solution = next(iter(oll_case.algorithms))
        solve_moves = [str(m) for m in solution]

        initial = VCube(size=3)
        # T-Perm: break OLL, but consider scramble is solved
        initial.rotate("R U R' U' R' F R2 U' R' U' R U R' F'")

        t = await self.run_scenario(
            step='oll',
            case_code='01',
            scramble_moves=[],
            solve_moves=solve_moves,
            initial_facelet_state=initial.state,
            expected_scramble="L F' L' F U F2 R' F' R U' F'",
            expected_scramble_oriented="L F' L' F U F2 R' F' R U' F'",
        )

        solved_target = VCube(size=3)
        solved_target.rotate(t.scramble)
        self.assertNotEqual(
            t.facelets_scrambled,
            solved_target.state,
        )

    async def test_oll_01_highly_scrambled_bt_cube(self) -> None:
        """
        OLL case 01: full cycle completes when BT cube is unsolved at start,
        and the scramble is considered not completed.

        facelets_scrambled is derived from the actual BT cube state, not a
        solved baseline - the extra assertion below confirms this.
        """
        oll_case = get_case('OLL', '01')
        solution = next(iter(oll_case.algorithms))
        solve_moves = [str(m) for m in solution]

        initial = VCube(size=3)
        initial.rotate("R2 B D2 L U F2 R2 D L2 B' U2 R' D")

        scramble_moves = "R2 D' R' F' L' F R U2 R F L U F2 D2 B2 U2 F2 R2 D B2"

        t = await self.run_scenario(
            step='oll',
            case_code='01',
            scramble_moves=scramble_moves.split(),
            solve_moves=solve_moves,
            initial_facelet_state=initial.state,
            expected_scramble="L F' L' F U F2 R' F' R U' F'",
            expected_scramble_oriented=scramble_moves,
        )

        solved_target = VCube(size=3)
        solved_target.rotate(t.scramble)
        self.assertEqual(
            t.facelets_scrambled,
            solved_target.state,
        )

    async def test_chained_training_cycles(self) -> None:
        """
        Two OLL-01 cycles chain correctly; BT cube stays unsolved between
        rounds - verified for both UF and DF orientations.

        alg[3] passes the OLL check_step but is not the inverse of setup[0],
        so the BT cube is left in a non-solved state after each cycle.  Cycle 2
        starts from that unsolved state; facelets_scrambled must incorporate
        that state (verified post-cycle via the defining formula).
        """
        oll_case = get_case('OLL', '01')
        alg3 = list(oll_case.algorithms)[3]

        for orientation in ('UF', 'DF', 'RD'):
            with self.subTest(orientation=orientation):
                om = get_orientation_moves(orientation)
                solve_moves = [str(m) for m in degrip_moves(om + alg3)]

                t = build_trainer(
                    step='oll',
                    case_codes=['01'],
                    seed=42,
                    orientation=orientation,
                )

                # Cycle 1
                await run_full_cycle(t, solve_moves, save_char='q')

                self.assertFalse(
                    t.bluetooth_cube_is_solved,
                    'BT cube must not be fully solved after an OLL solve',
                )
                self.assertTrue(t.bluetooth_scramble_is_completed)

                # Cycle 2
                state_before_cycle2 = t.bluetooth_cube_state

                await run_full_cycle(t, solve_moves, save_char='q')

                self.assertFalse(
                    t.bluetooth_cube_is_solved,
                    'BT cube must not be fully solved after the final OLL '
                    'solve',
                )
                self.assertTrue(t.bluetooth_scramble_is_completed)

                expected = VCube(state_before_cycle2, size=3, check=False)
                expected.rotate(t.scramble)

                self.assertEqual(
                    t.facelets_scrambled,
                    expected.state,
                    'facelets_scrambled must be computed from the unsolved '
                    'BT cube state',
                )

    async def test_bad_solve_interrupted_then_valid_solve(self) -> None:
        """
        Two-cycle OLL-01 scenario where cycle 1 is a DNF.

        Cycle 1: scramble completes normally, user makes bad moves during
        solving, then interrupts by pressing a key (getch 'stop' fires).
        The solve is flagged DNF - not saved to trainings - and the BT cube
        is left in a scrambled state (neither solved nor at OLL case).

        Cycle 2: bluetooth_scramble_is_completed is False, so the trainer
        computes a facelets-to-facelets path from the scrambled BT cube
        state to the OLL 01 target as scramble_oriented. Injecting those
        moves brings the BT cube to facelets_scrambled; the user then
        solves OLL correctly and timing is saved.
        """
        oll_case = get_case('OLL', '01')
        solution = next(iter(oll_case.algorithms))
        solve_moves = [str(m) for m in solution]

        # F R U R' U' F' changes corner orientations without solving OLL 01
        bad_solve_moves = ['F', 'R', 'U', "R'", "U'", "F'"]

        t = build_trainer(step='oll', case_codes=['01'], seed=42)

        # Cycle 1: good scramble, bad solve, keyboard interrupt
        cycle1_result = await TestConcreteScenarios.run_interrupted_solve_cycle(
            t, bad_solve_moves,
        )

        # DNF: start() returns True (continue), no timing saved
        self.assertTrue(cycle1_result)
        self.assertIsNone(t.trainings.cases.get('01'))
        self.assertFalse(t.bluetooth_cube_is_solved)
        self.assertFalse(
            t.bluetooth_scramble_is_completed,
            'bad moves must not accidentally complete OLL',
        )

        # Cycle 2: scramble from messy BT state, valid OLL solve
        consumer2 = asyncio.create_task(t.bluetooth_consumer())
        t.bluetooth_consumer_ref = consumer2

        try:
            with patch.object(
                    t, 'getch', side_effect=make_auto_getch(''),
            ):
                run_task2 = asyncio.create_task(t.start())
                await asyncio.sleep(0.05)

                # scramble_oriented is the facelets-to-facelets path from the
                # scrambled BT cube to the OLL 01 target state
                s_moves2 = [str(m) for m in t.scramble_oriented]
                await inject_moves(
                    t,
                    s_moves2,
                    clock_start=0,
                )
                await asyncio.wait_for(
                    t.scramble_completed_event.wait(),
                    timeout=5.0,
                )
                await asyncio.sleep(0.05)

                solve_clock2 = (
                    len(s_moves2) * (100 * MS_TO_NS_FACTOR) + SECOND
                )
                await inject_moves(
                    t,
                    [solve_moves[0]],
                    clock_start=solve_clock2,
                )
                await asyncio.wait_for(
                    t.solve_started_event.wait(),
                    timeout=1.0,
                )
                await asyncio.sleep(0.05)

                if len(solve_moves) > 1:
                    await inject_moves(
                        t,
                        solve_moves[1:],
                        clock_start=solve_clock2 + 200 * MS_TO_NS_FACTOR,
                    )
                await asyncio.wait_for(
                    t.solve_completed_event.wait(),
                    timeout=2.0,
                )
                await asyncio.wait_for(
                    run_task2,
                    timeout=2.0,
                )
        finally:
            queue2 = cast(
                'asyncio.Queue[list[EventDict] | None]', t.bluetooth_queue,
            )
            await queue2.put(None)
            await consumer2

        self.assertIn('01', t.trainings.cases)
        self.assertEqual(len(t.trainings.cases['01'].timings), 1)
        self.assertGreater(t.elapsed_time, 0)
        self.assertTrue(t.bluetooth_scramble_is_completed)

        # When bluetooth_scramble_is_completed was False at cycle-2 start,
        # facelets_scrambled is computed from a solved base (not the BT cube
        # state) - the BT cube state only influences scramble_oriented (the
        # path used to navigate to the target from the messy state)
        expected_from_solved = VCube(size=3)
        expected_from_solved.rotate(t.scramble)
        self.assertEqual(
            t.facelets_scrambled,
            expected_from_solved.state,
        )

        # scramble_oriented differs from scramble because it is the
        # facelets-to-facelets path from state after Cycle 1 to the OLL case
        self.assertNotEqual(
            str(t.scramble_oriented),
            str(t.scramble),
            'scramble_oriented must be the facelets-to-facelets path '
            'through the messy BT cube state, not the raw OLL setup',
        )
