import unittest

from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.solve import Solve


class TestSolveModule(unittest.TestCase):
    def test_solve_initialization(self):
        """Test initialization of a Solve object."""
        start_time = 1000000000
        end_time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(start_time, end_time, scramble)

        self.assertEqual(solve.start_time, start_time)
        self.assertEqual(solve.end_time, end_time)
        self.assertEqual(solve.scramble, scramble)
        self.assertEqual(solve.flag, '')
        self.assertEqual(solve.elapsed_time, end_time - start_time)

    def test_solve_with_string_times(self):
        """Test initialization of a Solve object with string times."""
        start_time = '1000000000'
        end_time = '1012345678'
        scramble = "F R U R' U' F'"

        solve = Solve(start_time, end_time, scramble)

        self.assertEqual(solve.start_time, 1000000000)
        self.assertEqual(solve.end_time, 1012345678)
        self.assertEqual(solve.elapsed_time, 12345678)

    def test_solve_final_time_normal(self):
        """Test the final_time property with no penalty."""
        start_time = 1000000000
        end_time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(start_time, end_time, scramble)

        self.assertEqual(solve.final_time, 12345678)

    def test_solve_final_time_plus_two(self):
        """Test the final_time property with +2 penalty."""
        start_time = 1000000000
        end_time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(start_time, end_time, scramble, PLUS_TWO)

        self.assertEqual(solve.final_time, 12345678 + (2 * SECOND))

    def test_solve_final_time_dnf(self):
        """Test the final_time property with DNF penalty."""
        start_time = 1000000000
        end_time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(start_time, end_time, scramble, DNF)

        self.assertEqual(solve.final_time, 0)

    def test_solve_string_representation(self):
        """Test the string representation of a Solve object."""
        start_time = 1000000000000
        end_time = 1005000000000  # 5 seconds
        scramble = "F R U R' U' F'"

        solve = Solve(start_time, end_time, scramble)

        # The exact string representation depends on format_time implementation,
        # but we can check that it contains the expected values
        self.assertIn('5.00', str(solve))

        # Test with +2 penalty
        solve.flag = PLUS_TWO
        self.assertIn('+2', str(solve))

        # Test with DNF
        solve.flag = DNF
        self.assertIn('DNF', str(solve))
