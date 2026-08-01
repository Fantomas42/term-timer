"""Tests for the bluetooth interface helpers."""
import unittest
from datetime import datetime
from typing import TYPE_CHECKING

from term_timer.bluetooth.interface import format_event

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import DisconnectEventDict
    from term_timer.bluetooth.annotations import FaceletsEventDict
    from term_timer.bluetooth.annotations import GyroEventDict
    from term_timer.bluetooth.annotations import MoveEventDict

SOLVED = (
    'UUUUUUUUURRRRRRRRRFFFFFFFFF'
    'DDDDDDDDDLLLLLLLLLBBBBBBBBB'
)


class FormatEventTestCase(unittest.TestCase):
    """Tests for the rendering of a cube event in the log."""

    def setUp(self) -> None:
        """Take the wall clock shared by the events under test."""
        self.now = datetime.now()  # noqa: DTZ005

    def test_format_move(self) -> None:
        """A move says which one, and both clocks that timed it."""
        event: MoveEventDict = {
            'event': 'move',
            'clock': 1856234,
            'timestamp': self.now,
            'serial': 412,
            'local_timestamp': self.now,
            'cube_timestamp': 1856234.0,
            'face': 0,
            'direction': 1,
            'move': "R'",
        }

        self.assertEqual(
            format_event(event),
            'MOVE clock=1856234 serial=412 cube_timestamp=1856234.000'
            " face=0 direction=1 move=R'",
        )

    def test_format_facelets_elides_the_state(self) -> None:
        """The facelets string is kept, the state it repeats is not."""
        event: FaceletsEventDict = {
            'event': 'facelets',
            'clock': 12,
            'timestamp': self.now,
            'serial': 41,
            'facelets': SOLVED,
            'state': {
                'CP': list(range(8)),
                'CO': [0] * 8,
                'EP': list(range(12)),
                'EO': [0] * 12,
            },
        }

        self.assertEqual(
            format_event(event),
            f'FACELETS clock=12 serial=41 facelets={ SOLVED }',
        )

    def test_format_gyro_joins_the_nested_payloads(self) -> None:
        """A quaternion is rounded and flattened, not dumped as a dict."""
        event: GyroEventDict = {
            'event': 'gyro',
            'clock': 12,
            'timestamp': self.now,
            'quaternion': {'x': 0.1234, 'y': -0.98, 'z': 0.03, 'w': 0.45},
            'velocity': {'x': 1.0, 'y': 0.0, 'z': -2.5},
        }

        self.assertEqual(
            format_event(event),
            'GYRO clock=12 quaternion=0.123,-0.980,0.030,0.450'
            ' velocity=1.000,0.000,-2.500',
        )

    def test_format_battery(self) -> None:
        """An event nobody wrote a special case for is rendered anyway."""
        event: BatteryEventDict = {
            'event': 'battery',
            'clock': 12,
            'timestamp': self.now,
            'level': 87,
            'charging_state': 0,
        }

        self.assertEqual(
            format_event(event),
            'BATTERY clock=12 level=87 charging_state=0',
        )

    def test_format_disconnect(self) -> None:
        """An event carrying nothing leaves no trailing space behind."""
        event: DisconnectEventDict = {
            'event': 'disconnect',
            'clock': 12,
            'timestamp': self.now,
        }

        self.assertEqual(format_event(event), 'DISCONNECT clock=12')
