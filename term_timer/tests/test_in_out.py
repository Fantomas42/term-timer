import unittest
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.solve import Solve


class TestInOut(unittest.TestCase):
    @patch('term_timer.in_out.SAVE_DIRECTORY', Path('/mock/path'))
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.open')
    def test_load_solves_existing_file(self, mock_open_file, mock_exists):
        """Test loading solves from an existing file."""
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.__enter__.return_value.readlines.return_value = [
            "9.24;1000000000;2000000000;F R U' B L D;;\n",
            "10.50;2000000000;3000000000;R U F' D;+2;\n",
        ]
        mock_open_file.return_value = mock_file

        solves = load_solves(3)

        # Check that we have 2 solves
        self.assertEqual(len(solves), 2)

        # Check the first solve
        self.assertEqual(solves[0].start_time, 1000000000)
        self.assertEqual(solves[0].end_time, 2000000000)
        self.assertEqual(solves[0].scramble, "F R U' B L D")
        self.assertEqual(solves[0].flag, '')

        # Check the second solve
        self.assertEqual(solves[1].start_time, 2000000000)
        self.assertEqual(solves[1].end_time, 3000000000)
        self.assertEqual(solves[1].scramble, "R U F' D")
        self.assertEqual(solves[1].flag, '+2')

    @patch('term_timer.in_out.SAVE_DIRECTORY', Path('/mock/path'))
    @patch('pathlib.Path.exists')
    def test_load_solves_non_existing_file(self, mock_exists):
        """Test loading solves from a non-existing file returns empty list."""
        mock_exists.return_value = False

        solves = load_solves(3)

        self.assertEqual(solves, [])

    @patch('term_timer.in_out.SAVE_DIRECTORY', Path('/mock/path'))
    @patch('pathlib.Path.open', new_callable=mock_open)
    def test_save_solves(self, mock_file):
        """Test saving solves to a file."""
        # Create some test solves
        solves = [
            Solve(1000000000, 2000000000, 'F R U', ''),
            Solve(3000000000, 4000000000, 'B L D', 'DNF'),
        ]

        save_solves(3, solves)

        # Check that file was opened for writing
        mock_file.assert_called_once_with('w+')

        # Check writes to the file
        handle = mock_file()
        self.assertEqual(handle.write.call_count, 2)

        # First write should contain the first solve
        call_args_list = handle.write.call_args_list
        self.assertIn(
            '1.00;1000000000;2000000000;F R U;', call_args_list[0][0][0],
        )

        # Second write should contain the second solve
        self.assertIn(
            '1.00;3000000000;4000000000;B L D;DNF', call_args_list[1][0][0],
        )
