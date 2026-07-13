"""Tests for bluetooth salt."""
import unittest

from term_timer.bluetooth.salt import get_salt


class TestGetSalt(unittest.TestCase):  # noqa: PLR0904
    """Test cases for get_salt function."""

    def test_valid_mac_address_standard_format(self) -> None:
        """Test with standard MAC address format."""
        mac = '01:23:45:67:89:AB'
        result = get_salt(mac)

        # Should return bytearray with reversed order
        expected = bytearray([0xAB, 0x89, 0x67, 0x45, 0x23, 0x01])
        self.assertEqual(result, expected)
        self.assertIsInstance(result, bytearray)
        self.assertEqual(len(result), 6)

    def test_valid_mac_address_lowercase(self) -> None:
        """Test with lowercase MAC address."""
        mac = 'aa:bb:cc:dd:ee:ff'
        result = get_salt(mac)

        expected = bytearray([0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])
        self.assertEqual(result, expected)

    def test_valid_mac_address_uppercase(self) -> None:
        """Test with uppercase MAC address."""
        mac = 'AA:BB:CC:DD:EE:FF'
        result = get_salt(mac)

        expected = bytearray([0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])
        self.assertEqual(result, expected)

    def test_valid_mac_address_mixed_case(self) -> None:
        """Test with mixed case MAC address."""
        mac = 'aA:Bb:Cc:Dd:Ee:Ff'
        result = get_salt(mac)

        expected = bytearray([0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])
        self.assertEqual(result, expected)

    def test_mac_address_with_zeros(self) -> None:
        """Test MAC address containing zeros."""
        mac = '00:11:22:33:44:55'
        result = get_salt(mac)

        expected = bytearray([0x55, 0x44, 0x33, 0x22, 0x11, 0x00])
        self.assertEqual(result, expected)

    def test_mac_address_all_zeros(self) -> None:
        """Test MAC address with all zeros."""
        mac = '00:00:00:00:00:00'
        result = get_salt(mac)

        expected = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.assertEqual(result, expected)

    def test_mac_address_all_ff(self) -> None:
        """Test MAC address with all FF."""
        mac = 'FF:FF:FF:FF:FF:FF'
        result = get_salt(mac)

        expected = bytearray([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        self.assertEqual(result, expected)

    def test_mac_address_boundary_values(self) -> None:
        """Test MAC address with boundary hex values."""
        mac = '0F:F0:A5:5A:C3:3C'
        result = get_salt(mac)

        expected = bytearray([0x3C, 0xC3, 0x5A, 0xA5, 0xF0, 0x0F])
        self.assertEqual(result, expected)

    def test_salt_order_reversal(self) -> None:
        """Test that the salt array is properly reversed."""
        mac = '11:22:33:44:55:66'
        result = get_salt(mac)

        # Original order: [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]
        # Reversed order: [0x66, 0x55, 0x44, 0x33, 0x22, 0x11]
        expected = bytearray([0x66, 0x55, 0x44, 0x33, 0x22, 0x11])
        self.assertEqual(result, expected)

        # Verify it's actually reversed
        original_order = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]
        self.assertEqual(list(result), list(reversed(original_order)))

    def test_mac_too_few_parts(self) -> None:
        """Test MAC address with too few parts is rejected."""
        mac = '01:23:45:67:89'  # Only 5 parts instead of 6
        with self.assertRaises(ValueError):
            get_salt(mac)

    def test_mac_too_many_parts(self) -> None:
        """Test MAC address with too many parts is rejected."""
        mac = '01:23:45:67:89:AB:CD'  # 7 parts instead of 6
        with self.assertRaises(ValueError):
            get_salt(mac)

    def test_mac_octet_out_of_range(self) -> None:
        """Test MAC address with an octet above 0xFF is rejected."""
        mac = '01:23:45:67:89:1FF'  # 0x1FF is out of byte range
        with self.assertRaises(ValueError):
            get_salt(mac)

    def test_invalid_mac_non_hex_characters(self) -> None:
        """Test MAC address with non-hex characters."""
        invalid_macs = [
            '01:23:45:67:89:XY',  # XY is not hex
            '01:23:45:67:89:GH',  # GH is not hex
            'ZZ:23:45:67:89:AB',  # ZZ is not hex
        ]

        for mac in invalid_macs:
            with self.assertRaises(ValueError):
                get_salt(mac)

    def test_mac_single_character_parts(self) -> None:
        """Test MAC address with single character parts - valid hex."""
        mac = '1:2:3:4:5:A'  # Single characters are valid hex
        result = get_salt(mac)

        expected = bytearray([0x0A, 0x05, 0x04, 0x03, 0x02, 0x01])
        self.assertEqual(result, expected)

    def test_invalid_mac_empty_string(self) -> None:
        """Test with empty string."""
        with self.assertRaises(ValueError):
            get_salt('')  # Empty string -> int('', 16) fails

    def test_invalid_mac_wrong_separator(self) -> None:
        """Test MAC address with wrong separator."""
        # These don't use ':' separator so split() will return different results
        wrong_separator_macs = [
            '01-23-45-67-89-AB',  # Dash separator - no ':' so one part
            '01.23.45.67.89.AB',  # Dot separator - no ':' so one part
            '01 23 45 67 89 AB',  # Space separator - no ':' so one part
            '0123456789AB',       # No separators - one part
        ]

        for mac in wrong_separator_macs:
            # These will be treated as single hex values
            with self.assertRaises(ValueError):
                get_salt(mac)  # Will fail on invalid hex conversion

    def test_invalid_mac_empty_parts(self) -> None:
        """Test MAC address with empty parts."""
        invalid_macs = [
            ':23:45:67:89:AB',     # Empty part at start
            '01::45:67:89:AB',     # Empty part in middle
            '01:23:45:67:89:',     # Empty part at end
        ]

        for mac in invalid_macs:
            with self.assertRaises(ValueError):
                get_salt(mac)

    def test_mac_three_digit_parts(self) -> None:
        """Test MAC address with three digit parts - valid hex."""
        mac = '012:034:056:078:09A:0BC'  # Three digit hex numbers under 256
        result = get_salt(mac)

        # Should convert each part as hex and reverse
        expected = bytearray([0x0BC, 0x09A, 0x078, 0x056, 0x034, 0x012])
        self.assertEqual(result, expected)

    def test_mac_address_case_insensitivity(self) -> None:
        """Test that case doesn't matter for the same MAC address."""
        mac_lower = 'ab:cd:ef:12:34:56'
        mac_upper = 'AB:CD:EF:12:34:56'
        mac_mixed = 'Ab:Cd:Ef:12:34:56'

        result_lower = get_salt(mac_lower)
        result_upper = get_salt(mac_upper)
        result_mixed = get_salt(mac_mixed)

        self.assertEqual(result_lower, result_upper)
        self.assertEqual(result_lower, result_mixed)
        self.assertEqual(result_upper, result_mixed)

    def test_return_type_is_bytearray(self) -> None:
        """Test that return type is specifically bytearray."""
        mac = '01:23:45:67:89:AB'
        result = get_salt(mac)

        self.assertIsInstance(result, bytearray)
        self.assertNotIsInstance(result, bytes)
        self.assertNotIsInstance(result, list)

    def test_bytearray_mutability(self) -> None:
        """Test that returned bytearray is mutable."""
        mac = '01:23:45:67:89:AB'
        result = get_salt(mac)

        # Should be able to modify the returned bytearray
        original_first = result[0]
        result[0] = 0x99
        self.assertNotEqual(result[0], original_first)
        self.assertEqual(result[0], 0x99)

    def test_consistent_results(self) -> None:
        """Test that same input produces same output consistently."""
        mac = '12:34:56:78:9A:BC'

        result1 = get_salt(mac)
        result2 = get_salt(mac)
        result3 = get_salt(mac)

        self.assertEqual(result1, result2)
        self.assertEqual(result2, result3)
        self.assertEqual(result1, result3)

    def test_hex_conversion_accuracy(self) -> None:
        """Test accuracy of hex string to integer conversion."""
        # Test specific hex values to ensure correct parsing
        test_cases = [
            ('00:01:02:03:04:05', [0x05, 0x04, 0x03, 0x02, 0x01, 0x00]),
            ('0A:0B:0C:0D:0E:0F', [0x0F, 0x0E, 0x0D, 0x0C, 0x0B, 0x0A]),
            ('10:20:30:40:50:60', [0x60, 0x50, 0x40, 0x30, 0x20, 0x10]),
            ('A0:B1:C2:D3:E4:F5', [0xF5, 0xE4, 0xD3, 0xC2, 0xB1, 0xA0]),
        ]

        for mac, expected in test_cases:
            result = get_salt(mac)
            self.assertEqual(list(result), expected)
