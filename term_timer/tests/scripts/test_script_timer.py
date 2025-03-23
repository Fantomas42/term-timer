import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from term_timer.scripts.timer import main


class TestTimer(unittest.TestCase):
    @patch('term_timer.scripts.timer.StatisticsResume')
    @patch('term_timer.scripts.timer.load_solves')
    @patch('sys.argv', ['timer.py', '--stats'])
    def test_stats_command(self, mock_load_solves, mock_statistics):
        """Test the --stats command line option."""
        # Configure mocks
        mock_load_solves.return_value = []
        mock_stats_instance = MagicMock()
        mock_statistics.return_value = mock_stats_instance

        # Run the main function
        result = main()

        # Verify the function behavior
        mock_load_solves.assert_called_once_with(3)  # Default puzzle size is 3
        mock_statistics.assert_called_once_with(3, [])
        mock_stats_instance.resume.assert_called_once_with('Global ')
        self.assertEqual(result, 0)  # Verify return code

    @patch('term_timer.scripts.timer.Listing')
    @patch('term_timer.scripts.timer.load_solves')
    @patch('sys.argv', ['timer.py', '--list', '5'])
    def test_list_command(self, mock_load_solves, mock_listing):
        """Test the --list command line option."""
        # Configure mocks
        mock_load_solves.return_value = []
        mock_list_instance = MagicMock()
        mock_listing.return_value = mock_list_instance

        # Run the main function
        result = main()

        # Verify the function behavior
        mock_load_solves.assert_called_once_with(3)  # Default puzzle size is 3
        mock_listing.assert_called_once_with([])
        mock_list_instance.resume.assert_called_once_with(5)
        self.assertEqual(result, 0)  # Verify return code

    @patch('term_timer.scripts.timer.console.print')
    @patch('term_timer.scripts.timer.Timer')
    @patch('sys.argv', ['timer.py', '-f'])
    def test_free_play_mode(self, mock_timer, mock_console_print):
        """Test free play mode activation."""
        # Configure mocks
        timer_instance = MagicMock()
        timer_instance.start.return_value = False  # Exit after first iteration
        timer_instance.stack = []
        mock_timer.return_value = timer_instance

        # Run the main function
        result = main()

        # Verify the function behavior
        mock_console_print.assert_called_with(
            ':lock: Mode Free Play is active, solves will not be recorded !',
            style='warning',
        )
        mock_timer.assert_called_once_with(
            cube_size=3,
            iterations=0,
            easy_cross=False,
            free_play=True,
            show_cube=False,
            countdown=0,
            metronome=0,
            stack=[],
        )
        self.assertEqual(result, 0)  # Verify return code

    @patch('term_timer.scripts.timer.Timer')
    @patch('term_timer.scripts.timer.load_solves')
    @patch('term_timer.scripts.timer.save_solves')
    @patch('term_timer.scripts.timer.StatisticsResume')
    @patch('sys.argv', ['timer.py', '3'])  # 3 scrambles
    def test_normal_operation_with_scrambles(
        self, mock_stats, mock_save, mock_load, mock_timer,
    ):
        """Test normal operation with a specific number of scrambles."""
        # Configure mocks
        mock_load.return_value = []

        timer_instance = MagicMock()
        timer_instance.stack = ['solve1', 'solve2', 'solve3']
        # First 3 calls return True (completed solve), then False to exit
        timer_instance.start.side_effect = [True, True, True, False]
        mock_timer.return_value = timer_instance

        stats_instance = MagicMock()
        mock_stats.return_value = stats_instance

        # Run the main function
        result = main()

        # Verify the function behavior
        self.assertEqual(
            mock_timer.call_count, 3,
        )  # Should create 3 timer instances
        mock_save.assert_called_once_with(3, ['solve1', 'solve2', 'solve3'])
        mock_stats.assert_called_once_with(3, ['solve1', 'solve2', 'solve3'])
        stats_instance.resume.assert_called_once_with('Global ')
        self.assertEqual(result, 0)  # Verify return code

    @patch('term_timer.scripts.timer.seed')
    @patch('term_timer.scripts.timer.Timer')
    @patch('sys.argv', ['timer.py', '-r', '42'])
    def test_seed_option(self, mock_timer, mock_seed):
        """Test the seed option sets the random seed."""
        # Configure mocks
        timer_instance = MagicMock()
        timer_instance.start.return_value = False  # Exit after first iteration
        timer_instance.stack = []
        mock_timer.return_value = timer_instance

        # Run the main function
        result = main()

        # Verify the random seed was set
        mock_seed.assert_called_once_with('42')
        self.assertEqual(result, 0)  # Verify return code
