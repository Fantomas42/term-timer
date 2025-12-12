"""Tests for case encoder functions."""
import unittest

from cubing_algs.masks import F2L_FR_MASK

from term_timer.methods.masks.encoders import f2l_case_encoder
from term_timer.methods.masks.encoders import oll_case_encoder
from term_timer.methods.masks.encoders import pll_case_encoder


class OLLEncoderTestCase(unittest.TestCase):
    """Test cases for OLL encoder."""

    def test_oll_encoder_solved_state(self) -> None:
        """Test OLL encoder with solved cube state."""
        solved = (
            'UUUUUUUUU'
            'RRRRRRRRR'
            'FFFFFFFFF'
            'DDDDDDDDD'
            'LLLLLLLLL'
            'BBBBBBBBB'
        )
        result = oll_case_encoder(solved)

        self.assertEqual(len(result), 21)
        # For solved cube, not all positions match U center
        self.assertTrue(all(c in '01' for c in result))

    def test_oll_encoder_all_same_as_center(self) -> None:
        """Test OLL encoder when all positions match U center."""
        # Create state where all OLL positions are U color
        # OLL positions: [15:18] + [24:36] + [42:45] + [51:54]
        all_u = (
            'UUUUUUUUU'  # U face: 0-8
            'RRRRRR'
             'UUU'      # R face: 15-17
            'FFFFFF'
             'UUU'      # F face: 24-26
            'UUUUUUUUU'  # D face: 27-35
            'LLLLLL'
             'UUU'      # L face: 42-44
            'BBBBBB'
             'UUU'      # B face: 51-53
        )
        result = oll_case_encoder(all_u)

        self.assertEqual(len(result), 21)
        self.assertEqual(result, '1' * 21)

    def test_oll_encoder_mixed_pattern(self) -> None:
        """Test OLL encoder with mixed OLL pattern."""
        mixed = (
            'UUUUUUUUU'
            'RRRRRRRRD'
            'FFFFFFUUU'
            'DDDDDDDDD'
            'LLLLLLLLL'
            'BBBBBBFFF'
        )
        result = oll_case_encoder(mixed)

        self.assertEqual(len(result), 21)
        self.assertTrue(all(c in '01' for c in result))

    def test_oll_encoder_length(self) -> None:
        """Test OLL encoder always returns 21 characters."""
        test_states = [
            'U' * 54,
            'R' * 54,
            (
                'UUUUUUUUU'
                'RRRRRRRRR'
                'FFFFFFFFF'
                'DDDDDDDDD'
                'LLLLLLLLL'
                'BBBBBBBBB'
            ),
        ]

        for state in test_states:
            result = oll_case_encoder(state)
            self.assertEqual(len(result), 21)


class PLLEncoderTestCase(unittest.TestCase):
    """Test cases for PLL encoder."""

    def test_pll_encoder_solved_state(self) -> None:
        """Test PLL encoder with solved cube state."""
        solved = (
            'UUUUUUUUU'
            'RRRRRRRRR'
            'FFFFFFFFF'
            'DDDDDDDDD'
            'LLLLLLLLL'
            'BBBBBBBBB'
        )
        result = pll_case_encoder(solved)

        # PLL fingerprint is 12 chars, not 21
        self.assertEqual(len(result), 12)
        self.assertEqual(result, '000111222333')

    def test_pll_encoder_less_than_four_colors(self) -> None:
        """Test PLL encoder with less than 4 colors (no early break)."""
        # Positions: [15:18] + [24:27] + [42:45] + [51:54]
        # Use only 2 colors to avoid early break
        two_colors = (
            'UUUUUUUUU'
            'RRRRRR'
             'RRR'  # 15-17: RRR
            'FFFFFF'
             'FFF'  # 24-26: FFF
            'DDDDDDDDD'
            'LLLLLL'
             'RRR'  # 42-44: RRR
            'BBBBBB'
             'FFF'  # 51-53: FFF
        )
        result = pll_case_encoder(two_colors)

        self.assertEqual(len(result), 12)
        self.assertEqual(result, '000111000111')

    def test_pll_encoder_all_same_color(self) -> None:
        """Test PLL encoder with all same color in fingerprint positions."""
        all_r = (
            'UUUUUUUUU'
            'RRRRRR'
             'RRR'  # 15-17: RRR
            'FFFFFF'
             'RRR'  # 24-26: RRR
            'DDDDDDDDD'
            'LLLLLL'
             'RRR'  # 42-44: RRR
            'BBBBBB'
             'RRR'  # 51-53: RRR
        )
        result = pll_case_encoder(all_r)

        self.assertEqual(len(result), 12)
        self.assertEqual(result, '0' * 12)

    def test_pll_encoder_length(self) -> None:
        """Test PLL encoder always returns 12 characters."""
        test_states = [
            'U' * 54,
            'R' * 54,
            (
                'UUUUUUUUU'
                'RRRRRRRRR'
                'FFFFFFFFF'
                'DDDDDDDDD'
                'LLLLLLLLL'
                'BBBBBBBBB'
            ),
        ]

        for state in test_states:
            result = pll_case_encoder(state)
            self.assertEqual(len(result), 12)

    def test_pll_encoder_numeric_output(self) -> None:
        """Test PLL encoder returns only numeric characters."""
        solved = (
            'UUUUUUUUU'
            'RRRRRRRRR'
            'FFFFFFFFF'
            'DDDDDDDDD'
            'LLLLLLLLL'
            'BBBBBBBBB'
        )
        result = pll_case_encoder(solved)

        self.assertTrue(all(c.isdigit() for c in result))


class F2LEncoderTestCase(unittest.TestCase):
    """Test cases for F2L encoder factory."""

    def test_f2l_encoder_returns_callable(self) -> None:
        """Test F2L encoder factory returns a callable."""
        mask = F2L_FR_MASK
        encoder = f2l_case_encoder(mask)

        self.assertTrue(callable(encoder))

    def test_f2l_encoder_solved_state(self) -> None:
        """Test F2L encoder with solved cube state."""
        mask = F2L_FR_MASK
        encoder = f2l_case_encoder(mask)

        solved = (
            'UUUUUUUUU'
            'RRRRRRRRR'
            'FFFFFFFFF'
            'DDDDDDDDD'
            'LLLLLLLLL'
            'BBBBBBBBB'
        )
        result = encoder(solved)

        self.assertEqual(len(result), 54)

    def test_f2l_encoder_length(self) -> None:
        """Test F2L encoder always returns 54 characters."""
        mask = F2L_FR_MASK
        encoder = f2l_case_encoder(mask)

        test_states = [
            (
                'UUUUUUUUU'
                'RRRRRRRRR'
                'FFFFFFFFF'
                'DDDDDDDDD'
                'LLLLLLLLL'
                'BBBBBBBBB'
            ),
        ]

        for state in test_states:
            result = encoder(state)
            self.assertEqual(len(result), 54)

    def test_f2l_encoder_numeric_output(self) -> None:
        """Test F2L encoder returns only numeric characters."""
        mask = F2L_FR_MASK
        encoder = f2l_case_encoder(mask)

        solved = (
            'UUUUUUUUU'
            'RRRRRRRRR'
            'FFFFFFFFF'
            'DDDDDDDDD'
            'LLLLLLLLL'
            'BBBBBBBBB'
        )
        result = encoder(solved)

        self.assertTrue(all(c.isdigit() for c in result))
