"""Tests for the stopwatch interface rendering."""
import asyncio
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


class TransitionStopWatch(StopWatch, Terminal):
    """StopWatch harness writing down the transitions it asks for."""

    def __init__(self) -> None:
        """Prepare a harness with an empty transition log."""
        super().__init__()
        self.transitions: list[tuple[str, int | None]] = []

    def set_state(self, state: str, timestamp: int | None = None) -> None:
        """
        Record one state transition instead of publishing it.

        Args:
            state: The state being entered.
            timestamp: Instant of the transition, if the caller times it.

        """
        self.transitions.append((state, timestamp))


class TestStopWatchTransitions(unittest.TestCase):
    """Tests for the instants the stopwatch stamps its transitions with."""

    def setUp(self) -> None:
        """Patch sound playback for each test."""
        sound_patcher = patch(
            'term_timer.interface.sounds.sd', create=True,
        )
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    def run_stopwatch() -> TransitionStopWatch:
        """
        Run a stopwatch over an already completed solve.

        Returns:
            The harness, with its transitions recorded.

        """
        watch = TransitionStopWatch()
        watch.console = RichConsole(record=True, width=120)
        watch.start_time = 1_000_000_000
        watch.end_time = 9_410_000_000
        watch.solve_completed_event.set()

        with patch('sys.stdout', io.StringIO()):
            asyncio.run(watch.stopwatch())

        return watch

    def test_the_solving_transition_carries_the_start(self) -> None:
        """The solve starts at the instant the solve says it does."""
        watch = self.run_stopwatch()

        self.assertEqual(watch.transitions[0], ('solving', 1_000_000_000))

    def test_the_stop_transition_carries_the_end(self) -> None:
        """The stop is stamped with end_time, not with the display's."""
        watch = self.run_stopwatch()

        self.assertEqual(watch.transitions[-1], ('stop', 9_410_000_000))
