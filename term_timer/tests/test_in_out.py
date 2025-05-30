import unittest
from pathlib import Path
from unittest.mock import patch

from term_timer.in_out import load_solves


class TestInOut(unittest.TestCase):

    @patch('term_timer.in_out.SAVE_DIRECTORY', Path('/mock/path'))
    @patch('pathlib.Path.exists')
    def test_load_solves_non_existing_file(self, mock_exists):
        """Test loading solves from a non-existing file returns empty list."""
        mock_exists.return_value = False

        solves = load_solves(3, 'default')

        self.assertEqual(solves, [])
