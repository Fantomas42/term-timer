"""Tests for the bt-info utility script."""
import logging
import unittest
from unittest.mock import patch

from cubing_algs.vcube import VCube

from term_timer.orientation import get_orientation_moves
from term_timer.scripts.bluetooth_info import linear_regression
from term_timer.scripts.bluetooth_info import show_state


class TestLinearRegression(unittest.TestCase):
    """Tests for the least squares regression of bt-info."""

    def test_perfect_line(self) -> None:
        """Test an exact affine relation."""
        slope, intercept = linear_regression(
            [1.0, 2.0, 3.0, 4.0],
            [3.0, 5.0, 7.0, 9.0],
        )

        self.assertAlmostEqual(slope, 2.0)
        self.assertAlmostEqual(intercept, 1.0)

    def test_noisy_line(self) -> None:
        """Test a relation with a residual on each point."""
        slope, intercept = linear_regression(
            [0.0, 1.0, 2.0, 3.0],
            [1.0, 3.0, 4.0, 6.0],
        )

        self.assertAlmostEqual(slope, 1.6)
        self.assertAlmostEqual(intercept, 1.1)

    def test_constant_x(self) -> None:
        """Test a null variance on x, where no slope can be computed."""
        slope, intercept = linear_regression(
            [2.0, 2.0, 2.0],
            [1.0, 5.0, 9.0],
        )

        self.assertAlmostEqual(slope, 1.0)
        self.assertAlmostEqual(intercept, 3.0)

    def test_empty(self) -> None:
        """Test that no data point gives the neutral line."""
        self.assertEqual(
            linear_regression([], []),
            (1.0, 0.0),
        )

    def test_single_point(self) -> None:
        """Test that a single point gives the neutral line through it."""
        self.assertEqual(
            linear_regression([2.0], [5.0]),
            (1.0, 3.0),
        )

    def test_mismatched_lengths(self) -> None:
        """Test that two series of different sizes are refused."""
        with self.assertRaises(ValueError):
            linear_regression([1.0, 2.0, 3.0], [1.0, 2.0])

        with self.assertRaises(ValueError):
            linear_regression([1.0, 2.0], [1.0, 2.0, 3.0])


class TestShowStateTiming(unittest.TestCase):
    """Tests for the rendering duration reported by show_state."""

    def setUp(self) -> None:
        """Build the orientation and the solved cube used by the renders."""
        self.orientation_moves = get_orientation_moves('UF')
        self.cube = VCube()

    def test_render_is_timed(self) -> None:
        """Test that a rendering reports its duration in the log."""
        with self.assertLogs(
                'term_timer.scripts.bluetooth_info',
                level=logging.DEBUG,
        ) as logs:
            show_state(
                ['R@100', 'U@200'],
                self.orientation_moves,
                self.cube,
            )

        records = [
            record for record in logs.records
            if record.getMessage().startswith('SHOW STATE:')
        ]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].levelno, logging.DEBUG)
        self.assertEqual(records[0].args[0], 2)  # type: ignore[index]

    def test_empty_render_is_timed(self) -> None:
        """Test that a rendering without any move is timed too."""
        with self.assertLogs(
                'term_timer.scripts.bluetooth_info',
                level=logging.DEBUG,
        ) as logs:
            show_state([], self.orientation_moves, self.cube)

        records = [
            record for record in logs.records
            if record.getMessage().startswith('SHOW STATE:')
        ]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].args[0], 0)  # type: ignore[index]

    def test_slow_render_is_warned(self) -> None:
        """Test that a rendering above the threshold is raised to warning."""
        with (
                patch(
                    'term_timer.scripts.bluetooth_info.'
                    'SHOW_STATE_SLOW_THRESHOLD',
                    -1.0,
                ),
                self.assertLogs(
                    'term_timer.scripts.bluetooth_info',
                    level=logging.DEBUG,
                ) as logs,
        ):
            show_state(
                ['R@100'],
                self.orientation_moves,
                self.cube,
            )

        records = [
            record for record in logs.records
            if record.getMessage().startswith('SHOW STATE:')
        ]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].levelno, logging.WARNING)
