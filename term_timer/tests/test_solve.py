"""Tests for solve."""

import datetime
import unittest

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves

from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.methods.base import Analyser
from term_timer.solve import Solve


class TestSolveInitialization(unittest.TestCase):
    """Tests for Solve class initialization."""

    def test_solve_initialization(self) -> None:
        """Test initialization of a Solve object."""
        date = 1000000000
        time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble)

        self.assertEqual(solve.date, date)
        self.assertEqual(solve.time, time)
        self.assertEqual(str(solve.scramble), scramble)
        self.assertEqual(solve.flag, '')
        self.assertEqual(solve.comment, '')
        self.assertEqual(solve.timer, '')
        self.assertEqual(solve.device, '')
        self.assertEqual(solve.session, 'default')
        self.assertEqual(solve.solve_id, 0)
        self.assertEqual(solve.cube_size, 3)

    def test_solve_initialization_with_all_parameters(self) -> None:
        """Test initialization with all optional parameters."""
        date = 1000000000
        time = 1012345678
        scramble = "F R U R' U' F'"
        flag = PLUS_TWO
        timer = 'bluetooth'
        device = 'GAN12'
        session = 'test_session'
        comment = 'Great solve!'
        solve_id = 42
        cube_size = 4
        moves = "R U R' U'"

        solve = Solve(
            date, time, scramble,
            flag=flag, timer=timer, device=device,
            session=session, comment=comment,
            solve_id=solve_id, cube_size=cube_size,
            moves=moves,
        )

        self.assertEqual(solve.date, date)
        self.assertEqual(solve.time, time)
        self.assertEqual(solve.flag, flag)
        self.assertEqual(solve.timer, timer)
        self.assertEqual(solve.device, device)
        self.assertEqual(solve.session, session)
        self.assertEqual(solve.comment, comment)
        self.assertEqual(solve.solve_id, solve_id)
        self.assertEqual(solve.cube_size, cube_size)
        self.assertEqual(solve.raw_moves, moves)

    def test_solve_initialization_with_comment(self) -> None:
        """Test initialization of a Solve object with comment."""
        date = 1000000000
        time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble, comment='Comment')

        self.assertEqual(solve.date, date)
        self.assertEqual(solve.time, time)
        self.assertEqual(str(solve.scramble), scramble)
        self.assertEqual(solve.flag, '')
        self.assertEqual(solve.comment, 'Comment')

    def test_solve_with_string_date_time(self) -> None:
        """Test initialization of a Solve object with string times."""
        date = '1000000000'
        time = '1012345678'
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble)  # type: ignore[arg-type]

        self.assertEqual(solve.date, 1000000000)
        self.assertEqual(solve.time, 1012345678)

    def test_solve_with_float_date(self) -> None:
        """Test initialization with float date."""
        date = 1000000000.5
        time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble)

        self.assertEqual(solve.date, 1000000000)

    def test_solve_with_algorithm_scramble(self) -> None:
        """Test initialization with Algorithm object as scramble."""
        date = 1000000000
        time = 1012345678
        scramble_algo = parse_moves("F R U R' U' F'")

        solve = Solve(date, time, scramble_algo)

        self.assertIsInstance(solve.scramble, Algorithm)
        self.assertEqual(str(solve.scramble), "F R U R' U' F'")

    def test_solve_empty_session_defaults_to_default(self) -> None:
        """Test that empty session string defaults to 'default'."""
        solve = Solve(1000000000, 1012345678, "R U R'", session='')
        self.assertEqual(solve.session, 'default')


class TestSolveFinalTime(unittest.TestCase):
    """Tests for final_time property with penalties."""

    def test_solve_final_time_normal(self) -> None:
        """Test the final_time property with no penalty."""
        date = 1000000000
        time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble)

        self.assertEqual(solve.final_time, 1012345678)

    def test_solve_final_time_plus_two(self) -> None:
        """Test the final_time property with +2 penalty."""
        date = 1000000000
        time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble, PLUS_TWO)

        self.assertEqual(solve.final_time, 1012345678 + (2 * SECOND))

    def test_solve_final_time_dnf(self) -> None:
        """Test the final_time property with DNF penalty."""
        date = 1000000000
        time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble, DNF)

        self.assertEqual(solve.final_time, 0)

    def test_solve_final_time_zero_time(self) -> None:
        """Test final_time with zero time."""
        solve = Solve(1000000000, 0, "R U R'")
        self.assertEqual(solve.final_time, 0)

    def test_solve_final_time_zero_time_plus_two(self) -> None:
        """Test final_time with zero time and +2 penalty."""
        solve = Solve(1000000000, 0, "R U R'", PLUS_TWO)
        self.assertEqual(solve.final_time, 2 * SECOND)


class TestSolveStringRepresentation(unittest.TestCase):
    """Tests for string representation."""

    def test_solve_string_representation(self) -> None:
        """Test the string representation of a Solve object."""
        date = 1000000000000
        time = 1005000000000  # 5 seconds
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble)

        self.assertIn('5.00', str(solve))

    def test_solve_string_with_plus_two(self) -> None:
        """Test string representation with +2 penalty."""
        date = 1000000000000
        time = 1005000000000
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble, PLUS_TWO)

        self.assertIn('+2', str(solve))

    def test_solve_string_with_dnf(self) -> None:
        """Test string representation with DNF."""
        date = 1000000000000
        time = 1005000000000
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble, DNF)

        self.assertIn('DNF', str(solve))


class TestSolveCachedProperties(unittest.TestCase):
    """Tests for cached_property methods."""

    def test_solution_with_moves(self) -> None:
        """Test solution property with moves."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="F R U R' U' F'",
        )
        self.assertIsInstance(solve.solution, Algorithm)
        self.assertEqual(str(solve.solution), "F R U R' U' F'")
        self.assertEqual(len(solve.solution), 6)

    def test_solution_without_moves(self) -> None:
        """Test solution property without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsInstance(solve.solution, Algorithm)
        self.assertEqual(len(solve.solution), 0)
        self.assertEqual(str(solve.solution), '')

    def test_scramble_from_string(self) -> None:
        """Test scramble property from string."""
        solve = Solve(1000000000, 1012345678, "F R U R' U' F'")
        self.assertIsInstance(solve.scramble, Algorithm)
        self.assertEqual(str(solve.scramble), "F R U R' U' F'")

    def test_scramble_from_algorithm(self) -> None:
        """Test scramble property from Algorithm."""
        algo = parse_moves("F R U R' U' F'")
        solve = Solve(1000000000, 1012345678, algo)
        self.assertIsInstance(solve.scramble, Algorithm)
        self.assertEqual(str(solve.scramble), "F R U R' U' F'")
        self.assertIs(solve.scramble, algo)

    def test_datetime_conversion(self) -> None:
        """Test datetime property."""
        date = 1000000000
        solve = Solve(date, 1012345678, "R U R'")

        dt = solve.datetime
        self.assertIsInstance(dt, datetime.datetime)
        self.assertEqual(dt.tzinfo, datetime.UTC)
        self.assertEqual(
            dt,
            datetime.datetime(2001, 9, 9, 1, 46, 40, tzinfo=datetime.UTC),
        )

    def test_datetime_with_recent_date(self) -> None:
        """Test datetime with recent timestamp."""
        date = 1700000000
        solve = Solve(date, 1012345678, "R U R'")

        dt = solve.datetime
        self.assertEqual(
            dt,
            datetime.datetime(2023, 11, 14, 22, 13, 20, tzinfo=datetime.UTC),
        )

    def test_move_times_extraction(self) -> None:
        """Test move_times property."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="R@100 U@200 R'@300",
        )
        move_times = solve.move_times
        self.assertEqual(len(move_times), 3)
        self.assertEqual(move_times[0], ('R', 100))
        self.assertEqual(move_times[1], ('U', 200))
        self.assertEqual(move_times[2], ("R'", 300))

    def test_move_times_empty(self) -> None:
        """Test move_times with no moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.move_times, [])

    def test_advanced_with_moves(self) -> None:
        """Test advanced property with moves."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="F R U R' U' F'",
        )
        self.assertTrue(solve.advanced)

    def test_advanced_without_moves(self) -> None:
        """Test advanced property without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertFalse(solve.advanced)

    def test_advanced_with_empty_moves(self) -> None:
        """Test advanced property with empty moves string."""
        solve = Solve(1000000000, 1012345678, "R U R'", moves='')
        self.assertFalse(solve.advanced)

    def test_rotations_with_moves(self) -> None:
        """Test rotations counting."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="x R U R' x' y",
        )
        self.assertEqual(solve.rotations, 3)

    def test_rotations_without_moves(self) -> None:
        """Test rotations without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.rotations, 0)

    def test_rotations_no_rotations(self) -> None:
        """Test rotations with moves but no rotation moves."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="R U R' U' R' F R F'",
        )
        self.assertEqual(solve.rotations, 0)


class TestSolveStaticMethods(unittest.TestCase):
    """Tests for static methods."""

    def test_compute_tps_normal(self) -> None:
        """Test TPS calculation with normal values."""
        tps = Solve.compute_tps(50, 10 * SECOND)
        self.assertEqual(tps, 5.0)

    def test_compute_tps_zero_time(self) -> None:
        """Test TPS calculation with zero time."""
        tps = Solve.compute_tps(50, 0)
        self.assertEqual(tps, 0)

    def test_compute_tps_high_speed(self) -> None:
        """Test TPS calculation with high speed."""
        tps = Solve.compute_tps(100, 5 * SECOND)
        self.assertEqual(tps, 20.0)

    def test_compute_tps_slow_speed(self) -> None:
        """Test TPS calculation with slow speed."""
        tps = Solve.compute_tps(10, 20 * SECOND)
        self.assertEqual(tps, 0.5)

    def test_compute_tps_fractional(self) -> None:
        """Test TPS calculation with fractional result."""
        tps = Solve.compute_tps(37, 10 * SECOND)
        self.assertEqual(tps, 3.7)

    def test_missed_moves_pair_no_optimization(self) -> None:
        """Test missed_moves_pair with optimal algorithm."""
        algo = parse_moves("R U R' U'")
        source, compressed = Solve.missed_moves_pair(algo)

        self.assertEqual(str(source), "R U R' U'")
        self.assertEqual(str(compressed), "R U R' U'")
        self.assertEqual(source.metrics.qtm, compressed.metrics.qtm)

    def test_missed_moves_pair_with_optimization(self) -> None:
        """Test missed_moves_pair with inefficient algorithm."""
        algo = parse_moves("R R' U U U")
        source, compressed = Solve.missed_moves_pair(algo)

        self.assertEqual(str(source), "R R' U U U")
        self.assertNotEqual(str(source), str(compressed))
        self.assertLess(compressed.metrics.qtm, source.metrics.qtm)

    def test_missed_moves_pair_do_undo(self) -> None:
        """Test missed_moves_pair with do-undo moves."""
        algo = parse_moves("R U R' U'")
        source, compressed = Solve.missed_moves_pair(algo)

        self.assertGreaterEqual(source.metrics.qtm, compressed.metrics.qtm)

    def test_missed_moves_pair_empty_algorithm(self) -> None:
        """Test missed_moves_pair with empty algorithm."""
        algo = Algorithm()
        source, compressed = Solve.missed_moves_pair(algo)

        self.assertEqual(len(source), 0)
        self.assertEqual(len(compressed), 0)


class TestSolveTPS(unittest.TestCase):
    """Tests for TPS calculations."""

    def test_tps_with_moves(self) -> None:
        """Test TPS calculation with moves."""
        solve = Solve(
            1000000000, 10 * SECOND, "R U R'",
            moves="R U R' U' R' F R2 U' R' U'",
        )
        expected_tps = 10 / 10
        self.assertEqual(solve.tps, expected_tps)

    def test_tps_without_moves(self) -> None:
        """Test TPS with no moves."""
        solve = Solve(1000000000, 10 * SECOND, "R U R'")
        self.assertEqual(solve.tps, 0.0)

    def test_tps_zero_time(self) -> None:
        """Test TPS with zero time."""
        solve = Solve(1000000000, 0, "R U R'", moves="R U R'")
        self.assertEqual(solve.tps, 0.0)


class TestSolveOrientationProperties(unittest.TestCase):
    """Tests for orientation-related properties."""

    def test_orientation_faces_explicit(self) -> None:
        """Test orientation_faces with explicit orientation."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        solve.orientation = 'WG'
        self.assertEqual(solve.orientation_faces, 'WG')

    def test_orientation_faces_default(self) -> None:
        """Test orientation_faces with default orientation."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsInstance(solve.orientation_faces, str)
        self.assertEqual(len(solve.orientation_faces), 2)

    def test_orientation_moves_with_orientation(self) -> None:
        """Test orientation_moves property."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        solve.orientation = 'UF'
        self.assertIsInstance(solve.orientation_moves, Algorithm)

    def test_reconstruction_with_moves(self) -> None:
        """Test reconstruction property."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="R U R' U'",
        )
        self.assertIsInstance(solve.reconstruction, Algorithm)


class TestSolveMethodAnalysis(unittest.TestCase):
    """Tests for method analysis properties."""

    def test_method_analyser_default(self) -> None:
        """Test method_analyser property returns a class."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertTrue(issubclass(solve.method_analyser, Analyser))

    def test_method_applied_without_moves(self) -> None:
        """Test method_applied without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsNone(solve.method_applied)

    def test_method_applied_with_moves(self) -> None:
        """Test method_applied with moves and proper timing."""
        solve = Solve(
            1000000000, 10000000000, "R U R'",
            moves="R@100 U@200 R'@300 U'@400 R'@500 F@600 R@700 F'@800",
        )
        self.assertIsNotNone(solve.method_applied)

    def test_aufs_without_method(self) -> None:
        """Test aufs without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.aufs, 0)

    def test_recognition_time_without_method(self) -> None:
        """Test recognition_time without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.recognition_time, 0)

    def test_execution_time_without_method(self) -> None:
        """Test execution_time without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.execution_time, 0)

    def test_score_without_method(self) -> None:
        """Test score without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsNone(solve.score)


class TestSolveMissedMoves(unittest.TestCase):
    """Tests for missed moves calculations."""

    def test_missed_moves_optimal(self) -> None:
        """Test missed_moves with optimal algorithm."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="R U R' U'",
        )
        algo = parse_moves("R U R' U'")
        missed = solve.missed_moves(algo)
        self.assertEqual(missed, 0)

    def test_missed_moves_with_inefficiency(self) -> None:
        """Test missed_moves with inefficient algorithm."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="R U R' U'",
        )
        algo = parse_moves('R R R U')
        missed = solve.missed_moves(algo)
        self.assertGreater(missed, 0)

    def test_missed_moves_empty_algorithm(self) -> None:
        """Test missed_moves with empty algorithm."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        missed = solve.missed_moves(Algorithm())
        self.assertEqual(missed, 0)

    def test_all_missed_moves_without_moves(self) -> None:
        """Test all_missed_moves without solution."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.all_missed_moves, 0)

    def test_step_missed_moves_without_method(self) -> None:
        """Test step_missed_moves without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.step_missed_moves, 0)

    def test_execution_missed_moves_without_method(self) -> None:
        """Test execution_missed_moves without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.execution_missed_moves, 0)

    def test_transition_missed_moves_calculation(self) -> None:
        """Test transition_missed_moves calculation."""
        solve = Solve(
            1000000000, 10000000000, "R U R'",
            moves='R@100 R@200 R@300 U@400',
        )
        transition = solve.transition_missed_moves
        expected = solve.all_missed_moves - solve.step_missed_moves
        self.assertEqual(transition, expected)


class TestSolvePauses(unittest.TestCase):
    """Tests for pause detection."""

    def test_pauses_empty_algorithm(self) -> None:
        """Test pauses with empty algorithm."""
        solve = Solve(1000000000, 1012345678, "R U R'", moves='R@100')
        pauses = solve.pauses(Algorithm())
        self.assertEqual(pauses, 0)

    def test_pauses_single_move(self) -> None:
        """Test pauses with single move returns 0."""
        algo = parse_moves('R@0')
        pauses = 0
        self.assertEqual(pauses, 0)
        self.assertEqual(len(algo), 1)

    def test_pauses_fast_sequence(self) -> None:
        """Test pauses with fast execution."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            moves="R@100 U@200 R'@300",
        )
        algo = parse_moves("R@100 U@200 R'@300")
        pauses = solve.pauses(algo)
        self.assertGreaterEqual(pauses, 0)

    def test_step_pauses_without_method(self) -> None:
        """Test step_pauses without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.step_pauses, 0)

    def test_execution_pauses_without_method(self) -> None:
        """Test execution_pauses without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.execution_pauses, 0)

    def test_pause_threshold_calculation(self) -> None:
        """Test pause_threshold property."""
        solve = Solve(
            1000000000, 1000000000, "R U R'",
            moves='R@100 U@200',
        )
        threshold = solve.pause_threshold
        self.assertGreater(threshold, 0)
        self.assertEqual(threshold, solve.move_speed * 2)


class TestSolveSerialization(unittest.TestCase):
    """Tests for as_save property."""

    def test_as_save_minimal(self) -> None:
        """Test as_save with minimal solve."""
        date = 1000000000
        time = 1012345678
        scramble = "R U R'"

        solve = Solve(date, time, scramble)
        data = solve.as_save

        self.assertEqual(data['date'], date)
        self.assertEqual(data['time'], time)
        self.assertEqual(data['scramble'], scramble)
        self.assertNotIn('flag', data)
        self.assertNotIn('timer', data)
        self.assertNotIn('device', data)
        self.assertNotIn('moves', data)
        self.assertNotIn('comment', data)

    def test_as_save_with_flag(self) -> None:
        """Test as_save with flag."""
        solve = Solve(1000000000, 1012345678, "R U R'", flag=PLUS_TWO)
        data = solve.as_save

        self.assertEqual(data['flag'], PLUS_TWO)

    def test_as_save_with_dnf(self) -> None:
        """Test as_save with DNF."""
        solve = Solve(1000000000, 1012345678, "R U R'", flag=DNF)
        data = solve.as_save

        self.assertEqual(data['flag'], DNF)

    def test_as_save_with_timer(self) -> None:
        """Test as_save with timer."""
        solve = Solve(1000000000, 1012345678, "R U R'", timer='bluetooth')
        data = solve.as_save

        self.assertEqual(data['timer'], 'bluetooth')

    def test_as_save_with_device(self) -> None:
        """Test as_save with device."""
        solve = Solve(1000000000, 1012345678, "R U R'", device='GAN12')
        data = solve.as_save

        self.assertEqual(data['device'], 'GAN12')

    def test_as_save_with_moves(self) -> None:
        """Test as_save with moves."""
        moves = "R U R' U'"
        solve = Solve(1000000000, 1012345678, "R U R'", moves=moves)
        data = solve.as_save

        self.assertEqual(data['moves'], moves)

    def test_as_save_with_comment(self) -> None:
        """Test as_save with comment."""
        comment = 'Great solve!'
        solve = Solve(1000000000, 1012345678, "R U R'", comment=comment)
        data = solve.as_save

        self.assertEqual(data['comment'], comment)

    def test_as_save_complete(self) -> None:
        """Test as_save with all fields."""
        date = 1000000000
        time = 1012345678
        scramble = "R U R'"
        flag = PLUS_TWO
        timer = 'bluetooth'
        device = 'GAN12'
        moves = "R U R' U'"
        comment = 'Perfect!'

        solve = Solve(
            date, time, scramble,
            flag=flag, timer=timer, device=device,
            moves=moves, comment=comment,
        )
        data = solve.as_save

        self.assertEqual(data['date'], date)
        self.assertEqual(data['time'], time)
        self.assertEqual(data['scramble'], scramble)
        self.assertEqual(data['flag'], flag)
        self.assertEqual(data['timer'], timer)
        self.assertEqual(data['device'], device)
        self.assertEqual(data['moves'], moves)
        self.assertEqual(data['comment'], comment)

    def test_as_save_empty_string_exclusion(self) -> None:
        """Test as_save excludes empty strings."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            flag='', timer='', device='', comment='',
        )
        data = solve.as_save

        self.assertNotIn('flag', data)
        self.assertNotIn('timer', data)
        self.assertNotIn('device', data)
        self.assertNotIn('comment', data)

    def test_as_save_is_dict(self) -> None:
        """Test as_save returns dictionary."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        data = solve.as_save

        self.assertIsInstance(data, dict)

    def test_as_save_scramble_from_algorithm(self) -> None:
        """Test as_save converts Algorithm scramble to string."""
        algo = parse_moves("R U R'")
        solve = Solve(1000000000, 1012345678, algo)
        data = solve.as_save

        self.assertIsInstance(data['scramble'], str)
        self.assertEqual(data['scramble'], "R U R'")


class TestSolveURLGeneration(unittest.TestCase):
    """Tests for URL generation properties."""

    def test_link_alg_cubing(self) -> None:
        """Test link_alg_cubing property."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        link = solve.link_alg_cubing

        self.assertIsInstance(link, str)
        self.assertIn('alg.cubing.net', link)

    def test_link_cube_db(self) -> None:
        """Test link_cube_db property."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        link = solve.link_cube_db

        self.assertIsInstance(link, str)
        self.assertIn('cubedb.net', link)

    def test_link_term_timer(self) -> None:
        """Test link_term_timer property."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            session='test', solve_id=42, cube_size=3,
        )
        link = solve.link_term_timer

        self.assertIsInstance(link, str)
        self.assertIn('/3/test/42/', link)

    def test_link_term_timer_custom_cube_size(self) -> None:
        """Test link_term_timer with custom cube size."""
        solve = Solve(
            1000000000, 1012345678, "R U R'",
            session='test', solve_id=10, cube_size=4,
        )
        link = solve.link_term_timer

        self.assertIn('/4/test/10/', link)


class TestSolveReportLines(unittest.TestCase):
    """Tests for report line generation."""

    def test_report_line_without_advanced(self) -> None:
        """Test report_line without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.report_line, '')

    def test_trainer_line_without_advanced(self) -> None:
        """Test trainer_line without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.trainer_line, '')

    def test_method_line_without_method_applied(self) -> None:
        """Test method_line without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.method_line, '')

    def test_method_text_without_advanced(self) -> None:
        """Test method_text without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.method_text, '')


class TestSolveMoveSpeed(unittest.TestCase):
    """Tests for move speed calculations."""

    def test_move_speed_with_timing(self) -> None:
        """Test move_speed property."""
        solve = Solve(
            1000000000, 1000000000, "R U R'",
            moves='R@100 U@200',
        )
        move_speed = solve.move_speed
        self.assertGreater(move_speed, 0)

    def test_move_speed_calculation(self) -> None:
        """Test move_speed is execution_time divided by solution length."""
        solve = Solve(
            1000000000, 1000000000, "R U R'",
            moves="R@100 U@200 R'@300 U'@400",
        )
        if solve.advanced and len(solve.solution) > 0:
            expected = solve.execution_time / len(solve.solution)
            self.assertEqual(solve.move_speed, expected)


class TestSolveReconstructionTiming(unittest.TestCase):
    """Tests for reconstruction_steps_timing."""

    def test_reconstruction_steps_timing_without_advanced(self) -> None:
        """Test reconstruction_steps_timing without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.reconstruction_steps_timing, [])

    def test_reconstruction_steps_timing_without_method(self) -> None:
        """Test reconstruction_steps_timing without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertEqual(solve.reconstruction_steps_timing, [])


class TestSolveEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions."""

    def test_solve_zero_date(self) -> None:
        """Test solve with zero date."""
        solve = Solve(0, 1012345678, "R U R'")
        self.assertEqual(solve.date, 0)

    def test_solve_negative_time(self) -> None:
        """Test solve with negative time."""
        solve = Solve(1000000000, -100, "R U R'")
        self.assertEqual(solve.time, -100)

    def test_solve_very_large_time(self) -> None:
        """Test solve with very large time."""
        large_time = 1000 * SECOND
        solve = Solve(1000000000, large_time, "R U R'")
        self.assertEqual(solve.time, large_time)

    def test_solve_empty_scramble(self) -> None:
        """Test solve with empty scramble."""
        solve = Solve(1000000000, 1012345678, '')
        self.assertEqual(str(solve.scramble), '')
        self.assertEqual(len(solve.scramble), 0)

    def test_solve_long_scramble(self) -> None:
        """Test solve with very long scramble."""
        long_scramble = ' '.join(["R U R' U'"] * 20)
        solve = Solve(1000000000, 1012345678, long_scramble)
        self.assertGreater(len(solve.scramble), 50)

    def test_solve_special_characters_in_comment(self) -> None:
        """Test solve with special characters in comment."""
        comment = "Test!@#$%^&*()_+-=[]{}|;':\",./<>?"
        solve = Solve(1000000000, 1012345678, "R U R'", comment=comment)
        self.assertEqual(solve.comment, comment)

    def test_solve_unicode_in_comment(self) -> None:
        """Test solve with unicode in comment."""
        comment = 'Great solve! 🎉 🧊'
        solve = Solve(1000000000, 1012345678, "R U R'", comment=comment)
        self.assertEqual(solve.comment, comment)

    def test_solve_very_long_comment(self) -> None:
        """Test solve with very long comment."""
        comment = 'x' * 10000
        solve = Solve(1000000000, 1012345678, "R U R'", comment=comment)
        self.assertEqual(len(solve.comment), 10000)

    def test_solve_max_cube_size(self) -> None:
        """Test solve with maximum cube size."""
        solve = Solve(1000000000, 1012345678, "R U R'", cube_size=7)
        self.assertEqual(solve.cube_size, 7)

    def test_solve_min_cube_size(self) -> None:
        """Test solve with minimum cube size."""
        solve = Solve(1000000000, 1012345678, "R U R'", cube_size=2)
        self.assertEqual(solve.cube_size, 2)

    def test_solve_complex_moves_notation(self) -> None:
        """Test solve with complex move notation."""
        moves = "Rw U2 x' D2 Fw' 3Uw M' E S"
        solve = Solve(1000000000, 1012345678, "R U R'", moves=moves)
        self.assertIsNotNone(solve.solution)

    def test_solve_moves_with_timing(self) -> None:
        """Test solve with timed moves."""
        moves = "R@0 U@100 R'@200 U'@300 R'@400 F@500 R@600 F'@700"
        solve = Solve(1000000000, 1012345678, "R U R'", moves=moves)
        self.assertEqual(len(solve.solution), 8)
        self.assertEqual(len(solve.move_times), 8)


class TestSolveReconstructionStepMethods(unittest.TestCase):
    """Tests for reconstruction_step_line and reconstruction_step_text."""

    def test_reconstruction_step_line_empty_moves(self) -> None:
        """Test reconstruction_step_line with empty moves."""
        solve = Solve(1000000000, 1012345678, "R U R'", moves='R@100')
        step_summary: dict = {
            'name': 'Test',
            'type': 'step',
            'moves': Algorithm(),
            'moves_humanized': Algorithm(),
            'moves_prettified': Algorithm(),
            'aufs': (0, 0),
            'total': 0,
            'recognition': 0,
            'execution': 0,
            'qtm': 0,
        }
        result = solve.reconstruction_step_line(step_summary, multiple=False)
        self.assertEqual(result, '')

    def test_reconstruction_step_text_empty_moves(self) -> None:
        """Test reconstruction_step_text with empty moves."""
        solve = Solve(1000000000, 1012345678, "R U R'", moves='R@100')
        step_summary: dict = {
            'name': 'Test',
            'type': 'step',
            'moves': Algorithm(),
            'moves_humanized': Algorithm(),
            'aufs': (0, 0),
            'post_pause': 0,
        }
        result = solve.reconstruction_step_text(step_summary, multiple=False)
        self.assertEqual(result, '')


class TestSolveMethodTextBuilder(unittest.TestCase):
    """Tests for method_text_builder method."""

    def test_method_text_builder_without_advanced(self) -> None:
        """Test method_text_builder without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        result = solve.method_text_builder(multiple=False)
        self.assertEqual(result, '')

    def test_method_text_builder_without_method_applied(self) -> None:
        """Test method_text_builder without method analysis."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        result = solve.method_text_builder(multiple=True)
        self.assertEqual(result, '')


class TestSolveGraphMethods(unittest.TestCase):
    """Tests for graph generation methods."""

    def test_time_graph_without_advanced(self) -> None:
        """Test time_graph without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        result = solve.time_graph()
        self.assertIsNone(result)

    def test_tps_graph_without_advanced(self) -> None:
        """Test tps_graph without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        result = solve.tps_graph()
        self.assertIsNone(result)

    def test_recognition_graph_without_advanced(self) -> None:
        """Test recognition_graph without moves."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        result = solve.recognition_graph()
        self.assertIsNone(result)


class TestSolveTypeConsistency(unittest.TestCase):
    """Tests for type consistency and conversions."""

    def test_date_is_integer(self) -> None:
        """Test that date is always stored as integer."""
        solve = Solve(1000000000.9, 1012345678, "R U R'")
        self.assertIsInstance(solve.date, int)

    def test_time_is_integer(self) -> None:
        """Test that time is always stored as integer."""
        solve = Solve(1000000000, 1012345678.9, "R U R'")
        self.assertIsInstance(solve.time, int)

    def test_final_time_is_integer(self) -> None:
        """Test that final_time is always integer."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsInstance(solve.final_time, int)

    def test_solution_is_algorithm(self) -> None:
        """Test that solution is always Algorithm."""
        solve = Solve(1000000000, 1012345678, "R U R'", moves="R U R'")
        self.assertIsInstance(solve.solution, Algorithm)

    def test_scramble_is_algorithm(self) -> None:
        """Test that scramble is always Algorithm."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsInstance(solve.scramble, Algorithm)

    def test_datetime_is_datetime(self) -> None:
        """Test that datetime is datetime object."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsInstance(solve.datetime, datetime.datetime)

    def test_tps_is_float(self) -> None:
        """Test that tps is float."""
        solve = Solve(1000000000, 1012345678, "R U R'", moves="R U R'")
        self.assertIsInstance(solve.tps, float)

    def test_advanced_is_bool(self) -> None:
        """Test that advanced is bool."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsInstance(solve.advanced, bool)

    def test_rotations_is_int(self) -> None:
        """Test that rotations is int."""
        solve = Solve(1000000000, 1012345678, "R U R'")
        self.assertIsInstance(solve.rotations, int)


class TestSolveMultipleInstances(unittest.TestCase):
    """Tests for multiple Solve instances."""

    def test_multiple_solves_independence(self) -> None:
        """Test that multiple solves are independent."""
        solve1 = Solve(1000000000, 1000000000, "R U R'")
        solve2 = Solve(2000000000, 2000000000, "F R U R'")

        self.assertNotEqual(solve1.date, solve2.date)
        self.assertNotEqual(solve1.time, solve2.time)
        self.assertNotEqual(str(solve1.scramble), str(solve2.scramble))

    def test_cached_properties_independence(self) -> None:
        """Test that cached properties don't interfere."""
        solve1 = Solve(1000000000, 1000000000, "R U R'", moves="R U R'")
        solve2 = Solve(2000000000, 2000000000, "F R U R'", moves="F R U R'")

        sol1 = solve1.solution
        sol2 = solve2.solution

        self.assertIsNot(sol1, sol2)
        self.assertNotEqual(str(sol1), str(sol2))

    def test_modification_does_not_affect_others(self) -> None:
        """Test that modifying one solve doesn't affect others."""
        solve1 = Solve(1000000000, 1000000000, "R U R'")
        solve2 = Solve(1000000000, 1000000000, "R U R'")

        solve1.flag = PLUS_TWO

        self.assertEqual(solve1.flag, PLUS_TWO)
        self.assertEqual(solve2.flag, '')
