"""Tests for gyroscope."""

import json
import unittest
from pathlib import Path
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.translate import translate_moves

from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.bluetooth.types import GyroEventDict
from term_timer.bluetooth.types import MoveEventDict
from term_timer.orientation import get_orientation_moves
from term_timer.transform import humanize_moves


class TestMoveRotationDetector(unittest.TestCase):

    def reconstruct(self, orientation_faces: str, algo: str) -> Algorithm:
        orientation_moves = get_orientation_moves(orientation_faces)

        return humanize_moves(
            translate_moves(orientation_moves)(
                parse_moves(algo),
            ),
        )

    def check_rotations(self, source_path: str,
                        expected: str,
                        reconstructed: str,
                        orientation_faces: str) -> None:
        path = Path(__file__).parent / 'replays' / source_path

        with path.open(encoding='utf-8') as f:
            events = json.load(f)

        moves = []
        rotation_detector = RotationDetector(75.0)

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

        moves_str = ' '.join(moves)
        self.assertEqual(moves_str, expected)

        reconstruction = self.reconstruct(orientation_faces, moves_str)
        self.assertEqual(str(reconstruction), reconstructed)


class TestVarious(TestMoveRotationDetector):
    # Replays recorded in z2 (DF)

    def test_m_m_prime_normal(self) -> None:
        self.check_rotations(
            'gan_gen2/M-M-normal.json',
            "L' R x' L R' x",
            "M' M", 'DF',
        )

    def test_m_m_prime_slow(self) -> None:
        self.check_rotations(
            'gan_gen2/M-M-slow.json',
            "L' R x' R' L x",
            "M' M", 'DF',
        )

    def test_triple_m_m_prime_fast(self) -> None:
        self.check_rotations(
            'gan_gen2/triple-M-M-fast.json',
            "L' R x' L R' x R L' x' L R' x R L' x' L R' x",
            "M' M M' M M' M", 'DF',
        )

    def test_octuple_y_speed(self) -> None:
        self.check_rotations(
            'gan_gen2/octuple-Y-speed.json',
            "y' y' y' y' y' y' y' y'",
            'y y y y y y y y', 'DF',
        )

    def test_alternate_4_y_normal(self) -> None:
        self.check_rotations(
            'gan_gen2/alternate-4-Y-normal.json',
            "y' y y y'",
            "y y' y' y", 'DF',
        )

    def test_quadruple_y_normal(self) -> None:
        self.check_rotations(
            'gan_gen2/quadruple-Y-normal.json',
            "y' y' y' y'",
            'y y y y', 'DF',
        )

    def test_triple_y_slow(self) -> None:
        self.check_rotations(
            'gan_gen2/triple-Y-slow.json',
            "y' y' y'",
            'y y y', 'DF',
        )

    def test_y_t_perm_y(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",
            "y R U R' U' R' F R R U' R' U' R U R' F' y'", 'DF',
        )

    def test_y_t_perm_y_bis(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y-bis.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",
            "y R U R' U' R' F R R U' R' U' R U R' F' y'", 'DF',
        )


class TestSimpleRotation(TestMoveRotationDetector):

    def test_y_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-UF.json',
            'y',
            'y', 'UF',
        )

    def test_y_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-DF.json',
            "y'",
            'y', 'DF',
        )

    def test_x_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/X-UF.json',
            'x',
            'x', 'UF',
        )

    def test_x_df(self) -> None:
        self.check_rotations(
            'gan_gen2/X-DF.json',
            "x'",
            'x', 'DF',
        )

    def test_z_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-UF.json',
            'z',
            'z', 'UF',
        )

    def test_z_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-DF.json',
            'z',
            'z', 'DF',
        )


class TestSimpleCancelRotation(TestMoveRotationDetector):

    def test_y_cancel_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-cancel-UF.json',
            "y y'",
            "y y'", 'UF',
        )

    def test_y_cancel_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Y-cancel-DF.json',
            "y' y",
            "y y'", 'DF',
        )

    def test_x_cancel_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/X-cancel-UF.json',
            "x x'",
            "x x'", 'UF',
        )

    def test_x_cancel_df(self) -> None:
        self.check_rotations(
            'gan_gen2/X-cancel-DF.json',
            "x' x",
            "x x'", 'DF',
        )

    def test_z_cancel_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-cancel-UF.json',
            "z z'",
            "z z'", 'UF',
        )

    def test_z_cancel_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Z-cancel-DF.json',
            "z z'",
            "z z'", 'DF',
        )


class TestSimpleQuadruleRotation(TestMoveRotationDetector):

    def test_quadruple_y_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/4-Y-UF.json',
            'y y y y',
            'y y y y', 'UF',
        )

    def test_quadruple_x_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/4-X-UF.json',
            'x x x x',
            'x x x x', 'UF',
        )

    def test_quadruple_z_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/4-Z-UF.json',
            'z z z z',
            'z z z z', 'UF',
        )


class TestUyURotation(TestMoveRotationDetector):

    def test_u_y_u_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/U-Y-U-UF.json',
            'U y U',
            'U y U', 'UF',
        )

    def test_u_y_u_df(self) -> None:
        self.check_rotations(
            'gan_gen2/U-Y-U-DF.json',
            "D y' D",
            'U y U', 'DF',
        )


class TestSliceCancelRotation(TestMoveRotationDetector):

    def test_mp_m_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/Mp-M-UF.json',
            "R' L x R L' x'",
            "M' M", 'UF',
        )

    def test_mp_m_df(self) -> None:
        self.check_rotations(
            'gan_gen2/Mp-M-DF.json',
            "R L' x' L R' x",
            "M' M", 'DF',
        )

    def test_s_sp_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/S-Sp-UF.json',
            "B F' z F B' z'",
            "S S'", 'UF',
        )

    def test_s_sp_df(self) -> None:
        self.check_rotations(
            'gan_gen2/S-Sp-DF.json',
            "B F' z F B' z'",
            "S S'", 'DF',
        )

    def test_e_ep_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/E-Ep-UF.json',
            "U D' y' D U' y",
            "E E'", 'UF',
        )

    def test_e_ep_df(self) -> None:
        self.check_rotations(
            'gan_gen2/E-Ep-DF.json',
            "D U' y U D' y'",
            "E E'", 'DF',
        )


class TestSexyStableRotation(TestMoveRotationDetector):

    def test_sexy_move_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/sexy-move-UF.json',
            "R U R' U'",
            "R U R' U'", 'UF',
        )

    def test_sexy_move_df(self) -> None:
        self.check_rotations(
            'gan_gen2/sexy-move-DF.json',
            "L D L' D'",
            "R U R' U'", 'DF',
        )


class TestSexyYSexyRotation(TestMoveRotationDetector):

    def test_sexy_y_sexy_move_uf(self) -> None:
        self.check_rotations(
            'gan_gen2/sexy-Y-sexy-UF.json',
            "R U R' U' y B U B' U'",
            "R U R' d' R U R' U'", 'UF',
        )

    def test_sexy_y_sexy_move_df(self) -> None:
        self.check_rotations(
            'gan_gen2/sexy-Y-sexy-DF.json',
            "L D L' D' y' B D B' D'",
            "R U R' d' R U R' U'", 'DF',
        )


class TestSexyVariationRotation(TestMoveRotationDetector):

    def test_sexy_y_r_df(self) -> None:
        self.check_rotations(
            'gan_gen2/sexy-Y-R-DF.json',
            "L D L' D' y' B",
            "R U R' d' R", 'DF',
        )

    def test_x_x_sexy_y_df(self) -> None:
        self.check_rotations(
            'gan_gen2/X-Y-sexy-Y-DF.json',
            "x' y' D F D' F' y'",
            "x y R U R' d'", 'DF',
        )
