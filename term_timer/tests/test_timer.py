"""Tests for timer."""
import unittest
from random import Random

from term_timer.timer import Timer


class TestTimerModule(unittest.TestCase):
    """Tests for Timer class."""

    def test_initialization(self) -> None:
        """Test that Timer initializes with all required attributes."""
        timer = Timer(
            cube_size=3,
            iterations=0,
            easy_cross=False,
            scramble='',
            scrambles=[],
            session='default',
            free_play=True,
            show_cube=False,
            show_reconstruction=False,
            show_time_graph=False,
            show_tps_graph=False,
            show_recognition_graph=False,
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
