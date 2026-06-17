"""Tests for scrambler module."""
import unittest
from random import Random
from unittest.mock import patch

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_case
from cubing_algs.cases.case import Case
from cubing_algs.parsing import parse_moves
from cubing_algs.solved_state import SOLVED_FACELETS_3x3x3
from cubing_algs.vcube import VCube

from term_timer.annotations import TrainingCase
from term_timer.scrambler import random_training
from term_timer.scrambler import scrambler
from term_timer.scrambler import trainer


def make_training_case(
        case_code: str = '01',
        step: str = 'OLL',
) -> TrainingCase:
    """
    Create a TrainingCase for testing.

    Returns:
        A TrainingCase wrapping the given case with its first two setups.

    """
    case = get_case(step, case_code)
    return TrainingCase(
        case=case,
        best_setups=list(case.setup_algorithms[:2]),
        solution=case.main_algorithm,
    )


class TestScramblerRawScramble(unittest.TestCase):
    """Tests for scrambler function with raw_scramble argument."""

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_returns_tuple_of_algorithm_and_vcube(self) -> None:
        """Test that scrambler returns (Algorithm, VCube)."""
        algo, cube = scrambler(
            3, 0,
            rng=self.rng,
            raw_scramble='R U',
        )
        self.assertIsInstance(algo, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_raw_scramble_applies_moves(self) -> None:
        """Test that raw_scramble is applied to the cube."""
        raw = "R U R' U'"
        _, cube = scrambler(
            3, 0,
            rng=self.rng,
            raw_scramble=raw,
        )

        expected_cube = VCube(size=3)
        expected_cube.rotate(parse_moves(raw))
        self.assertEqual(cube.state, expected_cube.state)

    def test_raw_scramble_returned_as_algorithm(self) -> None:
        """Test that the scramble algorithm matches the raw input moves."""
        raw = 'R U F'
        result, _ = scrambler(
            3, 0,
            rng=self.rng,
            raw_scramble=raw,
        )
        expected = parse_moves(raw)
        self.assertEqual(str(result), str(expected))

    def test_raw_scramble_skips_kociemba(self) -> None:
        """Test that raw_scramble bypasses the kociemba solver."""
        with patch(
                'term_timer.scrambler.facelets_to_facelets_algorithm',
        ) as mock_f2f:
            scrambler(
                3, 0,
                rng=self.rng,
                raw_scramble='R U',
            )
            mock_f2f.assert_not_called()


class TestScramblerEasyCross(unittest.TestCase):
    """Tests for scrambler function with easy_cross=True."""

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_returns_algorithm_and_vcube(self) -> None:
        """Test that scrambler with easy_cross=True returns correct types."""
        algo, cube = scrambler(3, 0, easy_cross=True, rng=self.rng)
        self.assertIsInstance(algo, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_cube_is_scrambled(self) -> None:
        """Test that the returned cube is not in the solved state."""
        _, cube = scrambler(3, 0, easy_cross=True, rng=self.rng)
        self.assertNotEqual(cube.state, SOLVED_FACELETS_3x3x3)

    def test_skips_kociemba(self) -> None:
        """Test that easy_cross mode does not call the kociemba solver."""
        with patch(
                'term_timer.scrambler.facelets_to_facelets_algorithm',
        ) as mock_f2f:
            scrambler(3, 0, easy_cross=True, rng=self.rng)
            mock_f2f.assert_not_called()

    def test_uses_scramble_easy_cross(self) -> None:
        """Test that the scramble_easy_cross function is used."""
        with patch('term_timer.scrambler.scramble_easy_cross') as mock_ec:
            mock_algo = parse_moves('R U')
            mock_ec.return_value = (mock_algo, Algorithm())
            scrambler(3, 0, easy_cross=True, rng=self.rng)
            mock_ec.assert_called_once()


class TestScramblerXCross(unittest.TestCase):
    """Tests for scrambler function with x_cross=True."""

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_returns_algorithm_and_vcube(self) -> None:
        """Test that scrambler with x_cross=True returns correct types."""
        algo, cube = scrambler(3, 0, x_cross=True, rng=self.rng)
        self.assertIsInstance(algo, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_cube_is_scrambled(self) -> None:
        """Test that the returned cube is not in the solved state."""
        _, cube = scrambler(3, 0, x_cross=True, rng=self.rng)
        self.assertNotEqual(cube.state, SOLVED_FACELETS_3x3x3)

    def test_skips_kociemba(self) -> None:
        """Test that x_cross mode does not call the kociemba solver."""
        with patch(
                'term_timer.scrambler.facelets_to_facelets_algorithm',
        ) as mock_f2f:
            scrambler(3, 0, x_cross=True, rng=self.rng)
            mock_f2f.assert_not_called()

    def test_uses_scramble_x_cross(self) -> None:
        """Test that the scramble_x_cross function is used."""
        with patch('term_timer.scrambler.scramble_x_cross') as mock_xc:
            mock_algo = parse_moves('R U')
            mock_xc.return_value = (mock_algo, Algorithm())
            scrambler(3, 0, x_cross=True, rng=self.rng)
            mock_xc.assert_called_once()


class TestScramblerEdgesOriented(unittest.TestCase):
    """Tests for scrambler function with edges_oriented=True."""

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_returns_algorithm_and_vcube(self) -> None:
        """
        Test that scrambler with edges_oriented=True
        returns correct types.
        """
        algo, cube = scrambler(3, 0, edges_oriented=True, rng=self.rng)
        self.assertIsInstance(algo, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_cube_is_scrambled(self) -> None:
        """Test that the returned cube is not in the solved state."""
        _, cube = scrambler(3, 0, edges_oriented=True, rng=self.rng)
        self.assertNotEqual(cube.state, SOLVED_FACELETS_3x3x3)

    def test_uses_scramble_edges_oriented(self) -> None:
        """Test that the scramble_edges_oriented function is used."""
        with patch(
                'term_timer.scrambler.scramble_edges_oriented',
        ) as mock_eo:
            mock_eo.return_value = parse_moves('R U')
            with patch(
                    'term_timer.scrambler.facelets_to_facelets_algorithm',
            ) as mock_f2f:
                mock_f2f.return_value = parse_moves('R U')
                scrambler(3, 0, edges_oriented=True, rng=self.rng)
            mock_eo.assert_called_once()

    def test_3x3_no_iterations_uses_kociemba(self) -> None:
        """Test that 3x3 edges_oriented without iterations calls kociemba."""
        with patch(
                'term_timer.scrambler.facelets_to_facelets_algorithm',
        ) as mock_f2f:
            mock_f2f.return_value = parse_moves('R U')
            scrambler(3, 0, edges_oriented=True, rng=self.rng)
            mock_f2f.assert_called_once()

    def test_with_iterations_skips_kociemba(self) -> None:
        """Test that edges_oriented with iterations skips kociemba."""
        with patch(
                'term_timer.scrambler.facelets_to_facelets_algorithm',
        ) as mock_f2f:
            scrambler(3, 10, edges_oriented=True, rng=self.rng)
            mock_f2f.assert_not_called()

    def test_passes_iterations_to_scramble_edges_oriented(self) -> None:
        """Test that iterations is passed through to scramble_edges_oriented."""
        with patch(
                'term_timer.scrambler.scramble_edges_oriented',
        ) as mock_eo:
            mock_eo.return_value = parse_moves('R U')
            scrambler(3, 10, edges_oriented=True, rng=self.rng)
            mock_eo.assert_called_once_with(10, rng=self.rng)

    def test_zero_iterations_passes_none_to_scramble_edges_oriented(
            self,
    ) -> None:
        """
        Test that iterations=0 is converted to None
        for scramble_edges_oriented.
        """
        with patch(
                'term_timer.scrambler.scramble_edges_oriented',
        ) as mock_eo:
            mock_eo.return_value = parse_moves('R U')
            with patch(
                    'term_timer.scrambler.facelets_to_facelets_algorithm',
            ) as mock_f2f:
                mock_f2f.return_value = parse_moves('R U')
                scrambler(3, 0, edges_oriented=True, rng=self.rng)
            mock_eo.assert_called_once_with(None, rng=self.rng)


class TestScramblerNxN(unittest.TestCase):
    """Tests for scrambler function for NxN cubes."""

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_4x4_scramble_returns_correct_types(self) -> None:
        """Test that a 4x4 scramble returns Algorithm and VCube."""
        algo, cube = scrambler(4, 40, rng=self.rng)
        self.assertIsInstance(algo, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_4x4_cube_is_scrambled(self) -> None:
        """Test that a 4x4 cube is not in the solved state after scrambling."""
        _, cube = scrambler(4, 40, rng=self.rng)
        solved_4x4 = VCube(size=4).state
        self.assertNotEqual(cube.state, solved_4x4)

    def test_3x3_with_iterations_skips_kociemba(self) -> None:
        """Test that 3x3 with explicit iterations skips kociemba."""
        with patch(
                'term_timer.scrambler.facelets_to_facelets_algorithm',
        ) as mock_f2f:
            scrambler(3, 20, rng=self.rng)
            mock_f2f.assert_not_called()

    def test_3x3_no_options_uses_kociemba(self) -> None:
        """Test that plain 3x3 scramble calls the kociemba solver."""
        with patch(
                'term_timer.scrambler.facelets_to_facelets_algorithm',
        ) as mock_f2f:
            mock_f2f.return_value = parse_moves('R U')
            scrambler(3, 0, rng=self.rng)
            mock_f2f.assert_called_once()

    def test_3x3_no_options_returns_correct_types(self) -> None:
        """Test that 3x3 plain scramble returns correct types."""
        algo, cube = scrambler(3, 0, rng=self.rng)
        self.assertIsInstance(algo, Algorithm)
        self.assertIsInstance(cube, VCube)
        self.assertNotEqual(cube.state, SOLVED_FACELETS_3x3x3)


class TestScramblerCubeStateConsistency(unittest.TestCase):
    """Tests ensuring scrambler returns consistent cube states."""

    def setUp(self) -> None:
        """Set up a seeded RNG."""
        self.rng = Random(7)  # noqa: S311

    def test_raw_scramble_cube_state_matches_manual_application(self) -> None:
        """Test cube state from raw_scramble matches manually applied moves."""
        raw = "L' R U2 F D'"
        _, cube = scrambler(3, 0, rng=self.rng,
                            raw_scramble=raw)
        expected = VCube(size=3)
        expected.rotate(parse_moves(raw, trust_input=False))
        self.assertEqual(cube.state, expected.state)

    def test_different_seeds_give_different_scrambles(self) -> None:
        """Test that different RNG seeds produce different scrambles."""
        _, cube1 = scrambler(3, 20, rng=Random(1))  # noqa: S311
        _, cube2 = scrambler(3, 20, rng=Random(99))  # noqa: S311
        self.assertNotEqual(cube1.state, cube2.state)

    def test_same_seed_gives_same_scramble(self) -> None:
        """Test that the same RNG seed produces the same scramble."""
        _, cube1 = scrambler(3, 20, rng=Random(42))  # noqa: S311
        _, cube2 = scrambler(3, 20, rng=Random(42))  # noqa: S311
        self.assertEqual(cube1.state, cube2.state)


class TestTrainerEcross(unittest.TestCase):
    """Tests for trainer function with ecross step."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [make_training_case()]
        self.orientation = parse_moves('')

    def test_returns_four_tuple(self) -> None:
        """Test that trainer returns a four-element tuple."""
        result = trainer('ecross', self.cases, self.rng, self.orientation)
        self.assertEqual(len(result), 3)

    def test_ecross_returns_correct_types(self) -> None:
        """Test that ecross trainer returns correct types for each element."""
        case, scramble, solution = trainer(
            'ecross', self.cases, self.rng, self.orientation,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)

    def test_ecross_uses_scramble_easy_cross(self) -> None:
        """Test that ecross step calls scramble_easy_cross."""
        with patch('term_timer.scrambler.scramble_easy_cross') as mock_ec:
            mock_ec.return_value = (parse_moves('R U'), parse_moves('U R'))
            trainer('ecross', self.cases, self.rng, self.orientation)
            mock_ec.assert_called_once()


class TestTrainerXcross(unittest.TestCase):
    """Tests for trainer function with xcross step."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [make_training_case()]
        self.orientation = parse_moves('')

    def test_xcross_returns_correct_types(self) -> None:
        """Test that xcross trainer returns correct types."""
        case, scramble, solution = trainer(
            'xcross', self.cases, self.rng, self.orientation,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)

    def test_xcross_uses_scramble_x_cross(self) -> None:
        """Test that xcross step calls scramble_x_cross."""
        with patch('term_timer.scrambler.scramble_x_cross') as mock_xc:
            mock_xc.return_value = (parse_moves('R U'), parse_moves('U R'))
            trainer('xcross', self.cases, self.rng, self.orientation)
            mock_xc.assert_called_once()


class TestTrainerCross(unittest.TestCase):
    """Tests for trainer function with cross step."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [make_training_case()]
        self.orientation = parse_moves('')

    def test_cross_returns_correct_types(self) -> None:
        """Test that cross trainer returns correct types."""
        case, scramble, solution = trainer(
            'cross', self.cases, self.rng, self.orientation,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)

    def test_cross_uses_scrambler(self) -> None:
        """Test that cross step uses the scrambler function."""
        with patch('term_timer.scrambler.scrambler') as mock_sc:
            mock_sc.return_value = (parse_moves('R U'), VCube(size=3))
            trainer('cross', self.cases, self.rng, self.orientation)
            mock_sc.assert_called_once()

    def test_cross_solution_is_empty(self) -> None:
        """Test that cross step returns an empty solution algorithm."""
        _, _, solution = trainer(
            'cross', self.cases, self.rng, self.orientation,
        )
        self.assertEqual(len(solution), 0)


class TestTrainerOll(unittest.TestCase):
    """Tests for trainer function with OLL step (calls random_training)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [
            make_training_case('01', 'OLL'),
            make_training_case('02', 'OLL'),
        ]
        self.orientation = parse_moves('')

    def test_oll_returns_correct_types(self) -> None:
        """Test that OLL trainer returns correct types."""
        case, scramble, solution = trainer(
            'oll', self.cases, self.rng, self.orientation,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)

    def test_oll_uses_random_training(self) -> None:
        """Test that non-special steps fall through to random_training."""
        with patch('term_timer.scrambler.random_training') as mock_rt:
            oll_case = get_case('OLL', '01')
            mock_rt.return_value = (
                oll_case,
                parse_moves('R U'),
                parse_moves('U R'),
            )
            trainer('oll', self.cases, self.rng, self.orientation)
            mock_rt.assert_called_once()

    def test_oll_case_matches_selected(self) -> None:
        """Test that the returned case is a valid case from the input list."""
        case, _, _ = trainer(
            'oll', self.cases, self.rng, self.orientation,
        )
        valid_case_codes = {tc.case.code for tc in self.cases}
        self.assertIn(case.code, valid_case_codes)


class TestRandomTraining(unittest.TestCase):
    """Tests for random_training function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [
            make_training_case('01', 'OLL'),
            make_training_case('02', 'OLL'),
            make_training_case('03', 'OLL'),
        ]

    def test_returns_three_tuple(self) -> None:
        """Test that random_training returns a three-element tuple."""
        result = random_training(self.cases, self.rng)
        self.assertEqual(len(result), 3)

    def test_returns_correct_types(self) -> None:
        """Test that random_training returns correct types."""
        case, scramble, solution = random_training(
            self.cases, self.rng,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)

    def test_returned_case_is_from_input(self) -> None:
        """Test that the returned case is one of the input cases."""
        valid_codes = {tc.case.code for tc in self.cases}
        for _ in range(10):
            case, _, _ = random_training(
                self.cases, self.rng,
            )
            self.assertIn(case.code, valid_codes)

    def test_solution_matches_case_main_algorithm(self) -> None:
        """Test that the returned solution is the case's main algorithm."""
        case, _, solution = random_training(
            self.cases, self.rng,
        )
        self.assertEqual(str(solution), str(case.main_algorithm))

    def test_single_case_always_selected(self) -> None:
        """Test that with a single case it is always selected."""
        single_cases = [make_training_case('01', 'OLL')]
        expected_code = single_cases[0].case.code
        for _ in range(5):
            case, _, _ = random_training(
                single_cases, self.rng,
            )
            self.assertEqual(case.code, expected_code)

    def test_scramble_transforms_applied(self) -> None:
        """Test that scramble has degrip and rotation compression applied."""
        cases = [make_training_case('01', 'OLL')]
        _, scramble, _ = random_training(cases, self.rng)
        algo_str = str(scramble)
        self.assertNotIn('@', algo_str)

    def test_rng_determines_selection(self) -> None:
        """Test that the same RNG seed produces the same case selection."""
        case1, _, _ = random_training(
            self.cases, Random(99),  # noqa: S311
        )
        case2, _, _ = random_training(
            self.cases, Random(99),  # noqa: S311
        )
        self.assertEqual(case1.code, case2.code)


class TestScramblerEasyCrossOrientation(unittest.TestCase):
    """
    Tests for orientation-aware easy_cross scramble generation.

    scramble_easy_cross() produces a scramble designed for use as
    ``z2 + scramble``: after applying z2 (DF orientation) then the scramble,
    the cross is easy on U (user's bottom). When the user's orientation is DF
    the scrambler must pre-translate the scramble so that Timer's reorient()
    restores the original, and must set cube.state to the physical state the
    user ends up with (z2 applied before the scramble).

    Expected values are pre-computed with seed 42 for deterministic checks.
    UF orientation leaves the canonical output unchanged; DF orientation must
    produce the adjusted scramble and cube state shown below.
    """

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_uf_orientation_scramble(self) -> None:
        """UF orientation returns the unmodified easy_cross scramble."""
        scramble, _ = scrambler(3, 0, easy_cross=True, rng=self.rng)
        self.assertEqual(
            str(scramble),
            "R L' U' B R F2 R' D R2 U' L' B2 U R2 U' F2 U' F2 D' R2 D",
        )

    def test_uf_orientation_cube_state(self) -> None:
        """UF orientation returns the unmodified easy_cross cube state."""
        _, cube = scrambler(3, 0, easy_cross=True, rng=self.rng)
        self.assertEqual(cube.orientation, 'UF')
        self.assertEqual(
            cube.state,
            'FDBUUFFUDBLRDRUBLFUBLLFBLRUFBRRDDUBURFRRLUBFDDFDRBDLLL',
        )

    def test_df_orientation_scramble(self) -> None:
        """
        DF orientation returns a pre-translated scramble.

        When Timer calls reorient() on this scramble the original canonical
        scramble is recovered, so the display becomes ``z2 original_scramble``
        which leaves U cross easy after the solution is applied.
        """
        scramble, _ = scrambler(
            3, 0, easy_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('z2'),
        )
        self.assertEqual(
            str(scramble),
            "L R' D' B L F2 L' U L2 D' R' B2 D L2 D' F2 D' F2 U' L2 U",
        )

    def test_df_orientation_cube_state(self) -> None:
        """
        DF orientation returns the cube state produced by z2
        then the original scramble.

        This is the physical cube state the user ends up with after applying
        the displayed ``z2 scramble`` sequence to a solved cube.
        """
        _, cube = scrambler(
            3, 0, easy_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('z2'),
        )
        self.assertEqual(cube.orientation, 'UF')
        self.assertEqual(
            cube.state,
            'DBDUULLBFUFBDRLLFLDLRBFRRBDUDFFDDBUFFRBDLULRBRRRUBLUFU',
        )
        solution = "z2 F U2 L' D2 F2"
        cube.rotate(solution)
        self.assertEqual(
            cube.state,
            'UDULDDDBDFFFFLDLLBLRRBFLUFBFUDUUUBURLBFRRDURLRRBLBFDBR',
        )

    def test_fr_orientation_scramble(self) -> None:
        """
        FR orientation returns a pre-translated scramble.

        When Timer calls reorient() on this scramble the original canonical
        scramble is recovered, so the display becomes ``x y original_scramble``
        which leaves U cross easy after the solution is applied.
        """
        scramble, _ = scrambler(
            3, 0, easy_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('x y'),
        )
        self.assertEqual(
            str(scramble),
            "U D' F' L U R2 U' B U2 F' D' L2 F U2 F' R2 F' R2 B' U2 B",
        )

    def test_fr_orientation_cube_state(self) -> None:
        """
        FR orientation returns the cube state produced by x y
        then the original scramble.

        This is the physical cube state the user ends up with after applying
        the displayed ``x y scramble`` sequence to a solved cube.
        """
        _, cube = scrambler(
            3, 0, easy_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('x y'),
        )
        self.assertEqual(cube.orientation, 'UF')
        self.assertEqual(
            cube.state,
            'RDLFUBUDLDLFLRUFDDLRBBFFRFRURUUDFLRBDUBDLRDBBUBFLBLRUF',
        )
        solution = "x y F U2 L' D2 F2"
        cube.rotate(solution)
        self.assertEqual(
            cube.state,
            'BFBUFFFLFRRRRUFUULUDDLRUBRLRBFBBBLBDULRDDFBDUDDLULRFLD',
        )


class TestScramblerXCrossOrientation(unittest.TestCase):
    """
    Tests for orientation-aware x_cross scramble generation.

    x_cross has the same orientation requirement as easy_cross: the canonical
    scramble from scramble_x_cross() is designed for ``z2 + scramble`` usage.
    The scrambler must apply the same pre-translation when orientation != 'UF'.

    Expected values are pre-computed with seed 42.
    """

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_uf_orientation_scramble(self) -> None:
        """UF orientation returns the unmodified x_cross scramble."""
        scramble, _ = scrambler(3, 0, x_cross=True, rng=self.rng)
        self.assertEqual(
            str(scramble),
            "U' B' D' L2 B' R L2 U' D' F' D B2 U2 B2 U' L2 F2 U R2 L2",
        )

    def test_uf_orientation_cube_state(self) -> None:
        """UF orientation returns the unmodified x_cross cube state."""
        _, cube = scrambler(3, 0, x_cross=True, rng=self.rng)
        self.assertEqual(cube.orientation, 'UF')
        self.assertEqual(
            cube.state,
            'DDDFUDLUFRLBFRDLFBURDBFUDLUBUBDDLUBULRFBLUFRLRFFBBLRRR',
        )

    def test_df_orientation_scramble(self) -> None:
        """DF orientation returns the pre-translated x_cross scramble."""
        scramble, _ = scrambler(
            3, 0, x_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('z2'),
        )
        self.assertEqual(
            str(scramble),
            "D' B' U' R2 B' L R2 D' U' F' U B2 D2 B2 D' R2 F2 D L2 R2",
        )

    def test_df_orientation_cube_state(self) -> None:
        """
        DF orientation returns the cube state produced by z2
        then the original x_cross scramble.
        """
        _, cube = scrambler(
            3, 0, x_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('z2'),
        )
        self.assertEqual(cube.orientation, 'UF')
        self.assertEqual(
            cube.state,
            'DBDRUUBDBRLFDRBFLRDRUDFBULDFDRUDFUUUBFRULFBRLLLLRBBFFL',
        )
        solution = "z2 R2 F U2 L' D2 F2 R'"
        cube.rotate(solution)
        self.assertEqual(
            cube.state,
            'DDDRDDDBUBFFLLBLLUFLRLFFFFFUUUUUUBUBRDRFRDDRRLBBRBRLBL',
        )

    def test_fr_orientation_scramble(self) -> None:
        """FR orientation returns the pre-translated x_cross scramble."""
        scramble, _ = scrambler(
            3, 0, x_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('x y'),
        )
        self.assertEqual(
            str(scramble),
            "F' L' B' D2 L' U D2 F' B' R' B L2 F2 L2 F' D2 R2 F U2 D2",
        )

    def test_fr_orientation_cube_state(self) -> None:
        """
        FR orientation returns the cube state produced by "x y"
        then the original x_cross scramble.
        """
        _, cube = scrambler(
            3, 0, x_cross=True, rng=self.rng,
            orientation_moves=Algorithm.parse_moves('x y'),
        )
        self.assertEqual(cube.orientation, 'UF')
        self.assertEqual(
            cube.state,
            'LRDBURLDUBFFURDFLBBBRBFFBRDDURLDFRUDULUULRUDRLDFFBLLBF',
        )
        solution = "x y R2 F U2 L' D2 F2 R'"
        cube.rotate(solution)
        self.assertEqual(
            cube.state,
            'FFFDFFFLBLRRUULUUBRUDURRRRRBBBBBBLBLDFDRDFFDDULLDLDULU',
        )


class TestScramblerEasyCrossDifficulty(unittest.TestCase):
    """Tests for scrambler reading ecross difficulty from config."""

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_passes_config_difficulty_to_easy_cross(self) -> None:
        """Test that the config difficulty is passed to scramble_easy_cross."""
        with patch('term_timer.scrambler.scramble_easy_cross') as mock_ec:
            mock_ec.return_value = (parse_moves('R U'), Algorithm())
            with patch(
                    'term_timer.scrambler.TRAINER_ECROSS_DIFFICULTY', 'easy',
            ):
                scrambler(3, 0, easy_cross=True, rng=self.rng)
            args, kwargs = mock_ec.call_args
            difficulty = args[0] if args else kwargs.get('difficulty')
            self.assertEqual(difficulty, 'easy')

    def test_default_config_passes_normal_difficulty(self) -> None:
        """Test that 'normal' config difficulty is passed to easy cross."""
        with patch('term_timer.scrambler.scramble_easy_cross') as mock_ec:
            mock_ec.return_value = (parse_moves('R U'), Algorithm())
            with patch(
                    'term_timer.scrambler.TRAINER_ECROSS_DIFFICULTY', 'normal',
            ):
                scrambler(3, 0, easy_cross=True, rng=self.rng)
            args, kwargs = mock_ec.call_args
            difficulty = args[0] if args else kwargs.get('difficulty')
            self.assertEqual(difficulty, 'normal')


class TestScramblerXCrossDifficulty(unittest.TestCase):
    """Tests for scrambler reading xcross difficulty and slots from config."""

    def setUp(self) -> None:
        """Set up a seeded RNG for reproducibility."""
        self.rng = Random(42)  # noqa: S311

    def test_passes_config_difficulty_to_x_cross(self) -> None:
        """Test that the config difficulty is passed to scramble_x_cross."""
        with patch('term_timer.scrambler.scramble_x_cross') as mock_xc:
            mock_xc.return_value = (parse_moves('R U'), Algorithm())
            with patch(
                    'term_timer.scrambler.TRAINER_XCROSS_DIFFICULTY', 'hard',
            ):
                scrambler(3, 0, x_cross=True, rng=self.rng)
            args, kwargs = mock_xc.call_args
            difficulty = args[0] if args else kwargs.get('difficulty')
            self.assertEqual(difficulty, 'hard')

    def test_passes_config_slots_to_x_cross(self) -> None:
        """Test that the config slots are passed to scramble_x_cross."""
        with patch('term_timer.scrambler.scramble_x_cross') as mock_xc:
            mock_xc.return_value = (parse_moves('R U'), Algorithm())
            with patch(
                    'term_timer.scrambler.TRAINER_XCROSS_SLOTS', ['FR', 'FL'],
            ):
                scrambler(3, 0, x_cross=True, rng=self.rng)
            args, _ = mock_xc.call_args
            self.assertEqual(args[1], ['FR', 'FL'])


class TestTrainerEasyCrossDifficulty(unittest.TestCase):
    """Tests for trainer reading ecross difficulty from config."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [make_training_case()]
        self.orientation = parse_moves('')

    def test_passes_config_difficulty_to_easy_cross(self) -> None:
        """Test that the config difficulty is passed to scramble_easy_cross."""
        with patch('term_timer.scrambler.scramble_easy_cross') as mock_ec:
            mock_ec.return_value = (parse_moves('R U'), Algorithm())
            with patch(
                    'term_timer.scrambler.TRAINER_ECROSS_DIFFICULTY', 'easy',
            ):
                trainer('ecross', self.cases, self.rng, self.orientation)
            args, kwargs = mock_ec.call_args
            difficulty = args[0] if args else kwargs.get('difficulty')
            self.assertEqual(difficulty, 'easy')


class TestTrainerXCrossDifficulty(unittest.TestCase):
    """Tests for trainer reading xcross difficulty and slots from config."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [make_training_case()]
        self.orientation = parse_moves('')

    def test_passes_config_difficulty_to_x_cross(self) -> None:
        """Test that the config difficulty is passed to scramble_x_cross."""
        with patch('term_timer.scrambler.scramble_x_cross') as mock_xc:
            mock_xc.return_value = (parse_moves('R U'), Algorithm())
            with patch(
                    'term_timer.scrambler.TRAINER_XCROSS_DIFFICULTY', 'hard',
            ):
                trainer('xcross', self.cases, self.rng, self.orientation)
            args, kwargs = mock_xc.call_args
            difficulty = args[0] if args else kwargs.get('difficulty')
            self.assertEqual(difficulty, 'hard')

    def test_passes_config_slots_to_x_cross(self) -> None:
        """Test that the config slots are passed to scramble_x_cross."""
        with patch('term_timer.scrambler.scramble_x_cross') as mock_xc:
            mock_xc.return_value = (parse_moves('R U'), Algorithm())
            with patch(
                    'term_timer.scrambler.TRAINER_XCROSS_SLOTS', ['FL', 'BR'],
            ):
                trainer('xcross', self.cases, self.rng, self.orientation)
            args, _ = mock_xc.call_args
            self.assertEqual(args[1], ['FL', 'BR'])
