"""Tests for case encoder functions."""
import unittest

from cubing_algs.masks import F2L_FR_MASK
from cubing_algs.masks import FULL_MASK
from cubing_algs.solved_state import SOLVED_FACELETS_3x3x3

from term_timer.methods.masks.encoders import CACHE_SIZE_LIMIT
from term_timer.methods.masks.encoders import MASK_CACHE
from term_timer.methods.masks.encoders import f2l_case_encoder
from term_timer.methods.masks.encoders import facelets_masked
from term_timer.methods.masks.encoders import oll_case_encoder
from term_timer.methods.masks.encoders import pll_case_encoder
from term_timer.methods.masks.encoders import state_masked


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


class TestBinaryMasks(unittest.TestCase):
    """Tests for binary mask operations on cube states."""

    def test_facelets_masked_basic(self) -> None:
        """Test facelets masked basic."""
        facelets = 'ABCD'
        mask = '1010'
        expected = 'A-C-'
        self.assertEqual(facelets_masked(facelets, mask), expected)

    def test_facelets_masked_all_ones(self) -> None:
        """Test facelets masked all ones."""
        facelets = 'ABCD'
        mask = '1111'
        expected = 'ABCD'
        self.assertEqual(facelets_masked(facelets, mask), expected)

    def test_facelets_masked_all_zeros(self) -> None:
        """Test facelets masked all zeros."""
        facelets = 'ABCD'
        mask = '0000'
        expected = '----'
        self.assertEqual(facelets_masked(facelets, mask), expected)

    def test_facelets_masked_empty(self) -> None:
        """Test facelets masked empty."""
        facelets = ''
        mask = ''
        expected = ''
        self.assertEqual(facelets_masked(facelets, mask), expected)

    def test_facelets_masked_single_char(self) -> None:
        """Test facelets masked single char."""
        facelets = 'X'
        mask = '1'
        expected = 'X'
        self.assertEqual(facelets_masked(facelets, mask), expected)

        facelets = 'X'
        mask = '0'
        expected = '-'
        self.assertEqual(facelets_masked(facelets, mask), expected)

    def test_facelets_masked_real_cube_pattern(self) -> None:
        """Test facelets masked real cube pattern."""
        facelets = SOLVED_FACELETS_3x3x3[:9]
        mask = '101010101'
        expected = 'U-U-U-U-U'
        self.assertEqual(facelets_masked(facelets, mask), expected)

    def test_state_masked_basic(self) -> None:
        """Test state masked basic."""
        mask = FULL_MASK
        result = state_masked(SOLVED_FACELETS_3x3x3, mask)

        self.assertEqual(result, SOLVED_FACELETS_3x3x3)

    def test_state_masked_all_zeros(self) -> None:
        """Test state masked all zeros."""
        mask = '0' * 54
        result = state_masked(SOLVED_FACELETS_3x3x3, mask)

        self.assertEqual(result, '-' * 54)

    def test_state_masked_partial(self) -> None:
        """Test state masked partial."""
        mask = '1' * 9 + '0' * 45
        result = state_masked(SOLVED_FACELETS_3x3x3, mask)

        self.assertEqual(
            result,
            'UUUUUUUUU---------------------------------------------',
        )

    def test_state_masked_different_state(self) -> None:
        """Test state masked different state."""
        scrambled_state = (
            'LUULUUFFFLBBRRRRRRUUUFFDFFDRRBDDBDDBFFRLLDLLDLLDUBBUBB'
        )
        mask = '1' * 27 + '0' * 27
        result = state_masked(scrambled_state, mask)

        self.assertEqual(
            result,
            '-UU-UUFFF---RRRRRRUUUFF-FF-RR-------FFR---------U--U--',
        )

    def test_facelets_masked_cache_hit(self) -> None:
        """Test cache hit path in optimized facelets_masked."""
        MASK_CACHE.clear()

        facelets = 'ABCD'
        mask = '1010'

        # First call - cache miss
        result1 = facelets_masked(facelets, mask)
        self.assertEqual(result1, 'A-C-')
        self.assertIn(mask, MASK_CACHE)

        # Second call - cache hit (covers lines 74-75)
        result2 = facelets_masked(facelets, mask)
        self.assertEqual(result2, 'A-C-')
        self.assertEqual(result1, result2)

    def test_facelets_masked_cache_eviction(self) -> None:
        """Test cache eviction when size limit is reached."""
        MASK_CACHE.clear()

        # Directly manipulate cache to test eviction by filling it beyond limit
        # This allows us to test the eviction logic paths (lines 86-88)

        # Fill cache manually to exactly the limit
        for i in range(CACHE_SIZE_LIMIT):
            # Create unique keys and dummy values
            key_prefix = f'test_mask_{i:04d}'
            mask_key = key_prefix + '0' * (54 - len(key_prefix))
            MASK_CACHE[mask_key] = tuple(bool(j % 2) for j in range(54))

        # Verify cache is at limit
        self.assertEqual(len(MASK_CACHE), CACHE_SIZE_LIMIT)

        # Now call facelets_masked with a new unique mask to trigger eviction
        test_facelets = SOLVED_FACELETS_3x3x3
        trigger_mask = '1' + '0' * 53  # Unique mask not in cache

        result = facelets_masked(test_facelets, trigger_mask)

        # Verify eviction occurred - cache should be reduced and new mask added
        expected_size = CACHE_SIZE_LIMIT // 2 + 1
        self.assertEqual(len(MASK_CACHE), expected_size)

        # The triggering mask should be in the cache
        self.assertIn(trigger_mask, MASK_CACHE)

        # Verify the result is correct
        expected_result = 'U' + '-' * 53
        self.assertEqual(result, expected_result)

    def test_facelets_masked_cache_behavior_with_repeated_patterns(
        self,
    ) -> None:
        """Test cache behavior with realistic repeated mask usage."""
        MASK_CACHE.clear()

        # Test with cube-sized strings and common patterns
        facelets = SOLVED_FACELETS_3x3x3
        common_masks = [FULL_MASK, '0' * 54, '1' * 27 + '0' * 27]

        # First round - populate cache
        results1 = [facelets_masked(facelets, mask) for mask in common_masks]

        # Verify all masks are cached
        for mask in common_masks:
            self.assertIn(mask, MASK_CACHE)

        # Second round - should hit cache
        results2 = [facelets_masked(facelets, mask) for mask in common_masks]

        # Results should be identical
        self.assertEqual(results1, results2)
