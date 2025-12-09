"""Tests for solve."""

import unittest

from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.solve import Solve


class TestSolveModule(unittest.TestCase):
    """Tests for Solve class initialization and properties."""

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

    def test_solve_initialization_with_comment(self) -> None:
        """Test initialization of a Solve object."""
        date = 1000000000
        time = 1012345678
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble, comment='Comment')

        self.assertEqual(solve.date, date)
        self.assertEqual(solve.time, time)
        self.assertEqual(str(solve.scramble), scramble)
        self.assertEqual(solve.flag, '')
        self.assertEqual(solve.comment, 'Comment')

    def test_solve_with_string(self) -> None:
        """Test initialization of a Solve object with string times."""
        date = '1000000000'
        time = '1012345678'
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble)  # type: ignore[arg-type]

        self.assertEqual(solve.date, 1000000000)
        self.assertEqual(solve.time, 1012345678)

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

    def test_solve_string_representation(self) -> None:
        """Test the string representation of a Solve object."""
        date = 1000000000000
        time = 1005000000000  # 5 seconds
        scramble = "F R U R' U' F'"

        solve = Solve(date, time, scramble)

        # The exact string representation depends on format_time implementation,
        # but we can check that it contains the expected values
        self.assertIn('5.00', str(solve))

        # Test with +2 penalty
        solve.flag = PLUS_TWO
        self.assertIn('+2', str(solve))

        # Test with DNF
        solve.flag = DNF
        self.assertIn('DNF', str(solve))
