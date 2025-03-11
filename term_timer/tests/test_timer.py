import termios
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from term_timer.constants import SECOND
from term_timer.solve import Solve
from term_timer.timer import Timer


class TestTimer(unittest.TestCase):
    def setUp(self):
        self.stack = [
            Solve(1000000000, 1010000000, 'scramble1'),  # 10s
            Solve(2000000000, 2008000000, 'scramble2'),  # 8s
        ]

        self.timer = Timer(
            cube_size=3,
            easy_cross=False,
            iterations=0,
            free_play=False,
            show_cube=False,
            countdown=0,
            metronome=0,
            stack=self.stack,
        )

    def test_initialization(self):
        """Test timer initialization."""
        self.assertEqual(self.timer.cube_size, 3)
        self.assertEqual(self.timer.easy_cross, False)
        self.assertEqual(self.timer.iterations, 0)
        self.assertEqual(self.timer.free_play, False)
        self.assertEqual(self.timer.show_cube, False)
        self.assertEqual(self.timer.countdown, 0)
        self.assertEqual(self.timer.metronome, 0)
        self.assertEqual(self.timer.stack, self.stack)
        self.assertEqual(self.timer.start_time, 0)
        self.assertEqual(self.timer.end_time, 0)
        self.assertEqual(self.timer.elapsed_time, 0)

    @patch('term_timer.timer.select.select')
    @patch('term_timer.timer.termios.tcgetattr')
    @patch('term_timer.timer.termios.tcsetattr')
    @patch('term_timer.timer.tty.setcbreak')
    @patch('sys.stdin')
    def test_getch(
        self,
        mock_stdin,
        mock_setcbreak,
        mock_tcsetattr,
        mock_tcgetattr,
        mock_select,
    ):
        """Test getch method for keyboard input."""
        # Setup mocks
        mock_tcgetattr.return_value = 'old_settings'
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = 'a'
        mock_select.return_value = ([0], [], [])  # stdin ready for reading

        # Test with character input
        with patch('builtins.print') as mock_print:
            result = Timer.getch(timeout=0.1)

            # Verify the result
            self.assertEqual(result, 'a')

            # Verify that terminal settings were properly handled
            mock_tcgetattr.assert_called_once_with(0)
            mock_setcbreak.assert_called_once_with(0)
            mock_tcsetattr.assert_called_once_with(
                0, termios.TCSADRAIN, 'old_settings',
            )

            # Verify that the terminal was cleared
            mock_print.assert_called_once()

    def test_beep(self):  # noqa: PLR6301
        """Test beep method."""
        with patch('builtins.print') as mock_print:
            Timer.beep()
            mock_print.assert_called_once_with('\a', end='', flush=True)

    @patch('time.perf_counter_ns')
    @patch('time.sleep')
    def test_inspection(self, mock_sleep, mock_perf_counter):
        """Test inspection countdown."""
        # Setup mocks
        mock_perf_counter.return_value = 1000000000
        self.timer.countdown = 15

        # Mock Event.is_set to return False once then True to exit the loop
        self.timer.stop_event.is_set = MagicMock(side_effect=[False, True])

        # Mock beep method
        with (
            patch.object(self.timer, 'beep') as mock_beep,
            patch('term_timer.console.console.print') as mock_print,
        ):
            self.timer.inspection()

            # Verify beep was not called
            # since state wouldn't change in our mocked scenario
            mock_beep.assert_not_called()

            # Verify console.print was called to show inspection time
            mock_print.assert_called_once()
            mock_sleep.assert_called_once_with(0.01)

    @patch('time.perf_counter_ns')
    @patch('time.sleep')
    def test_stopwatch(self, mock_sleep, mock_perf_counter):
        """Test stopwatch functionality."""
        # Setup mocks
        start_time = 1000000000
        mock_perf_counter.return_value = start_time + (
            5 * SECOND
        )  # 5 seconds elapsed
        self.timer.start_time = start_time

        # Mock Event.is_set to return False once then True to exit the loop
        self.timer.stop_event.is_set = MagicMock(side_effect=[False, True])

        with patch('term_timer.console.console.print') as mock_print:
            self.timer.stopwatch()

            # Verify console.print was called to show elapsed time
            mock_print.assert_called_once()
            mock_sleep.assert_called_once_with(0.01)

    def test_start_line(self):
        """Test start_line method."""
        with patch('term_timer.console.console.print') as mock_print:
            Timer.start_line()

            # Verify console.print was called with the right message
            mock_print.assert_called_once()
            args, kwargs = mock_print.call_args
            self.assertIn('Press any key to start/stop', args[0])
            self.assertEqual(kwargs['style'], 'consign')

    def test_save_line(self):
        """Test save_line method."""
        with patch('term_timer.console.console.print') as mock_print:
            Timer.save_line()

            # Verify console.print was called with the right message
            mock_print.assert_called_once()
            args, kwargs = mock_print.call_args
            self.assertIn('Press any key to save', args[0])
            self.assertEqual(kwargs['style'], 'consign')

    def test_handle_solve(self):
        """Test handle_solve method which processes a new solve."""
        new_solve = Solve(3000000000, 3009000000, 'scramble3')  # 9s

        with patch('term_timer.console.console.print') as mock_print:
            self.timer.handle_solve(new_solve)

            # Verify the solve was added to the stack
            self.assertEqual(len(self.timer.stack), 3)
            self.assertEqual(self.timer.stack[-1], new_solve)

            # Verify console.print was called
            self.assertTrue(mock_print.call_count >= 1)

    @patch('term_timer.timer.scrambler')
    def test_start_quit_immediately(self, mock_scrambler):
        """Test start method when user quits immediately."""
        # Setup mocks
        mock_scrambler.return_value = (['F', 'R', 'U'], MagicMock())

        with (
            patch.object(self.timer, 'getch', return_value='q'),
            patch('term_timer.console.console.print'),
        ):
            # Start the timer but immediately quit
            result = self.timer.start()

            # Verify the result
            self.assertFalse(result)

            # Verify scrambler was called
            mock_scrambler.assert_called_once_with(
                cube_size=3, easy_cross=False, iterations=0,
            )
