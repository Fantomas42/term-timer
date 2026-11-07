"""Tests for the stopwatch interface rendering."""
import asyncio
import io
import unittest
from unittest.mock import patch

from rich.console import Console as RichConsole
from rich.theme import Theme

from term_timer.formatter import format_time
from term_timer.interface.console import theme
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


class TestStopWatchTimerFrame(unittest.TestCase):
    """
    Tests for the frames redrawing the running time.

    The time is redrawn a hundred times per second: once the line is
    drawn, a frame only rewrites the time with codes Rich rendered once,
    instead of going through the whole Rich pipeline every 10ms.
    """

    def setUp(self) -> None:
        """Patch sound playback and capture the terminal for each test."""
        sound_patcher = patch(
            'term_timer.interface.sounds.sd', create=True,
        )
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

        self.output = io.StringIO()
        stdout_patcher = patch('sys.stdout', self.output)
        stdout_patcher.start()
        self.addCleanup(stdout_patcher.stop)

    def console(self, *, terminal: bool) -> RichConsole:
        """
        Build a console writing to the captured terminal.

        Returns:
            A console with the application theme.

        """
        return RichConsole(
            file=self.output,
            force_terminal=terminal,
            color_system='truecolor' if terminal else None,
            highlighter=None,
            theme=Theme(theme),
            width=120,
        )

    def build(self, *, terminal: bool = True) -> MottoStopWatch:
        """
        Build a stopwatch harness whose line is already drawn.

        Returns:
            The configured harness.

        """
        watch = MottoStopWatch()
        watch.console = self.console(terminal=terminal)
        watch.print_timer(6_410_000_000, 'timer_base')
        return watch

    def frame(self, watch: MottoStopWatch, elapsed: int, style: str) -> str:
        """
        Draw one more frame.

        Returns:
            What the frame wrote to the terminal.

        """
        start = len(self.output.getvalue())
        watch.print_timer(elapsed, style)
        return self.output.getvalue()[start:]

    def rich_time(self, elapsed: int, *, terminal: bool) -> str:
        """
        Render the time the way Rich prints it.

        Returns:
            The time with its style codes.

        """
        reference = self.console(terminal=terminal)
        reference.begin_capture()
        reference.print(
            f'[result]{ format_time(elapsed) }[/result]', end='',
        )
        return reference.end_capture()

    def test_frame_matches_the_rich_rendering(self) -> None:
        """A frame writes exactly what Rich would, after the rewind."""
        watch = self.build()

        self.assertEqual(
            self.frame(watch, 6_420_000_000, 'timer_base'),
            '\b' * 9 + self.rich_time(6_420_000_000, terminal=True),
        )

    def test_frame_skips_the_rich_pipeline(self) -> None:
        """Once its codes are rendered, a frame no longer prints via Rich."""
        watch = self.build()
        self.frame(watch, 6_415_000_000, 'timer_base')

        with patch.object(
                watch.console, 'print', wraps=watch.console.print,
        ) as rich_print:
            self.frame(watch, 6_420_000_000, 'timer_base')
            self.frame(watch, 6_430_000_000, 'timer_base')

        rich_print.assert_not_called()

    def test_style_change_redraws_through_rich(self) -> None:
        """A new time threshold redraws the whole line, motto included."""
        watch = self.build()

        output = self.frame(watch, 10_010_000_000, 'timer_10')

        self.assertIn('Go Go Go:', output)
        self.assertIn('00:10.010', output)

    def test_frame_without_colors_is_plain(self) -> None:
        """A console without colors gets the bare time, no style code."""
        watch = self.build(terminal=False)

        output = self.frame(watch, 6_420_000_000, 'timer_base')

        self.assertEqual(output, '\b' * 9 + '00:06.420')
        self.assertEqual(
            output, '\b' * 9 + self.rich_time(6_420_000_000, terminal=False),
        )
