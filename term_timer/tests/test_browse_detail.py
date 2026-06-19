"""Tests for the browse detail panel rendering."""
import unittest
from unittest.mock import Mock

from rich.text import Text

from term_timer.browse.panels.detail import DetailPanel
from term_timer.constants import SECOND
from term_timer.interface.console import console
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter


class TestRenderDetail(unittest.TestCase):
    """Tests for DetailPanel.render_detail."""

    def setUp(self) -> None:
        """Set up a reporter with sample solves and a stub log widget."""
        self.solves = [
            Solve(1700000000, 10 * SECOND, 'F R U', ''),
            Solve(1700000100, 15 * SECOND, 'R U F', ''),
        ]
        self.reporter = SolveStatisticsReporter(3, self.solves)

        self.log = Mock()
        self.log.content_size.width = 80

    def test_returns_styled_text(self) -> None:
        """render_detail returns a styled Text reproducing the detail."""
        result = DetailPanel.render_detail(self.reporter, 1, self.log)

        self.assertIsInstance(result, Text)
        self.assertIn('Detail for 3x3x3', result.plain)
        self.assertIn('Scramble', result.plain)
        self.assertIn('F R U', result.plain)
        # ANSI styling is preserved as Text spans.
        self.assertGreater(len(result.spans), 0)

    def test_falls_back_to_default_width(self) -> None:
        """A zero content width falls back to a usable default width."""
        self.log.content_size.width = 0

        result = DetailPanel.render_detail(self.reporter, 1, self.log)

        self.assertIsInstance(result, Text)
        self.assertIn('Detail for 3x3x3', result.plain)

    def test_invokes_detail_command(self) -> None:
        """render_detail delegates to the reporter's detail command."""
        reporter = Mock(spec=SolveStatisticsReporter)

        DetailPanel.render_detail(reporter, 3, self.log)

        reporter.detail.assert_called_once()
        call = reporter.detail.call_args
        self.assertEqual(call.args[0], 3)
        for flag in (
                'show_highlights', 'show_doctor', 'show_cube',
                'show_reconstruction', 'show_tps_graph', 'show_time_graph',
                'show_fluency_graph', 'show_recognition_graph',
        ):
            self.assertIn(flag, call.kwargs)

    def test_restores_console_state(self) -> None:
        """render_detail restores the shared console width and colors."""
        original_width = console.width
        original_color_system = console._color_system  # noqa: SLF001

        DetailPanel.render_detail(self.reporter, 1, self.log)

        self.assertEqual(console.width, original_width)
        self.assertEqual(
            console._color_system,  # noqa: SLF001
            original_color_system,
        )
