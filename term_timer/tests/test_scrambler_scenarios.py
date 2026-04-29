"""
Scenario helpers and reproducers for scrambler interactions.

The helpers are designed to construct specific cube states
and run specific conditions so that the problematic behaviour
can be observed in isolation, without a physical Bluetooth cube.
"""
import unittest
from dataclasses import dataclass
from random import Random

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_case
from cubing_algs.cases.case import Case
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.solver import facelets_to_facelets_algorithm
from cubing_algs.vcube import VCube

from term_timer.annotations import TrainingCase
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
        orientation_moves: Algorithm | None = None,
        seed: int = 42,
) -> TrainerScenarioResult:
    """
    Run a trainer() call and return every intermediate artefact.

    Args:
        step: Training step ('oll', 'pll', 'f2l', 'cross', 'ecross', 'xcross').
        case_codes: List of case codes to include (e.g. ['01', '02']).
        collection: Collection name for non-cross steps (e.g. 'OLL', 'F2L').
        bt_cube: Optional VCube to use as Bluetooth cube base.
        orientation_moves: Orientation moves.
        seed: RNG seed for reproducibility.

    Returns:
        TrainerScenarioResult with all artefacts.

    """
    rng = Random(seed)  # noqa: S311

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
        step, cases, rng, orientation_moves,
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


class TestOrientationBTInteraction(unittest.TestCase):
    """
    Verify that orientation does not interfere with BT cube state tracking.

    The BT cube always tracks in UF-standard notation regardless of the
    user's chosen display orientation. These tests confirm that setting a
    non-UF orientation produces different scramble NOTATION (for display)
    but identical target facelet STATES.
    """

    def test_orientation_changes_move_notation(self) -> None:
        """
        The same training case with two different orientations should produce
        different scramble move sequences (notation for display) but arrive at
        cube states that represent the same physical OLL case, just viewed
        from a different angle.
        """
        for seed in range(5):
            result_uf = run_trainer_scenario(
                'oll', ['01'], seed=seed,
            )
            result_df = run_trainer_scenario(
                'oll', ['01'], seed=seed,
                orientation_moves=parse_moves('z2'),
            )

            self.assertNotEqual(
                str(result_uf.scramble), str(result_df.scramble),
                f'Seed {seed}: scrambles must differs between UF and DF.',
            )
            self.assertEqual(
                str(result_uf.solution), str(result_df.solution),
                f'Seed {seed}: solutions must be equals between UF and DF.',
            )

    def test_scramble_from_non_uf_orientation_is_pure_face_moves(self) -> None:
        """
        After degrip and compress, the scramble produced by random_training()
        should contain no rotation moves regardless of orientation, confirming
        that the sandwich pattern is fully absorbed.
        """
        for moves in ('', 'z2', 'x y', 'z', 'y'):
            result = run_trainer_scenario(
                'oll', ['01', '02'],
                orientation_moves=parse_moves(moves),
                seed=42,
            )
            self.assertTrue(
                AlgorithmProbe.is_pure_face_moves(result.scramble),
                f'Orientation {moves}: scramble should have no rotation '
                f'moves but got: {result.scramble}',
            )
