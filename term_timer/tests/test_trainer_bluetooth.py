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
from cubing_algs.transform.translate import translate_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.orientation import get_orientation_moves
from term_timer.trainer import Trainer
from term_timer.training import CaseTraining
from term_timer.training import Trainings


class FakeBluetoothClient:
    """Minimal BLE client stub that satisfies truthy checks and .client.name."""

    name: str = 'FakeCube'
    is_connected: bool = True


class FakeBluetoothInterface:
    """Truthy BT interface stub — no real BLE calls."""

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
    return cast('list[EventDict]', [event])


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
        seed: RNG seed — use a fixed value for reproducible scramble selection.
        free_play: Skip the save-and-confirm phase at the end of each solve.
        orientation: The orientation of the cube.

    Returns:
        Configured Trainer ready for testing.

    """
    cube = (initial_cube or VCube(size=3)).copy()
    empty_trainings = Trainings(method='CFOP', step=step.upper(), cases={})

    with (
        patch(
            'term_timer.trainer.load_trainings',
            return_value=empty_trainings,
        ),
        patch('term_timer.trainer.save_trainings'),
    ):
        instance = Trainer(
            step=step,
            case_codes=case_codes or [],
            oldest=0,
            slowest=0,
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
        clock_step: int = 100_000_000,
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
            await inject_moves(trainer, s_moves, clock_start=0)
            await asyncio.wait_for(
                trainer.scramble_completed_event.wait(), timeout=2.0,
            )
            # wait_control() cancels the getch task asynchronously; wait for
            # scramble_solve() to call set_state('scrambled') before we inject
            # the first solve move (must land in 'scrambled', not
            # 'scrambling')
            await asyncio.sleep(0.05)

            # Phase 2: first solve move (starts the timer)
            solve_clock = len(s_moves) * 100_000_000 + 1_000_000_000
            await inject_moves(
                trainer, [solve_moves[0]], clock_start=solve_clock,
            )
            await asyncio.wait_for(
                trainer.solve_started_event.wait(), timeout=1.0,
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
                    clock_start=solve_clock + 200_000_000,
                )
            await asyncio.wait_for(
                trainer.solve_completed_event.wait(), timeout=2.0,
            )

            # Phase 4: save prompt (handled by getch mock)
            await asyncio.wait_for(run_task, timeout=2.0)
    finally:
        queue = cast(
            'asyncio.Queue[list[EventDict] | None]', trainer.bluetooth_queue,
        )
        await queue.put(None)
        await consumer

    return trainer


class BluetoothTrainerTestCase(unittest.IsolatedAsyncioTestCase):
    """
    Base class for Trainer bluetooth scenario tests.

    Set step / case_codes / seed as class attributes. Each test gets a fresh
    Trainer via make_trainer(). Subclass and override as needed.

    Class attributes:
        step:       Training step for tests in this class.
        case_codes: Cases to include; empty list = all cases.
        seed:       RNG seed for reproducible scramble selection.

    """

    step: str = 'oll'
    case_codes: ClassVar[list[str]] = []
    seed: int = 42

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


class TestTrainerSetup(BluetoothTrainerTestCase):
    """
    Unit-level: inspect Trainer state without running start().

    These tests do not need asyncio because they only check properties set
    during __init__ or set directly by the test.
    """

    step = 'oll'
    case_codes: ClassVar[list[str]] = ['01']

    def test_cases_match_requested_codes(self) -> None:
        """Trainer exposes exactly the requested cases."""
        t = self.make_trainer()

        self.assertEqual(len(t.cases), 1)
        self.assertEqual(t.cases[0].case.code, '01')

    def test_bluetooth_cube_reflects_initial_state(self) -> None:
        """bluetooth_cube_state matches the initial_cube passed in."""
        oll_case = get_case('OLL', '20')
        setup = next(iter(oll_case.setup_algorithms))
        initial = VCube(size=3)
        initial.rotate(setup)

        t = self.make_trainer(initial_cube=initial)

        self.assertFalse(t.bluetooth_cube_is_solved)
        self.assertEqual(t.bluetooth_cube_state, initial.state)

    def test_select_oldest_cases_prioritises_unpractised(self) -> None:
        """Cases with no training data sort before practised ones."""
        t = self.make_trainer(seed=0)

        # Build a two-case dict from the real OLL collection
        collection = get_collection('CFOP/oll').cases
        valid_cases = {
            code: case
            for code, case in collection.items()
            if case.setup_algorithms
        }
        two_cases = dict(list(valid_cases.items())[:2])
        first_code, second_code = list(two_cases.keys())

        # Mark first_code as recently practised; second_code is unseen
        t.trainings.cases[first_code] = CaseTraining(
            code=first_code, last_date=9_999_999_999, timings=[1000],
        )

        selected = t.select_oldest_cases(two_cases, count=1)

        # Unpractised case should be prioritised
        self.assertEqual(selected, [second_code])


class TestFullOLLRun(BluetoothTrainerTestCase):
    """
    Full start() run: inject BT moves to drive all phases.

    Injection timing
    ----------------
    The BT consumer and start() task both run on the same event loop thread.
    We must yield between injection steps so the state machine can advance:

      Phase 1  scramble_completed_event  fires when bluetooth_cube matches
                                         facelets_scrambled (checked by
                                         handle_scrambled)
      Phase 2  solve_started_event       fires on the first move in 'scrambled'
                                         state
      Phase 3  solve_completed_event     fires when
                                         bluetooth_scramble_is_completed
                                         returns True (step check, virtual cube)
      Phase 4  getch('save')             returns save_char immediately via mock

    Scramble vs solve moves
    -----------------------
    Scramble moves must bring bluetooth_cube from initial_cube.state to
    facelets_scrambled. The easiest source is t.scramble (the algorithm that
    start() generated) — read it after the initial sleep(0.05).

    Solve moves must make bluetooth_scramble_is_completed True. That property
    checks: VCube().rotate(scramble_oriented + moves_so_far) has the step
    solved. Inject the case algorithm (i.e. the OLL solution).

    Between phases 2 and 3: wait for solve_started_event, then sleep briefly
    so the state transitions through 'scrambled' → 'solving' before the
    remaining solve moves land. Moves processed in 'solving' state trigger the
    completion check; moves in 'scrambled' state only advance the timer.

    Clock values
    ------------
    Use strictly increasing nanosecond clocks across all injections for
    consistent timing reconstruction. Pass clock_start= to inject_moves().
    """

    step = 'oll'
    case_codes: ClassVar[list[str]] = ['01']
    seed = 42

    async def _full_run(
            self,
            solve_moves: list[str],
            *,
            save_char: str = 'q',
            scramble_moves: list[str] | None = None,
    ) -> Trainer:
        """
        Drive one full OLL training cycle and return the Trainer.

        Returns:
            The Trainer instance after start() has returned.

        """
        t = self.make_trainer()
        return await run_full_cycle(
            t, solve_moves, save_char=save_char, scramble_moves=scramble_moves,
        )

    async def test_elapsed_time_is_recorded(self) -> None:
        """A completed solve records elapsed_time and moves on the Trainer."""
        solution = next(iter(get_case('OLL', '01').algorithms))
        solve_moves = [str(m) for m in solution]

        t = await self._full_run(solve_moves, save_char='q')

        self.assertGreater(t.elapsed_time, 0)
        self.assertGreater(len(t.moves), 0)

    async def test_timing_recorded_in_trainings(self) -> None:
        """
        With save_char='' (save), training data is updated in memory.

        save_trainings is mocked; the in-memory Trainings is still updated.
        """
        solution = next(iter(get_case('OLL', '01').algorithms))
        solve_moves = [str(m) for m in solution]

        t = await self._full_run(solve_moves, save_char='')

        self.assertIn('01', t.trainings.cases)
        self.assertEqual(len(t.trainings.cases['01'].timings), 1)

    async def test_cancel_discards_timing(self) -> None:
        """Pressing 'z' at the save prompt cancels — timing is removed."""
        solution = next(iter(get_case('OLL', '01').algorithms))
        solve_moves = [str(m) for m in solution]

        t = await self._full_run(solve_moves, save_char='z')

        if '01' in t.trainings.cases:
            self.assertEqual(len(t.trainings.cases['01'].timings), 0)


class TestBTCubeInitialState(BluetoothTrainerTestCase):
    """
    Scenarios where the BT cube is not solved at connection time.

    When initial_cube is not solved Trainer.start() still uses the normal
    scramble (bluetooth_scramble_is_completed with empty state returns True
    for OLL, so the delta branch is never taken). However facelets_scrambled
    is computed from BT_cube_state.rotate(scramble) instead of
    solved.rotate(scramble), giving a different completion target for the
    scramble phase. The solve phase is unaffected.
    """

    step = 'oll'
    case_codes: ClassVar[list[str]] = ['01']

    def test_initial_bt_cube_is_not_solved(self) -> None:
        """Unit guard: initial cube passed in is reflected on the trainer."""
        oll_case = get_case('OLL', '01')
        setup = next(iter(oll_case.setup_algorithms))
        initial = VCube(size=3)
        initial.rotate(setup)

        t = self.make_trainer(initial_cube=initial)

        self.assertFalse(t.bluetooth_cube_is_solved)
        self.assertEqual(t.bluetooth_cube_state, initial.state)

    async def test_full_run_with_unsolved_initial_bt_cube(self) -> None:
        """
        A full start() cycle completes correctly when the BT cube starts in
        an unsolved state (OLL case already applied before training begins).

        What differs from the solved-cube case
        --------------------------------------
        start() computes facelets_scrambled as VCube(bt_state).rotate(scramble)
        instead of VCube().rotate(scramble), giving a different completion
        target for the scramble phase. handle_scrambled() waits for
        bluetooth_cube to reach that state. Injecting t.scramble still works:
          VCube(bt_state).rotate(scramble) == facelets_scrambled by definition.

        The solve phase is unaffected: bluetooth_scramble_is_completed uses
        VCube().rotate(scramble_oriented + moves), not the physical cube.

        Assertions
        ----------
        1. elapsed_time > 0
           - timing loop ran from start_time to end_time

        2. case '01' has one timing entry
           - solve_line() called add_timing() on the in-memory Trainings

        3. facelets_scrambled == VCube(initial_state).rotate(t.scramble).state
           - start() used the actual BT cube state as the scramble origin,
             not an assumed solved baseline; both t.scramble and
             t.facelets_scrambled come from the run, nothing is set manually

        4. facelets_scrambled != VCube().rotate(t.scramble).state
           - confirms the unsolved origin produces a different target than
             the solved-cube path would
        """
        oll_case = get_case('OLL', '01')
        setup = next(iter(oll_case.setup_algorithms))
        solution = next(iter(oll_case.algorithms))

        initial = VCube(size=3)
        initial.rotate(setup)

        t = self.make_trainer(initial_cube=initial)
        solve_moves = [str(m) for m in solution]
        await run_full_cycle(t, solve_moves, save_char='')

        # 1. Timer ran
        self.assertGreater(t.elapsed_time, 0)

        # 2. Timing saved
        self.assertIn('01', t.trainings.cases)
        self.assertEqual(len(t.trainings.cases['01'].timings), 1)

        # 3. facelets_scrambled formula holds for unsolved initial cube
        expected = VCube(initial.state, size=3, check=False)
        expected.rotate(t.scramble)
        self.assertEqual(t.facelets_scrambled, expected.state)

        # 4. that target differs from the solved-initial path
        solved_target = VCube(size=3)
        solved_target.rotate(t.scramble)
        self.assertNotEqual(t.facelets_scrambled, solved_target.state)


class TestScrambleOrientedProperties(BluetoothTrainerTestCase):
    """
    Verify t.scramble, t.scramble_oriented, and t.facelets_scrambled as set
    by start() for UF and DF orientations.

    UF orientation (standard hold, U on top F facing front)
    -------------------------------------------------------
    reorient is the identity transform, so:
      scramble_oriented == scramble  (same algorithm, same notation)
      scramble is one of the case's raw setup algorithms

    DF orientation (cube held with D on top, F facing front → z2 rotation)
    ----------------------------------------------------------------------
    trainer() adapts the setup for the DF frame (U→D, R→L, etc.), so:
      scramble uses D-face moves — NOT in the case's raw UF setup list
      scramble_oriented == reorient(scramble) translates BACK to UF notation
        and equals the UF scramble (canonical form regardless of orientation)

    Solve moves for DF
    ------------------
    bluetooth_scramble_is_completed checks the virtual UF-frame cube:
      VCube().rotate(scramble_oriented + reorient(injected_moves))
    scramble_oriented is already in UF, so injected_moves must also result
    in UF notation after reorient. Injecting reorient_DF(solution_UF) means
    reorient(reorient_DF(solution_UF)) = solution_UF → check passes correctly.
    """

    step = 'oll'
    case_codes: ClassVar[list[str]] = ['01']
    seed = 42

    async def test_scramble_properties_uf_orientation(self) -> None:
        """
        With UF orientation (no reorientation).

        Verifies:
        - scramble is one of the case's raw setup algorithms
        - scramble_oriented == scramble
        - facelets_scrambled == VCube().rotate(scramble).state
        """
        oll_case = get_case('OLL', '01')
        solution = next(iter(oll_case.algorithms))
        valid_setups = {str(s) for s in oll_case.setup_algorithms}

        t = self.make_trainer(orientation='UF')
        await run_full_cycle(t, [str(m) for m in solution], save_char='q')

        self.assertIn(str(t.scramble), valid_setups)
        self.assertEqual(str(t.scramble_oriented), str(t.scramble))

        expected = VCube(size=3)
        expected.rotate(t.scramble)
        self.assertEqual(t.facelets_scrambled, expected.state)

    async def test_scramble_properties_df_orientation(self) -> None:
        """
        With DF orientation (z2 reorientation).

        Verifies:
        - scramble uses D-face moves — not in the case's raw UF setup list
        - scramble_oriented translates back to UF and equals the UF scramble
        - facelets_scrambled == VCube().rotate(scramble).state (DF moves)
        - solve moves must be reoriented so the virtual UF-frame check passes
        """
        oll_case = get_case('OLL', '01')
        solution = next(iter(oll_case.algorithms))
        valid_setups = {str(s) for s in oll_case.setup_algorithms}

        # Reorient the solution from UF notation into DF notation so that
        # bluetooth_scramble_is_completed can translate it back to UF for
        # the check
        reorient_df = translate_moves(get_orientation_moves('DF'))
        solve_moves_df = [str(m) for m in reorient_df(solution)]

        t = self.make_trainer(orientation='DF')
        await run_full_cycle(t, solve_moves_df, save_char='q')

        # scramble is orientation-adapted — uses D, not U
        self.assertNotIn(str(t.scramble), valid_setups)

        # scramble_oriented is the canonical UF form of the scramble
        self.assertNotEqual(str(t.scramble_oriented), str(t.scramble))
        self.assertIn(str(t.scramble_oriented), valid_setups)

        expected = VCube(size=3)
        expected.rotate(t.scramble)
        self.assertEqual(t.facelets_scrambled, expected.state)
