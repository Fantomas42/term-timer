"""Tests for timer."""
import unittest
from random import Random
from unittest.mock import patch

from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer

SECOND = 1_000_000_000


def build_timer(stack: list[Solve] | None = None) -> Timer:
    """
    Build a Timer instance with minimal configuration for tests.

    Returns:
        A free-play Timer ready for display tests.

    """
    return Timer(
        cube_size=3,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble='',
        scrambles=[],
        session='default',
        free_play=True,
        show_cube=False,
        show_highlights=False,
        show_doctor=False,
        show_reconstruction=False,
        show_time_graph=False,
        show_tps_graph=False,
        show_fluency_graph=False,
        show_recognition_graph=False,
        show_steps=False,
        countdown=0,
        metronome=0,
        orientation='DF',
        method='raw',
        stack=stack or [],
        rng=Random(),  # noqa: S311
    )


class TestTimerModule(unittest.TestCase):
    """Tests for Timer class."""

    def test_initialization(self) -> None:
        """Test that Timer initializes with all required attributes."""
        timer = Timer(
            cube_size=3,
            iterations=0,
            easy_cross=False,
            x_cross=False,
            edges_oriented=False,
            scramble='',
            scrambles=[],
            session='default',
            free_play=True,
            show_cube=False,
            show_highlights=True,
            show_doctor=True,
            show_reconstruction=False,
            show_time_graph=False,
            show_tps_graph=False,
            show_fluency_graph=False,
            show_recognition_graph=False,
            show_steps=False,
            countdown=0,
            metronome=0,
            orientation='DF',
            method='raw',
            stack=[],
            rng=Random(),  # noqa: S311
        )

        for key in (
                'moves',
                'bluetooth_queue',
                'bluetooth_cube',
                'bluetooth_interface',
                'bluetooth_consumer_ref',
                'bluetooth_hardware',
                'facelets_received_event',
                'hardware_received_event',
                'console',
                'cube_orientation_moves',
                'save_moves',
                'save_gesture',
                'save_gesture_event',
                'countdown',
                'inspection_completed_event',
                'scramble',
                'scrambled',
                'scramble_oriented',
                'counter',
                'facelets_scrambled',
                'scramble_completed_event',
                'state',
                'start_time',
                'end_time',
                'elapsed_time',
                'metronome',
                'solve_started_event',
                'solve_completed_event',
                'orientation_faces',
                'rng',
        ):
            self.assertTrue(hasattr(timer, key))


class TestProjectionLine(unittest.TestCase):
    """Tests for the next-solve average projection display."""

    @staticmethod
    def stats(seconds: list[float]) -> SolveStatisticsReporter:
        """
        Build a statistics reporter from a list of times in seconds.

        Returns:
            A reporter over the given solve times.

        """
        stack = [
            Solve(0, int(s * SECOND), '', cube_size=3)
            for s in seconds
        ]
        return SolveStatisticsReporter(3, stack)

    @staticmethod
    def render(stats: SolveStatisticsReporter) -> str:
        """
        Capture the console output of projection_line.

        Returns:
            The rendered projection text.

        """
        timer = build_timer()
        with timer.console.capture() as capture:
            timer.projection_line(stats)
        return capture.get()

    def test_disabled_when_no_projections(self) -> None:
        """No output is produced when STATS_AO_PROJECTIONS is empty."""
        stats = self.stats([12, 13, 11.5, 14, 12.5])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', []):
            self.assertEqual(self.render(stats), '')

    def test_shows_range_and_target(self) -> None:
        """A full window shows the BPA/WPA range and a reachable PB."""
        stats = self.stats([12, 13, 11.5, 14, 11])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', [5]):
            output = self.render(stats)
        self.assertIn('Estimate #2', output)
        self.assertIn('Ao5', output)
        self.assertIn('-', output)
        self.assertIn('PB', output)

    def test_preview_before_full_window_has_no_target(self) -> None:
        """One solve short of a window shows the range but no PB target."""
        stats = self.stats([12, 13, 11.5, 14])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', [5]):
            output = self.render(stats)
        self.assertIn('Ao5', output)
        self.assertNotIn('PB', output)

    def test_skips_average_without_enough_solves(self) -> None:
        """An average needing more solves than available is omitted."""
        stats = self.stats([12, 13, 11.5, 14, 12.5])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', [12]):
            self.assertEqual(self.render(stats), '')
