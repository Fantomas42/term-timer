"""Tests for gyroscope."""
import json
import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.translate import translate_moves

from term_timer.bluetooth.gyroscope import RotationDetector
from term_timer.orientation import get_orientation_moves
from term_timer.transform import humanize_moves

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import GyroEventDict
    from term_timer.bluetooth.annotations import MoveEventDict


class TestMoveRotationDetector(unittest.TestCase):
    """Tests for RotationDetector move detection."""

    @staticmethod
    def reconstruct(orientation_faces: str, algo: str) -> Algorithm:
        """
        Reconstruct algorithm with orientation translation.

        Returns:
            Humanized algorithm with orientation applied.

        """
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
        """Check that rotation detection produces expected results."""
        path = Path(__file__).parent / 'replays' / source_path

        with path.open(encoding='utf-8') as f:
            events = json.load(f)

        moves = []
        rotation_detector = RotationDetector(75.0)

        for event in events:
            event_name = event['event']

            if event_name == 'move':
                event = cast('MoveEventDict', event)

                moves.append(event['move'])

            if event_name == 'gyro':
                event = cast('GyroEventDict', event)

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
    """Tests for various rotation scenarios with GAN Gen2 replays."""

    def test_m_m_prime_normal(self) -> None:
        """Test m m prime normal."""
        self.check_rotations(
            'gan_gen2/M-M-normal.json',
            "L' R x' L R' x",
            "M' M", 'DF',
        )

    def test_m_m_prime_slow(self) -> None:
        """Test m m prime slow."""
        self.check_rotations(
            'gan_gen2/M-M-slow.json',
            "L' R x' R' L x",
            "M' M", 'DF',
        )

    def test_triple_m_m_prime_fast(self) -> None:
        """Test triple m m prime fast."""
        self.check_rotations(
            'gan_gen2/triple-M-M-fast.json',
            "L' R x' L R' x R L' x' L R' x R L' x' L R' x",
            "M' M M' M M' M", 'DF',
        )

    def test_octuple_y_speed(self) -> None:
        """Test octuple y speed."""
        self.check_rotations(
            'gan_gen2/octuple-Y-speed.json',
            "y' y' y' y' y' y' y' y'",
            'y y y y y y y y', 'DF',
        )

    def test_alternate_4_y_normal(self) -> None:
        """Test alternate 4 y normal."""
        self.check_rotations(
            'gan_gen2/alternate-4-Y-normal.json',
            "y' y y y'",
            "y y' y' y", 'DF',
        )

    def test_quadruple_y_normal(self) -> None:
        """Test quadruple y normal."""
        self.check_rotations(
            'gan_gen2/quadruple-Y-normal.json',
            "y' y' y' y'",
            'y y y y', 'DF',
        )

    def test_triple_y_slow(self) -> None:
        """Test triple y slow."""
        self.check_rotations(
            'gan_gen2/triple-Y-slow.json',
            "y' y' y'",
            'y y y', 'DF',
        )

    def test_y_t_perm_y(self) -> None:
        """Test y t perm y."""
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",
            "y R U R' U' R' F R R U' R' U' R U R' F' y'", 'DF',
        )

    def test_y_t_perm_y_bis(self) -> None:
        """Test y t perm y bis."""
        self.check_rotations(
            'gan_gen2/Y-Tperm-Y-bis.json',
            "y' B D B' D' B' L B B D' B' D' B D B' L' y",
            "y R U R' U' R' F R R U' R' U' R U R' F' y'", 'DF',
        )


class TestSimpleRotation(TestMoveRotationDetector):
    """Tests for simple single rotation detection."""

    def test_y_uf(self) -> None:
        """Test y uf."""
        self.check_rotations(
            'gan_gen2/Y-UF.json',
            'y',
            'y', 'UF',
        )

    def test_y_df(self) -> None:
        """Test y df."""
        self.check_rotations(
            'gan_gen2/Y-DF.json',
            "y'",
            'y', 'DF',
        )

    def test_x_uf(self) -> None:
        """Test x uf."""
        self.check_rotations(
            'gan_gen2/X-UF.json',
            'x',
            'x', 'UF',
        )

    def test_x_df(self) -> None:
        """Test x df."""
        self.check_rotations(
            'gan_gen2/X-DF.json',
            "x'",
            'x', 'DF',
        )

    def test_z_uf(self) -> None:
        """Test z uf."""
        self.check_rotations(
            'gan_gen2/Z-UF.json',
            'z',
            'z', 'UF',
        )

    def test_z_df(self) -> None:
        """Test z df."""
        self.check_rotations(
            'gan_gen2/Z-DF.json',
            'z',
            'z', 'DF',
        )


class TestSimpleCancelRotation(TestMoveRotationDetector):
    """Tests for rotation cancellation detection."""

    def test_y_cancel_uf(self) -> None:
        """Test y cancel uf."""
        self.check_rotations(
            'gan_gen2/Y-cancel-UF.json',
            "y y'",
            "y y'", 'UF',
        )

    def test_y_cancel_df(self) -> None:
        """Test y cancel df."""
        self.check_rotations(
            'gan_gen2/Y-cancel-DF.json',
            "y' y",
            "y y'", 'DF',
        )

    def test_x_cancel_uf(self) -> None:
        """Test x cancel uf."""
        self.check_rotations(
            'gan_gen2/X-cancel-UF.json',
            "x x'",
            "x x'", 'UF',
        )

    def test_x_cancel_df(self) -> None:
        """Test x cancel df."""
        self.check_rotations(
            'gan_gen2/X-cancel-DF.json',
            "x' x",
            "x x'", 'DF',
        )

    def test_z_cancel_uf(self) -> None:
        """Test z cancel uf."""
        self.check_rotations(
            'gan_gen2/Z-cancel-UF.json',
            "z z'",
            "z z'", 'UF',
        )

    def test_z_cancel_df(self) -> None:
        """Test z cancel df."""
        self.check_rotations(
            'gan_gen2/Z-cancel-DF.json',
            "z z'",
            "z z'", 'DF',
        )


class TestSimpleQuadruleRotation(TestMoveRotationDetector):
    """Tests for quadruple rotation detection."""

    def test_quadruple_y_uf(self) -> None:
        """Test quadruple y uf."""
        self.check_rotations(
            'gan_gen2/4-Y-UF.json',
            'y y y y',
            'y y y y', 'UF',
        )

    def test_quadruple_x_uf(self) -> None:
        """Test quadruple x uf."""
        self.check_rotations(
            'gan_gen2/4-X-UF.json',
            'x x x x',
            'x x x x', 'UF',
        )

    def test_quadruple_z_uf(self) -> None:
        """Test quadruple z uf."""
        self.check_rotations(
            'gan_gen2/4-Z-UF.json',
            'z z z z',
            'z z z z', 'UF',
        )


class TestUyURotation(TestMoveRotationDetector):
    """Tests for U-rotation-U sequence detection."""

    def test_u_y_u_uf(self) -> None:
        """Test u y u uf."""
        self.check_rotations(
            'gan_gen2/U-Y-U-UF.json',
            'U y U',
            'U y U', 'UF',
        )

    def test_u_y_u_df(self) -> None:
        """Test u y u df."""
        self.check_rotations(
            'gan_gen2/U-Y-U-DF.json',
            "D y' D",
            'U y U', 'DF',
        )


class TestSliceCancelRotation(TestMoveRotationDetector):
    """Tests for slice move rotation cancellation."""

    def test_mp_m_uf(self) -> None:
        """Test mp m uf."""
        self.check_rotations(
            'gan_gen2/Mp-M-UF.json',
            "R' L x R L' x'",
            "M' M", 'UF',
        )

    def test_mp_m_df(self) -> None:
        """Test mp m df."""
        self.check_rotations(
            'gan_gen2/Mp-M-DF.json',
            "R L' x' L R' x",
            "M' M", 'DF',
        )

    def test_s_sp_uf(self) -> None:
        """Test s sp uf."""
        self.check_rotations(
            'gan_gen2/S-Sp-UF.json',
            "B F' z F B' z'",
            "S S'", 'UF',
        )

    def test_s_sp_df(self) -> None:
        """Test s sp df."""
        self.check_rotations(
            'gan_gen2/S-Sp-DF.json',
            "B F' z F B' z'",
            "S S'", 'DF',
        )

    def test_e_ep_uf(self) -> None:
        """Test e ep uf."""
        self.check_rotations(
            'gan_gen2/E-Ep-UF.json',
            "U D' y' D U' y",
            "E E'", 'UF',
        )

    def test_e_ep_df(self) -> None:
        """Test e ep df."""
        self.check_rotations(
            'gan_gen2/E-Ep-DF.json',
            "D U' y U D' y'",
            "E E'", 'DF',
        )


class TestSexyStableRotation(TestMoveRotationDetector):
    """Tests for sexy move with stable orientation."""

    def test_sexy_move_uf(self) -> None:
        """Test sexy move uf."""
        self.check_rotations(
            'gan_gen2/sexy-move-UF.json',
            "R U R' U'",
            "R U R' U'", 'UF',
        )

    def test_sexy_move_df(self) -> None:
        """Test sexy move df."""
        self.check_rotations(
            'gan_gen2/sexy-move-DF.json',
            "L D L' D'",
            "R U R' U'", 'DF',
        )


class TestSexyYSexyRotation(TestMoveRotationDetector):
    """Tests for sexy move with Y rotation between repetitions."""

    def test_sexy_y_sexy_move_uf(self) -> None:
        """Test sexy y sexy move uf."""
        self.check_rotations(
            'gan_gen2/sexy-Y-sexy-UF.json',
            "R U R' U' y B U B' U'",
            "R U R' d' R U R' U'", 'UF',
        )

    def test_sexy_y_sexy_move_df(self) -> None:
        """Test sexy y sexy move df."""
        self.check_rotations(
            'gan_gen2/sexy-Y-sexy-DF.json',
            "L D L' D' y' B D B' D'",
            "R U R' d' R U R' U'", 'DF',
        )


class TestSexyVariationRotation(TestMoveRotationDetector):
    """Tests for sexy move variations with rotations."""

    def test_sexy_y_r_df(self) -> None:
        """Test sexy y r df."""
        self.check_rotations(
            'gan_gen2/sexy-Y-R-DF.json',
            "L D L' D' y' B",
            "R U R' d' R", 'DF',
        )

    def test_x_x_sexy_y_df(self) -> None:
        """Test x x sexy y df."""
        self.check_rotations(
            'gan_gen2/X-Y-sexy-Y-DF.json',
            "x' y' D F D' F' y'",
            "x y R U R' d'", 'DF',
        )
