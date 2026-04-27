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
    return TrainingCase(case=case, best_setups=list(case.setup_algorithms[:2]))


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
        result = trainer('ecross', self.cases, self.orientation, self.rng)
        self.assertEqual(len(result), 4)

    def test_ecross_returns_correct_types(self) -> None:
        """Test that ecross trainer returns correct types for each element."""
        case, scramble, solution, cube = trainer(
            'ecross', self.cases, self.orientation, self.rng,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_ecross_cube_is_scrambled(self) -> None:
        """Test that ecross returns a scrambled cube."""
        _, _, _, cube = trainer(
            'ecross', self.cases, self.orientation, self.rng,
        )
        self.assertNotEqual(cube.state, SOLVED_FACELETS_3x3x3)

    def test_ecross_uses_scramble_easy_cross(self) -> None:
        """Test that ecross step calls scramble_easy_cross."""
        with patch('term_timer.scrambler.scramble_easy_cross') as mock_ec:
            mock_ec.return_value = (parse_moves('R U'), parse_moves('U R'))
            trainer('ecross', self.cases, self.orientation, self.rng)
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
        case, scramble, solution, cube = trainer(
            'xcross', self.cases, self.orientation, self.rng,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_xcross_uses_scramble_x_cross(self) -> None:
        """Test that xcross step calls scramble_x_cross."""
        with patch('term_timer.scrambler.scramble_x_cross') as mock_xc:
            mock_xc.return_value = (parse_moves('R U'), parse_moves('U R'))
            trainer('xcross', self.cases, self.orientation, self.rng)
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
        case, scramble, solution, cube = trainer(
            'cross', self.cases, self.orientation, self.rng,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_cross_uses_scrambler(self) -> None:
        """Test that cross step uses the scrambler function."""
        with patch('term_timer.scrambler.scrambler') as mock_sc:
            mock_sc.return_value = (parse_moves('R U'), VCube(size=3))
            trainer('cross', self.cases, self.orientation, self.rng)
            mock_sc.assert_called_once()

    def test_cross_solution_is_empty(self) -> None:
        """Test that cross step returns an empty solution algorithm."""
        _, _, solution, _ = trainer(
            'cross', self.cases, self.orientation, self.rng,
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
        case, scramble, solution, cube = trainer(
            'oll', self.cases, self.orientation, self.rng,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)
        self.assertIsInstance(cube, VCube)

    def test_oll_uses_random_training(self) -> None:
        """Test that non-special steps fall through to random_training."""
        with patch('term_timer.scrambler.random_training') as mock_rt:
            oll_case = get_case('OLL', '01')
            mock_rt.return_value = (
                oll_case,
                parse_moves('R U'),
                parse_moves('U R'),
            )
            trainer('oll', self.cases, self.orientation, self.rng)
            mock_rt.assert_called_once()

    def test_oll_case_matches_selected(self) -> None:
        """Test that the returned case is a valid case from the input list."""
        case, _, _, _ = trainer(
            'oll', self.cases, self.orientation, self.rng,
        )
        valid_case_codes = {tc.case.code for tc in self.cases}
        self.assertIn(case.code, valid_case_codes)


class TestTrainerBluetoothCube(unittest.TestCase):
    """Tests for trainer function with bluetooth_cube parameter."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.rng = Random(42)  # noqa: S311
        self.cases = [make_training_case()]
        self.orientation = parse_moves('')

    def test_with_bluetooth_cube_copies_state(self) -> None:
        """Test that a provided bluetooth_cube is used as the base state."""
        bt_cube = VCube(size=3)
        bt_cube.rotate('R U')

        _, _, _, cube = trainer(
            'ecross', self.cases, self.orientation, self.rng,
            bluetooth_cube=bt_cube,
        )

        self.assertIsInstance(cube, VCube)

    def test_without_bluetooth_cube_uses_solved(self) -> None:
        """Test that without bluetooth_cube a fresh solved cube is the base."""
        with patch('term_timer.scrambler.scramble_easy_cross') as mock_ec:
            fresh_cube = VCube(size=3)
            mock_ec.return_value = (parse_moves(''), Algorithm())
            _, _, _, cube = trainer(
                'ecross', self.cases, self.orientation, self.rng,
            )
            self.assertEqual(cube.state, fresh_cube.state)


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
        self.orientation = parse_moves('')

    def test_returns_three_tuple(self) -> None:
        """Test that random_training returns a three-element tuple."""
        result = random_training(self.cases, self.orientation, self.rng)
        self.assertEqual(len(result), 3)

    def test_returns_correct_types(self) -> None:
        """Test that random_training returns correct types."""
        case, scramble, solution = random_training(
            self.cases, self.orientation, self.rng,
        )
        self.assertIsInstance(case, Case)
        self.assertIsInstance(scramble, Algorithm)
        self.assertIsInstance(solution, Algorithm)

    def test_returned_case_is_from_input(self) -> None:
        """Test that the returned case is one of the input cases."""
        valid_codes = {tc.case.code for tc in self.cases}
        for _ in range(10):
            case, _, _ = random_training(
                self.cases, self.orientation, self.rng,
            )
            self.assertIn(case.code, valid_codes)

    def test_solution_matches_case_main_algorithm(self) -> None:
        """Test that the returned solution is the case's main algorithm."""
        case, _, solution = random_training(
            self.cases, self.orientation, self.rng,
        )
        self.assertEqual(str(solution), str(case.main_algorithm))

    def test_orientation_moves_incorporated(self) -> None:
        """Test that orientation moves are included in scramble generation."""
        orientation = parse_moves('x y')
        _, algo1, _ = random_training(
            self.cases, orientation, Random(42),  # noqa: S311
        )
        _, algo2, _ = random_training(
            self.cases, parse_moves(''), Random(42),  # noqa: S311
        )
        self.assertNotEqual(str(algo1), str(algo2))

    def test_single_case_always_selected(self) -> None:
        """Test that with a single case it is always selected."""
        single_cases = [make_training_case('01', 'OLL')]
        expected_code = single_cases[0].case.code
        for _ in range(5):
            case, _, _ = random_training(
                single_cases, self.orientation, self.rng,
            )
            self.assertEqual(case.code, expected_code)

    def test_scramble_transforms_applied(self) -> None:
        """Test that scramble has degrip and rotation compression applied."""
        cases = [make_training_case('01', 'OLL')]
        _, scramble, _ = random_training(cases, self.orientation, self.rng)
        algo_str = str(scramble)
        self.assertNotIn('@', algo_str)

    def test_rng_determines_selection(self) -> None:
        """Test that the same RNG seed produces the same case selection."""
        case1, _, _ = random_training(
            self.cases, self.orientation, Random(99),  # noqa: S311
        )
        case2, _, _ = random_training(
            self.cases, self.orientation, Random(99),  # noqa: S311
        )
        self.assertEqual(case1.code, case2.code)
