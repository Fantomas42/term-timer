import unittest
from unittest.mock import patch

from term_timer.list import Listing
from term_timer.solve import Solve


class TestListing(unittest.TestCase):
    def setUp(self):
        """Set up test cases with sample solves."""
        self.solves = [
            Solve(1000000000, 2000000000, 'F R U', ''),
            Solve(3000000000, 4000000000, 'R U F', ''),
            Solve(5000000000, 6000000000, 'U F R', 'DNF'),
            Solve(7000000000, 8000000000, 'F U R', '+2'),
        ]
        self.listing = Listing(self.solves)

    @patch('term_timer.list.console')
    def test_resume_no_solves(self, mock_console):  # noqa: PLR6301
        """Test that a warning is displayed when there are no solves."""
        empty_listing = Listing([])
        empty_listing.resume(5)

        mock_console.print.assert_called_once_with(
            '[warning]No saved solves yet.[/warning]',
        )

    @patch('term_timer.list.console')
    def test_resume_with_limit(self, mock_console):
        """Test that resume respects the limit parameter."""
        self.listing.resume(2)

        # Should print 2 solves
        self.assertEqual(mock_console.print.call_count, 2)

    @patch('term_timer.list.console')
    def test_resume_limit_larger_than_stack(self, mock_console):
        """Test that resume handles limits larger than the stack size."""
        self.listing.resume(10)

        # Should only print 4 solves (the size of our stack)
        self.assertEqual(mock_console.print.call_count, 4)

    @patch('term_timer.list.console')
    def test_resume_format(self, mock_console):
        """Test the formatting of the resume output."""
        self.listing.resume(1)

        # Check the format of the most recent solve
        call_args = mock_console.print.call_args[0]

        # The index should be #4 (for the 4th solve)
        self.assertIn('#4', call_args[0])

        # The time should be formatted
        self.assertIn('[result]00:01.000[/result]', call_args[1])

        # The scramble should be included
        self.assertIn('[consign]F U R[/consign]', call_args[2])

        # The flag should be included
        self.assertIn('[result]+2[/result]', call_args[3])

    @patch('term_timer.list.console')
    def test_resume_reverse_order(self, mock_console):
        """Test that solves are displayed in reverse order (newest first)."""
        self.listing.resume(4)

        # Get all the call arguments
        call_args_list = mock_console.print.call_args_list

        # First call should have #4 (newest)
        self.assertIn('#4', call_args_list[0][0][0])

        # Last call should have #1 (oldest)
        self.assertIn('#1', call_args_list[3][0][0])
