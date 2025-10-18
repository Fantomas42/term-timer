import json
import unittest
from pathlib import Path
from typing import cast

from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.bluetooth.types import GyroEventDict
from term_timer.bluetooth.types import MoveEventDict


class TestMoveRotationDetector(unittest.TestCase):
    # Replays recorded in z2 (DF)

    def check_rotations(self, source_path: str, expected: str) -> None:
        path = Path(__file__).parent / 'replays' / source_path

        with path.open(encoding='utf-8') as f:
            events = json.load(f)

        moves = []
        rotation_detector = RotationDetector()

        for event in events:
            event_name = event['event']

            if event_name == 'move':
                event = cast(MoveEventDict, event)

                moves.append(event['move'])

            if event_name == 'gyro':
                event = cast(GyroEventDict, event)

                rotation_result = rotation_detector.process_gyro_event(
                    event['quaternion'],
                )

                if rotation_result:
                    moves.append(rotation_result['rotation'])

        self.assertEqual(
            ' '.join(moves),
            expected,
        )


class TestVarious(TestMoveRotationDetector):
    # Replays recorded in z2 (DF)

    def test_m_m_prime_normal(self) -> None:
        self.check_rotations(
            'gan_gen2/M-M-normal.json',
            "L' R x' L R' x",
        )

    def test_m_m_prime_slow(self) -> None:
        self.check_rotations(
            'gan_gen2/M-M-slow.json',
            "L' R x' R' L x",
        )

    def test_triple_m_m_prime_fast(self) -> None:
        self.check_rotations(
            'gan_gen2/triple-M-M-fast.json',
            "L' R x' L R' x R L' x' L R' x R L' x' L R' x",
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
            "y' y' y'",
        )

    def test_y_t_perm_y(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",
        )

    def test_y_t_perm_y_bis(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y-bis.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",
        )


class TestSimpleRotation(TestMoveRotationDetector):

    def test_y_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-UF.json',
            'y',
        )

    def test_y_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-DF.json',
            "y'",
        )

    def test_x_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/X-UF.json',
            'x',
        )

    def test_x_df(self) -> None:
        self.check_rotations(
            'gan_gen2/X-DF.json',
            "x'",
        )

    def test_z_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-UF.json',
            'z',
        )

    def test_z_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-DF.json',
            'z',
        )


class TestSimpleCancelRotation(TestMoveRotationDetector):

    def test_y_cancel_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-cancel-UF.json',
            "y y'",
        )

    def test_y_cancel_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-cancel-DF.json',
            "y' y",
        )

    def test_x_cancel_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/X-cancel-UF.json',
            "x x'",
        )

    def test_x_cancel_df(self) -> None:
        self.check_rotations(
            'gan_gen2/X-cancel-DF.json',
            "x' x",
        )

    def test_z_cancel_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-cancel-UF.json',
            "z z'",
        )

    def test_z_cancel_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-cancel-DF.json',
            "z z'",
        )


class TestSimpleQuadruleRotation(TestMoveRotationDetector):

    def test_quadruple_y_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/4-Y-UF.json',
            'y y y y',
        )

    def test_quadruple_x_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/4-X-UF.json',
            'x x x x',
        )

    def test_quadruple_z_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/4-Z-UF.json',
            'z z z z',
        )


class TestUyURotation(TestMoveRotationDetector):

    def test_u_y_u_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/U-Y-U-UF.json',
            'U y U',
        )

    def test_u_y_u_df(self) -> None:
        self.check_rotations(
            'gan_gen2/U-Y-U-DF.json',
            "D y' D",
        )


class TestSliceCancelRotation(TestMoveRotationDetector):

    def test_mp_m_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Mp-M-UF.json',
            "R' L x R L' x'",
        )

    def test_mp_m_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Mp-M-DF.json',
            "R L' x' L R' x",
        )

    def test_s_sp_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/S-Sp-UF.json',
            "B F' z F B' z'",
        )

    def test_s_sp_df(self) -> None:
        self.check_rotations(
            'gan_gen2/S-Sp-DF.json',
            "B F' z F B' z'",
        )

    def test_e_ep_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/E-Ep-UF.json',
            "U D' y' D U' y",
        )

    def test_e_ep_df(self) -> None:
        self.check_rotations(
            'gan_gen2/E-Ep-DF.json',
            "D U' y U D' y'",
        )


class TestSexyStableRotation(TestMoveRotationDetector):

    def test_sexy_move_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/sexy-move-UF.json',
            "R U R' U'",
        )

    def test_sexy_move_df(self) -> None:
        self.check_rotations(
            'gan_gen2/sexy-move-DF.json',
            "L D L' D'",
        )
