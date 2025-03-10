# ruff: noqa: ARG002, DTZ007
import unittest
from datetime import datetime
from unittest.mock import mock_open
from unittest.mock import patch

from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.scripts.cs_timer import date_to_ns
from term_timer.scripts.cs_timer import import_csv
from term_timer.scripts.cs_timer import time_to_ns


class TestCsTimer(unittest.TestCase):
    def test_date_to_ns(self):
        """Test conversion of date string to nanoseconds."""
        test_date = '2023-05-15 14:30:45'
        expected = int(
            datetime.strptime(test_date, '%Y-%m-%d %H:%M:%S').timestamp()
            * SECOND,
        )
        result = date_to_ns(test_date)
        self.assertEqual(result, expected)

    def test_time_to_ns_with_minutes(self):
        """Test conversion of time string with minutes to nanoseconds."""
        test_time = '1:23.45'
        # 1 minute 23.45 seconds = 83.45 seconds
        expected = int(83.45 * SECOND)
        result = time_to_ns(test_time)
        self.assertEqual(result, expected)

    def test_time_to_ns_without_minutes(self):
        """Test conversion of time string without minutes to nanoseconds."""
        test_time = '23.45'
        expected = int(23.45 * SECOND)
        result = time_to_ns(test_time)
        self.assertEqual(result, expected)

    def test_time_to_ns_seconds_only(self):
        """Test converting time with only seconds to nanoseconds."""
        time_str = '23.45'  # 23.45 seconds
        expected_seconds = 23 + 45 / 100
        expected_ns = int(expected_seconds * SECOND)

        result = time_to_ns(time_str)

        self.assertEqual(result, expected_ns)

    @patch('sys.argv', ['cs_timer.py', 'test_export.csv'])
    @patch(
        'pathlib.Path.open',
        new_callable=mock_open,
        read_data=(
            'No.;Time;Comment;Scramble;Date;Time(centis)\n'
            "1;12.34;Nice solve;R U R' U';2023-05-15 14:30:45;12.34\n"
            "2;DNF(15.67);Failed;F R F' R';2023-05-15 14:32:10;15.67\n"
            "3;16.78+;Plus two;L B L' B';2023-05-15 14:33:25;16.78\n"
        ),
    )
    @patch('builtins.print')
    def test_import_csv(self, mock_print, mock_open):
        """Test importing CSV data and formatting output."""
        import_csv()

        # Check the calls to print
        calls = mock_print.call_args_list

        # Parse the output to verify the format
        expected_outputs = [
            f"12.34;{ date_to_ns('2023-05-15 14:30:45') };"
            f"{ date_to_ns('2023-05-15 14:30:45') + time_to_ns('12.34') };"
            "R U R' U';;",
            f"15.67;{ date_to_ns('2023-05-15 14:32:10') };"
            f"{ date_to_ns('2023-05-15 14:32:10') + time_to_ns('15.67') };"
            f"F R F' R';{ DNF };",
            f"16.78;{ date_to_ns('2023-05-15 14:33:25') };"
            f"{ date_to_ns('2023-05-15 14:33:25') + time_to_ns('16.78') };"
            f"L B L' B';{ PLUS_TWO };",
        ]

        for i, call in enumerate(calls):
            self.assertIn(expected_outputs[i], call[0][0])

    @patch('sys.argv', ['cs_timer.py', 'test_file.csv'])
    @patch(
        'pathlib.Path.open',
        new_callable=mock_open,
        read_data=(
            'No.;Time;Comment;Scramble;Date;Time(centis)\n'
            "1;12.34;;F R U R' U' F';2023-01-01 12:00:00;12.34\n"
            "2;DNF(15.67);;R U R' U';2023-01-01 12:05:00;15.67\n"
            "3;14.56+;;L' B L B';2023-01-01 12:10:00;14.56\n"
        ),
    )
    @patch('builtins.print')
    def test_import_csv_full_states(self, mock_print, mock_open):
        """Test importing CS Timer CSV export file."""
        import_csv()

        # Verify that print was called for each solve with correct format
        self.assertEqual(mock_print.call_count, 3)

        # Check first call (normal solve)
        first_call_args = mock_print.call_args_list[0][0][0]
        self.assertIn('12340', first_call_args)
        self.assertIn("F R U R' U' F'", first_call_args)
        self.assertIn('', first_call_args)  # No flag

        # Check second call (DNF solve)
        second_call_args = mock_print.call_args_list[1][0][0]
        self.assertIn('15670', second_call_args)
        self.assertIn("R U R' U'", second_call_args)
        self.assertIn('DNF', second_call_args)

        # Check third call (+2 solve)
        third_call_args = mock_print.call_args_list[2][0][0]
        self.assertIn('14560', third_call_args)
        self.assertIn("L' B L B'", third_call_args)
        self.assertIn('+2', third_call_args)
