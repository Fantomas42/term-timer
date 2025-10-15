import json
import unittest
from pathlib import Path
from typing import cast

from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.bluetooth.types import GyroEventDict
from term_timer.bluetooth.types import MoveEventDict


class TestMoveRotationDetector(unittest.TestCase):
    use_velocity = False

    def check_rotations(self, source_path: str, expected: str) -> None:
        path = Path(__file__).parent / 'replays' / source_path

        with path.open(encoding='utf-8') as f:
            events = json.load(f)

        moves = []
        rotation_detector = RotationDetector()

        for event in events:
            event_name = event['event']
            timestamp = cast(float, event['timestamp'])

            if event_name == 'move':
                event = cast(MoveEventDict, event)

                moves.append(event['move'])

            if event_name == 'gyro':
                event = cast(GyroEventDict, event)

                velocity = event.get('velocity')

                if self.use_velocity and velocity:
                    rotation_result = (
                        rotation_detector.process_gyro_event_with_velocity(
                            event['quaternion'],
                            velocity,
                            timestamp,
                        )
                    )
                else:
                    rotation_result = rotation_detector.process_gyro_event(
                        event['quaternion'],
                        timestamp,
                    )

                if rotation_result:
                    moves.append(rotation_result['rotation'])

        self.assertEqual(
            ' '.join(moves),
            expected,
        )


class TestMoveRotationsNoVelocity(TestMoveRotationDetector):
    use_velocity = False

    def test_m_m_prime_normal(self) -> None:
        self.check_rotations(
            'gan_gen2/M-M-normal.json',
            "L' R x' L R' x",
        )

    def test_m_m_prime_slow(self) -> None:
        self.check_rotations(
            'gan_gen2/M-M-slow.json',
            "L' R z R' L z'",  # TODO(me): fix + why z ?
        )

    def test_triple_m_m_prime_fast(self) -> None:
        self.check_rotations(
            'gan_gen2/triple-M-M-fast.json',
            "L' R z L R' z' R L' z L R' z' R L' z L R' z'",  # TODO(me): why z ?
        )

    def test_octuple_y_speed(self) -> None:
        self.check_rotations(
            'gan_gen2/octuple-Y-speed.json',
            "y' y' y' y' y' y' y' y'",
        )

    def test_alternate_4_y_normal(self) -> None:
        self.check_rotations(
            'gan_gen2/alternate-4-Y-normal.json',
            "y' y y y'",
        )

    def test_quadruple_y_normal(self) -> None:
        self.check_rotations(
            'gan_gen2/quadruple-Y-normal.json',
            "y' y' y' y'",
        )

    def test_triple_y_slow(self) -> None:
        self.check_rotations(
            'gan_gen2/triple-Y-slow.json',
            "y' y' y'",  # TODO(me): fix
        )

    def test_y_t_perm_y(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",  # TODO(me): fix
        )

    def test_y_t_perm_y_bis(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y-bis.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",  # TODO(me): fix
        )
