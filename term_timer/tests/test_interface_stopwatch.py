"""Tests for the stopwatch interface rendering."""
import io
import unittest
from unittest.mock import patch

from rich.console import Console as RichConsole

from term_timer.interface.stopwatch import StopWatch
from term_timer.interface.terminal import Terminal


class MottoStopWatch(StopWatch, Terminal):
    """Minimal StopWatch harness with terminal helpers for rendering tests."""


class TestStopWatchMotto(unittest.TestCase):
    """Tests for the motto opening the stopwatch lines."""

    def setUp(self) -> None:
        """Patch sound playback for each test."""
        sound_patcher = patch(
            'term_timer.interface.sounds.sd', create=True,
        )
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    def build() -> MottoStopWatch:
        """
        Build a stopwatch harness with a recording console.

        Returns:
            The configured harness.

        """
        watch = MottoStopWatch()
        watch.console = RichConsole(record=True, width=120)
        watch.step_width = 0
        return watch

    def test_step_renders_the_default_motto(self) -> None:
        """A completed step opens with the default motto."""
        watch = self.build()
        with patch('sys.stdout', io.StringIO()):
            watch.print_step('timer_base', 6_410_000_000, 'Cross', htm=6)

        self.assertIn('Go Go Go:', watch.console.export_text())

    def test_timer_renders_the_default_motto(self) -> None:
        """The running line opens with the default motto."""
        watch = self.build()
        with patch('sys.stdout', io.StringIO()):
            watch.print_timer(6_410_000_000, 'timer_base')

        self.assertIn('Go Go Go:', watch.console.export_text())

    def test_step_uses_the_overridden_motto(self) -> None:
        """A completed step follows the stopwatch motto."""
        watch = self.build()
        watch.motto = 'Chrono  :'
        with patch('sys.stdout', io.StringIO()):
            watch.print_step('timer_base', 6_410_000_000, 'Cross', htm=6)

        output = watch.console.export_text()
        self.assertIn('Chrono  :', output)
        self.assertNotIn('Go Go Go:', output)

    def test_timer_uses_the_overridden_motto(self) -> None:
        """The running line follows the stopwatch motto."""
        watch = self.build()
        watch.motto = 'Chrono  :'
        with patch('sys.stdout', io.StringIO()):
            watch.print_timer(6_410_000_000, 'timer_base')

        output = watch.console.export_text()
        self.assertIn('Chrono  :', output)
        self.assertNotIn('Go Go Go:', output)

    def test_motto_brackets_are_not_markup(self) -> None:
        """A motto containing brackets renders literally."""
        watch = self.build()
        watch.motto = '[GO]:'
        with patch('sys.stdout', io.StringIO()):
            watch.print_step('timer_base', 6_410_000_000, 'Cross', htm=6)
            watch.print_timer(6_410_000_000, 'timer_base')

        output = watch.console.export_text()
        self.assertEqual(output.count('[GO]:'), 2)
