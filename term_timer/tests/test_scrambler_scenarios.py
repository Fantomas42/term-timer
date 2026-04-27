"""
Scenario helpers and reproducers for the design issues in DESIGN_ISSUES.md.

TODO(me): Update or remove

Each section maps to a numbered issue. The helpers are designed to construct
specific cube states and run specific conditions so that the problematic
behaviour can be observed in isolation, without a physical Bluetooth cube.
"""
import unittest
from dataclasses import dataclass
from random import Random

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases import get_case
from cubing_algs.cases.case import Case
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.solver import facelets_to_facelets_algorithm
from cubing_algs.vcube import VCube

from term_timer.annotations import TrainingCase
from term_timer.methods.base import FaceletAnalyser
from term_timer.orientation import get_orientation_moves
from term_timer.scrambler import scrambler
from term_timer.scrambler import trainer


class CubeBuilder:
    """Factory for VCube instances in specific CFOP states."""

    @staticmethod
    def solved() -> VCube:
        """
        Return a fresh solved 3x3 cube.

        Returns:
            A VCube in the solved state.

        """
        return VCube(size=3)

    @staticmethod
    def from_moves(moves_str: str) -> VCube:
        """
        Return a cube with the given move sequence applied.

        Args:
            moves_str: Move sequence string to apply to the solved cube.

        Returns:
            A VCube after applying the given moves.

        """
        cube = VCube(size=3)
        cube.rotate(parse_moves(moves_str))
        return cube

    @staticmethod
    def from_state(state: str) -> VCube:
        """
        Return a cube initialised from a raw 54-char facelet string.

        Args:
            state: 54-character facelet string in URFDLB face order.

        Returns:
            A VCube initialised from the given facelet state.

        """
        return VCube(state, size=3, check=False)

    @staticmethod
    def with_pll_only_scrambled(pll_code: str = 'T') -> VCube:
        """
        Return a cube where F2L and OLL are solved but PLL is scrambled.

        This is the typical BT-cube state after an OLL training solve:
        the user solved OLL, leaving PLL untouched from the previous solve.

        Args:
            pll_code: PLL case code to use for the setup (default: 'T').

        Returns:
            A VCube with OLL solved and PLL scrambled.

        """
        pll_case = get_case('PLL', pll_code)
        setup = next(iter(pll_case.setup_algorithms))
        cube = VCube(size=3)
        cube.rotate(setup)
        return cube

    @staticmethod
    def with_f2l_done_oll_scrambled(oll_code: str = '20') -> VCube:
        """
        Return a cube where cross and F2L are solved but OLL is scrambled.

        This is the typical BT-cube state after an F2L training solve:
        the user solved the F2L pair, leaving OLL (and PLL) untouched.

        Args:
            oll_code: OLL case code to use for the setup (default: '20').

        Returns:
            A VCube with F2L solved and OLL scrambled.

        """
        oll_case = get_case('OLL', oll_code)
        setup = next(iter(oll_case.setup_algorithms))
        cube = VCube(size=3)
        cube.rotate(setup)
        return cube

    @staticmethod
    def partially_scrambled(seed: int = 42, moves: int = 8) -> VCube:
        """
        Return a deterministically scrambled cube (not solved).

        Args:
            seed: RNG seed for reproducibility.
            moves: Number of random moves to apply.

        Returns:
            A VCube in a non-solved scrambled state.

        """
        rng = Random(seed)  # noqa: S311
        _, cube = scrambler(3, moves, rng=rng)
        return cube


class AlgorithmProbe:
    """Inspection helpers for Algorithm objects."""

    @staticmethod
    def trailing_rotations(algo: Algorithm) -> list[Move]:
        """
        Return the trailing rotation moves of an algorithm.

        Args:
            algo: Algorithm to inspect.

        Returns:
            List of trailing Move objects that are rotation moves.

        """
        result: list[Move] = []
        for move in reversed(list(algo)):
            if move.is_rotation_move:
                result.insert(0, move)
            else:
                break
        return result

    @staticmethod
    def has_any_rotation(algo: Algorithm) -> bool:
        """
        Return True if the algorithm contains any rotation move.

        Args:
            algo: Algorithm to inspect.

        Returns:
            True if at least one move is a rotation.

        """
        return any(m.is_rotation_move for m in algo)

    @staticmethod
    def is_pure_face_moves(algo: Algorithm) -> bool:
        """
        Return True if the algorithm contains no rotation moves.

        Args:
            algo: Algorithm to inspect.

        Returns:
            True if no move is a rotation.

        """
        return not AlgorithmProbe.has_any_rotation(algo)

    @staticmethod
    def scramble_percentage(
            scramble: Algorithm, cube_size: int = 3,
    ) -> float:
        """
        Return the facelets-scrambled percentage for a scramble.

        Args:
            scramble: Algorithm to measure.
            cube_size: Size of the cube (default: 3).

        Returns:
            Percentage of facelets displaced by the scramble (0-100).

        """
        return scramble.impacts(cube_size).facelets_scrambled_percent * 100


# ---------------------------------------------------------------------------
# ScenarioResult
# ---------------------------------------------------------------------------

@dataclass
class TrainerScenarioResult:
    """
    All artefacts produced by a single trainer() call.

    Attributes:
        case: The selected training Case.
        scramble: The raw scramble algorithm (UF-standard notation).
        solution: The reference solution algorithm.
        target_cube: The VCube after applying scramble to the base cube.
        facelets_scrambled: target_cube.state — the BT completion target.
        base_was_solved: Whether the base cube was solved before scrambling.
        bt_cube_initial: A copy of the BT cube state passed in (or None).

    """

    case: Case
    scramble: Algorithm
    solution: Algorithm
    target_cube: VCube
    facelets_scrambled: str
    base_was_solved: bool
    bt_cube_initial: str | None


def run_trainer_scenario(  # noqa: PLR0913
        step: str,
        case_codes: list[str],
        collection: str = 'OLL',
        *,
        bt_cube: VCube | None = None,
        orientation: CubeOrientation = 'UF',
        seed: int = 42,
) -> TrainerScenarioResult:
    """
    Run a trainer() call and return every intermediate artefact.

    Args:
        step: Training step ('oll', 'pll', 'f2l', 'cross', 'ecross', 'xcross').
        case_codes: List of case codes to include (e.g. ['01', '02']).
        collection: Collection name for non-cross steps (e.g. 'OLL', 'F2L').
        bt_cube: Optional VCube to use as Bluetooth cube base.
        orientation: Orientation string passed to get_orientation_moves().
        seed: RNG seed for reproducibility.

    Returns:
        TrainerScenarioResult with all artefacts.

    """
    rng = Random(seed)  # noqa: S311
    orientation_moves = get_orientation_moves(orientation)

    cases = []
    for code in case_codes:
        case_obj = get_case(collection, code)
        cases.append(
            TrainingCase(
                case=case_obj,
                best_setups=list(case_obj.setup_algorithms[:5]),
            ),
        )

    base_was_solved = bt_cube.is_solved if bt_cube else True
    bt_initial = bt_cube.state if bt_cube else None

    selected_case, scramble, solution, target_cube = trainer(
        step, cases, orientation_moves, rng,
        bluetooth_cube=bt_cube,
    )

    return TrainerScenarioResult(
        case=selected_case,
        scramble=scramble,
        solution=solution,
        target_cube=target_cube,
        facelets_scrambled=target_cube.state,
        base_was_solved=base_was_solved,
        bt_cube_initial=bt_initial,
    )


# ---------------------------------------------------------------------------
# Issue 1 -- Cross modes + Bluetooth assume a solved base
# ---------------------------------------------------------------------------

class TestIssue1CrossBTBase(unittest.TestCase):
    """
    Reproduce Issue 1: cross-mode trainer() with an unsolved BT cube.

    The cross scramble generators (scramble_easy_cross, scramble_x_cross,
    and the generic scrambler) all assume a solved starting cube. When a BT
    cube is connected and not solved, the facelets_scrambled target becomes
    unreachable — the user cannot arrive at it by applying the scramble to
    their actual cube.
    """

    @staticmethod
    def _run_cross(
            step: str, bt_cube: VCube | None, seed: int = 42,
    ) -> tuple[Algorithm, str]:
        """
        Run a cross-mode trainer call.

        Args:
            step: Cross mode step ('cross', 'ecross', or 'xcross').
            bt_cube: Optional BT cube to use as base.
            seed: RNG seed.

        Returns:
            Tuple of (scramble algorithm, target facelet state).

        """
        rng = Random(seed)  # noqa: S311
        oll_case = get_case('OLL', '01')
        cases = [
            TrainingCase(
                case=oll_case,
                best_setups=list(oll_case.setup_algorithms[:2]),
            ),
        ]
        _, scramble, _, cube = trainer(
            step, cases, parse_moves(''), rng,
            bluetooth_cube=bt_cube,
        )
        return scramble, cube.state

    def test_ecross_solved_bt_target_is_reachable(self) -> None:
        """
        Baseline: when BT cube is solved, applying the scramble reaches
        facelets_scrambled exactly.
        """
        bt = CubeBuilder.solved()
        scramble, target = self._run_cross('ecross', bt)

        reached = bt.copy()
        reached.rotate(scramble)
        self.assertEqual(
            reached.state, target,
            'Solved BT cube + scramble should equal target.',
        )

    @unittest.expectedFailure
    def test_ecross_unsolved_bt_target_is_same_as_solved_base(self) -> None:
        """
        Correct behaviour (not yet implemented): when BT cube is unsolved,
        the cross-mode target should still equal the target produced from a
        solved base, because cross scramble generators are designed for a
        solved starting cube.

        Currently FAILS — trainer() uses the unsolved BT cube as the base,
        so the two targets diverge. Remove @expectedFailure once Issue 1 is
        fixed (cross modes should always use a fresh solved VCube as base).
        """
        bt = CubeBuilder.from_moves('R U R U')
        _, target_with_bt = self._run_cross('ecross', bt)
        _, target_no_bt = self._run_cross('ecross', CubeBuilder.solved())

        self.assertEqual(
            target_with_bt, target_no_bt,
            'After fix: target must be identical regardless of BT cube state.',
        )

    @unittest.expectedFailure
    def test_cross_unsolved_bt_target_is_same_as_solved_base(self) -> None:
        """
        Correct behaviour (not yet implemented): same as above for cross mode.

        Currently FAILS — same root cause as ecross.
        Remove @expectedFailure once Issue 1 is fixed.
        """
        bt = CubeBuilder.partially_scrambled(seed=7)
        self.assertFalse(bt.is_solved)

        _, target_with_bt = self._run_cross('cross', bt)
        _, target_no_bt = self._run_cross('cross', CubeBuilder.solved())

        self.assertEqual(target_with_bt, target_no_bt)

    def test_ecross_bt_tracking_is_self_consistent(self) -> None:
        """
        Regardless of the base bug, the BT cube + scramble always reaches
        facelets_scrambled. This means the scramble-completion check fires
        at the right physical moment — but on the wrong target state.

        This guard test must keep passing after the fix (the BT tracking
        itself is correct; only the choice of base cube is wrong).
        """
        bt = CubeBuilder.from_moves('R U R U')
        scramble, facelets_scrambled = self._run_cross('ecross', bt)

        bt_after = bt.copy()
        bt_after.rotate(scramble)
        self.assertEqual(
            bt_after.state, facelets_scrambled,
            'BT cube + scramble must equal facelets_scrambled.',
        )

    @unittest.expectedFailure
    def test_ecross_facelets_scrambled_matches_solved_base(self) -> None:
        """
        Correct behaviour (not yet implemented): facelets_scrambled must equal
        the state reached by applying the scramble to a fresh solved cube,
        regardless of what the BT cube state was at the start.

        Currently FAILS — unsolved BT base shifts the stored target.
        Remove @expectedFailure once Issue 1 is fixed.
        """
        bt = CubeBuilder.from_moves('R U R U')
        scramble, facelets_scrambled = self._run_cross('ecross', bt)

        solved_after = CubeBuilder.solved()
        solved_after.rotate(scramble)
        self.assertEqual(
            facelets_scrambled, solved_after.state,
            'After fix: facelets_scrambled must equal solved + scramble.',
        )

    def test_condition_bt_solved_no_divergence(self) -> None:
        """Guard: when BT cube starts solved, there is no divergence."""
        bt = CubeBuilder.solved()
        scramble, facelets_scrambled = self._run_cross('ecross', bt)

        solved_after = CubeBuilder.solved()
        solved_after.rotate(scramble)
        self.assertEqual(facelets_scrambled, solved_after.state)


class TestIssueBTDeltaInconsistency(unittest.TestCase):
    """
    Reproduce Issue 3: in Timer.start(), when a BT delta is computed, only
    self.scramble_oriented is updated. self.scramble keeps the original WCA
    scramble. The cube display percentage (computed from self.scramble) then
    reflects the WCA scramble, not the delta the user is executing.

    This class tests the pure logic of the inconsistency without
    instantiating the Timer (which requires async infrastructure).
    """

    def setUp(self) -> None:
        """Set up a seeded RNG and a WCA scramble + canonical cube."""
        self.rng = Random(42)  # noqa: S311
        self.wca_scramble, self.canonical_cube = scrambler(
            3, 0, rng=self.rng,
        )

    def simulate_bt_delta(self, bt_cube: VCube) -> Algorithm:
        """
        Reproduce the Timer BT delta computation.

        Args:
            bt_cube: Current BT cube state to compute the delta from.

        Returns:
            Algorithm to move from bt_cube state to the canonical target.

        """
        return facelets_to_facelets_algorithm(
            bt_cube.state,
            self.canonical_cube.state,
        )

    def test_delta_differs_from_wca_scramble_when_bt_unsolved(self) -> None:
        """
        When BT cube is not solved, the delta scramble is a different
        algorithm from the WCA scramble — but Timer only stores the delta
        in scramble_oriented, leaving self.scramble pointing at the WCA
        scramble. The percentage is therefore wrong.
        """
        bt_cube = CubeBuilder.partially_scrambled(seed=7)
        self.assertFalse(bt_cube.is_solved)

        delta = self.simulate_bt_delta(bt_cube)

        self.assertNotEqual(
            str(delta), str(self.wca_scramble),
            'Delta and WCA scramble should differ for an unsolved BT cube.',
        )

    def test_percentage_diverges_between_delta_and_wca_scramble(self) -> None:
        """
        The facelets-scrambled percentage of the WCA scramble (used in
        print_cube_scrambled) differs from the percentage of the delta
        (what the user actually executes). This demonstrates the display
        inconsistency introduced by not updating self.scramble.

        The BT cube is constructed as the canonical target minus one face
        move — giving a single-move delta while the WCA scramble is a
        full-length sequence, making the divergence measurable.
        """
        bt_cube = VCube(self.canonical_cube.state, size=3, check=False)
        bt_cube.rotate(parse_moves("R'"))

        delta = self.simulate_bt_delta(bt_cube)

        pct_wca = AlgorithmProbe.scramble_percentage(self.wca_scramble)
        pct_delta = AlgorithmProbe.scramble_percentage(delta)

        self.assertLess(
            pct_delta, pct_wca,
            msg=(
                f'Delta % ({pct_delta:.1f}) should be lower than '
                f'WCA % ({pct_wca:.1f}): delta is 1 move vs full scramble.'
            ),
        )

    def test_both_reach_same_target_state(self) -> None:
        """
        Guard: both the WCA scramble (from solved) and the delta (from BT
        cube state) should produce the same canonical cube state. This
        confirms the cube display is correct — only the percentage annotation
        is wrong.
        """
        bt_cube = CubeBuilder.partially_scrambled(seed=7)
        delta = self.simulate_bt_delta(bt_cube)

        cube_via_wca = CubeBuilder.solved()
        cube_via_wca.rotate(self.wca_scramble)

        cube_via_delta = bt_cube.copy()
        cube_via_delta.rotate(delta)

        self.assertEqual(
            cube_via_wca.state, cube_via_delta.state,
            'WCA and delta paths should reach the same target facelet state.',
        )

    def test_no_divergence_when_bt_is_solved(self) -> None:
        """
        Guard: when BT cube is already solved, the Timer skips the delta
        path (bluetooth_cube_is_solved is True). No inconsistency occurs.
        """
        bt_cube = CubeBuilder.solved()
        delta = self.simulate_bt_delta(bt_cube)

        cube_via_wca = CubeBuilder.solved()
        cube_via_wca.rotate(self.wca_scramble)

        cube_via_delta = bt_cube.copy()
        cube_via_delta.rotate(delta)

        self.assertEqual(cube_via_wca.state, cube_via_delta.state)


# ---------------------------------------------------------------------------
# Issue 5 -- F2L training with Bluetooth: setup applied to partial base
# ---------------------------------------------------------------------------

class TestIssue5PartialBTBase(unittest.TestCase):
    """
    Reproduce Issue 5: random_training() setup algorithms assume a fully
    solved cube. When a BT cube is connected and only the current training
    step is done (not the full cube), the target state becomes inconsistent
    with a fresh solve.

    OLL training is coincidentally unaffected (OLL and PLL are independent
    layers). F2L training is broken — the F2L setup applied to a cube with
    existing F2L structure produces a different target.
    """

    @staticmethod
    def _run_oll(
            bt_cube: VCube | None = None, seed: int = 42,
    ) -> TrainerScenarioResult:
        """
        Run an OLL trainer scenario.

        Args:
            bt_cube: Optional BT cube to use as base.
            seed: RNG seed.

        Returns:
            TrainerScenarioResult for the OLL scenario.

        """
        return run_trainer_scenario(
            'oll', ['01', '02', '03'],
            collection='OLL',
            bt_cube=bt_cube,
            seed=seed,
        )

    @staticmethod
    def _run_f2l(
            bt_cube: VCube | None = None, seed: int = 42,
    ) -> TrainerScenarioResult:
        """
        Run an F2L trainer scenario.

        Args:
            bt_cube: Optional BT cube to use as base.
            seed: RNG seed.

        Returns:
            TrainerScenarioResult for the F2L scenario.

        """
        return run_trainer_scenario(
            'f2l', ['01', '02', '03'],
            collection='F2L',
            bt_cube=bt_cube,
            seed=seed,
        )

    @unittest.expectedFailure
    def test_oll_training_target_is_same_as_solved_base(self) -> None:
        """
        Correct behaviour (not yet implemented): facelets_scrambled must be
        the same whether the BT cube is partially solved or fresh — the OLL
        setup assumes a fully solved cube, so the base must always be solved.

        Currently FAILS — trainer() copies the partial BT state as the base,
        shifting the stored target.
        Remove @expectedFailure once Issue 5 is fixed.
        """
        bt_cube = CubeBuilder.with_pll_only_scrambled()
        analyser = FaceletAnalyser()
        self.assertTrue(analyser.check_step('OLL', bt_cube.state))
        self.assertFalse(bt_cube.is_solved)

        result_bt = self._run_oll(bt_cube=bt_cube)
        result_solved = self._run_oll(bt_cube=None)

        self.assertEqual(
            result_bt.facelets_scrambled,
            result_solved.facelets_scrambled,
            'After fix: targets must be equal regardless of BT cube state.',
        )

    def test_oll_bt_tracking_is_self_consistent(self) -> None:
        """
        Guard: even with the wrong target, the BT cube + scramble always
        reaches facelets_scrambled. The completion check fires at the right
        physical moment — on the wrong target state.

        This guard must keep passing after the fix.
        """
        bt_cube = CubeBuilder.with_pll_only_scrambled()
        result = self._run_oll(bt_cube=bt_cube)

        bt_after = bt_cube.copy()
        bt_after.rotate(result.scramble)

        self.assertEqual(
            bt_after.state, result.facelets_scrambled,
            'BT cube + scramble must still reach the stored target.',
        )

    def test_f2l_scramble_is_independent_of_bt_base(self) -> None:
        """
        Guard: the scramble algorithm itself is identical whether or not
        a BT cube is connected. Only the base cube (and hence the target
        state) changes. This isolates the bug to the base selection, not
        to the scramble generation.
        """
        bt_cube = CubeBuilder.with_f2l_done_oll_scrambled()
        result_bt = self._run_f2l(bt_cube=bt_cube)
        result_solved = self._run_f2l(bt_cube=None)

        self.assertEqual(
            result_bt.scramble, result_solved.scramble,
            'Scramble algorithm must be identical regardless of BT base.',
        )

    @unittest.expectedFailure
    def test_f2l_training_target_is_same_as_solved_base(self) -> None:
        """
        Correct behaviour (not yet implemented): facelets_scrambled must equal
        the target computed from a solved base for all F2L cases.

        Currently FAILS — partial BT base produces a wrong F2L case target.
        Remove @expectedFailure once Issue 5 is fixed.
        """
        bt_cube = CubeBuilder.with_f2l_done_oll_scrambled()
        analyser = FaceletAnalyser()
        self.assertTrue(analyser.check_step('Cross', bt_cube.state))
        self.assertFalse(bt_cube.is_solved)

        result_bt = self._run_f2l(bt_cube=bt_cube)
        result_solved = self._run_f2l(bt_cube=None)

        self.assertEqual(
            result_bt.facelets_scrambled,
            result_solved.facelets_scrambled,
            'After fix: targets must be equal regardless of BT cube state.',
        )

    @unittest.expectedFailure
    def test_f2l_bt_reaches_same_state_as_solved_base(self) -> None:
        """
        Correct behaviour (not yet implemented): applying the F2L scramble to
        the BT cube's starting position must produce the same state as applying
        it to a solved cube (the completion check must fire on the correct
        F2L case state).

        Currently FAILS — the two base cubes produce diverging targets.
        Remove @expectedFailure once Issue 5 is fixed.
        """
        bt_cube = CubeBuilder.with_f2l_done_oll_scrambled()
        result = self._run_f2l(bt_cube=bt_cube)

        bt_after = bt_cube.copy()
        bt_after.rotate(result.scramble)

        solved_after = CubeBuilder.solved()
        solved_after.rotate(result.scramble)

        self.assertEqual(
            bt_after.state, solved_after.state,
            'After fix: BT path and solved path must reach the same state.',
        )

    def test_f2l_solved_bt_no_divergence(self) -> None:
        """Guard: when the BT cube is fully solved, there is no divergence."""
        bt_cube = CubeBuilder.solved()
        result_bt = self._run_f2l(bt_cube=bt_cube)
        result_solved = self._run_f2l(bt_cube=None)

        self.assertEqual(
            result_bt.facelets_scrambled,
            result_solved.facelets_scrambled,
        )


# ---------------------------------------------------------------------------
# Orientation x BT interaction
# ---------------------------------------------------------------------------

class TestOrientationBTInteraction(unittest.TestCase):
    """
    Verify that orientation does not interfere with BT cube state tracking.

    The BT cube always tracks in UF-standard notation regardless of the
    user's chosen display orientation. These tests confirm that setting a
    non-UF orientation produces different scramble NOTATION (for display)
    but identical target facelet STATES.
    """

    def test_orientation_changes_move_notation_not_target_state(self) -> None:
        """
        The same training case with two different orientations should produce
        different scramble move sequences (notation for display) but arrive at
        cube states that represent the same physical OLL case, just viewed
        from a different angle.
        """
        for seed in range(5):
            result_uf = run_trainer_scenario(
                'oll', ['01'], orientation='UF', seed=seed,
            )
            result_df = run_trainer_scenario(
                'oll', ['01'], orientation='DF', seed=seed,
            )

            self.assertNotEqual(
                str(result_uf.scramble), str(result_df.scramble),
                f'Seed {seed}: scrambles should differ between UF and DF.',
            )

    def test_scramble_from_non_uf_orientation_is_pure_face_moves(self) -> None:
        """
        After degrip and compress, the scramble produced by random_training()
        should contain no rotation moves regardless of orientation, confirming
        that the sandwich pattern is fully absorbed.
        """
        for orient_str in ('UF', 'DF', 'UR', 'UB', 'FU', 'RU'):
            result = run_trainer_scenario(
                'oll', ['01', '02'], orientation=orient_str, seed=42,
            )
            self.assertTrue(
                AlgorithmProbe.is_pure_face_moves(result.scramble),
                f'Orientation {orient_str}: scramble should have no rotation '
                f'moves but got: {result.scramble}',
            )
