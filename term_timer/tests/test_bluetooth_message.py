import unittest

from term_timer.bluetooth.message import GanProtocolMessage


class TestGanProtocolMessage(unittest.TestCase):
    """Test cases for GanProtocolMessage class."""

    def setUp(self) -> None:
        hex_value = 0xAB47882CFFF873493FA2B87509ECB43AFF000000
        hex_string = hex(hex_value)[2:]  # noqa: FURB116
        if len(hex_string) % 2:
            hex_string = '0' + hex_string

        self.data = bytearray.fromhex(hex_string)
        self.empty_data = bytearray()
        self.single_byte_data = bytearray([0xFF])
        self.two_byte_data = bytearray([0xAB, 0xCD])
        self.small_data = bytearray([0x12, 0x34, 0x56, 0x78])

    def test_str(self) -> None:
        msg = GanProtocolMessage(self.data)
        self.assertEqual(
            str(msg),
            '1010101101000111100010000010110011111111111110000111001101001001001111111010001010111000011101010000100111101100101101000011101011111111000000000000000000000000',
        )

    def test_get_bit_words_signed_little_endian(self) -> None:
        msg = GanProtocolMessage(self.data)

        event = msg.get_bit_word(0, 8, signed=True)
        event_bis = msg.get_bit_word(0, 16, signed=True)
        qw = msg.get_bit_word(8, 32, little_endian=True, signed=True)
        qx = msg.get_bit_word(40, 32, little_endian=True, signed=True)
        qy = msg.get_bit_word(72, 32, little_endian=True, signed=True)
        qz = msg.get_bit_word(104, 32, little_endian=True, signed=True)

        self.assertEqual(event, -85)
        self.assertEqual(event_bis, -21689)
        self.assertEqual(qw, -13858745)
        self.assertEqual(qx, 1061778424)
        self.assertEqual(qy, 158709922)
        self.assertEqual(qz, -12929812)

    def test_get_bit_words_unsigned_little_endian(self) -> None:
        msg = GanProtocolMessage(self.data)

        event = msg.get_bit_word(0, 8, signed=False)
        event_bis = msg.get_bit_word(0, 16, signed=False)
        qw = msg.get_bit_word(8, 32, little_endian=True, signed=False)
        qx = msg.get_bit_word(40, 32, little_endian=True, signed=False)
        qy = msg.get_bit_word(72, 32, little_endian=True, signed=False)
        qz = msg.get_bit_word(104, 32, little_endian=True, signed=False)

        self.assertEqual(event, 171)
        self.assertEqual(event_bis, 43847)
        self.assertEqual(qw, 4281108551)
        self.assertEqual(qx, 1061778424)
        self.assertEqual(qy, 158709922)
        self.assertEqual(qz, 4282037484)

    def test_get_bit_words_invalid_size(self) -> None:
        msg = GanProtocolMessage(self.data)

        with self.assertRaises(ValueError):
            msg.get_bit_word(0, 21)

    def test_init_with_empty_data(self) -> None:
        """Test initialization with empty byte array."""
        msg = GanProtocolMessage(self.empty_data)
        self.assertEqual(str(msg), '')

    def test_init_with_single_byte(self) -> None:
        """Test initialization with single byte."""
        msg = GanProtocolMessage(self.single_byte_data)
        self.assertEqual(str(msg), '11111111')

    def test_init_with_two_bytes(self) -> None:
        """Test initialization with two bytes."""
        msg = GanProtocolMessage(self.two_byte_data)
        self.assertEqual(str(msg), '1010101111001101')

    def test_get_bit_word_single_bit(self) -> None:
        """Test extracting single bit."""
        msg = GanProtocolMessage(self.two_byte_data)  # 1010101111001101
        self.assertEqual(msg.get_bit_word(0, 1), 1)
        self.assertEqual(msg.get_bit_word(1, 1), 0)
        self.assertEqual(msg.get_bit_word(7, 1), 1)

    def test_get_bit_word_two_bits_signed(self) -> None:
        """Test extracting two bits with signed interpretation."""
        msg = GanProtocolMessage(bytearray([0b11000000]))  # 11000000
        # First two bits are '11' which is -1 in 2-bit signed
        self.assertEqual(msg.get_bit_word(0, 2, signed=True), -1)
        # Bits 2-3 are '00' which is 0 in 2-bit signed
        self.assertEqual(msg.get_bit_word(2, 2, signed=True), 0)

    def test_get_bit_word_two_bits_unsigned(self) -> None:
        """Test extracting two bits with unsigned interpretation."""
        msg = GanProtocolMessage(bytearray([0b11000000]))  # 11000000
        # First two bits are '11' which is 3 unsigned
        self.assertEqual(msg.get_bit_word(0, 2, signed=False), 3)
        # Bits 2-3 are '00' which is 0 unsigned
        self.assertEqual(msg.get_bit_word(2, 2, signed=False), 0)

    def test_get_bit_word_eight_bits_signed(self) -> None:
        """Test extracting eight bits with signed interpretation."""
        msg = GanProtocolMessage(bytearray([0x80, 0x7F]))  # 10000000 01111111
        # First byte 0x80 = -128 in signed 8-bit
        self.assertEqual(msg.get_bit_word(0, 8, signed=True), -128)
        # Second byte 0x7F = 127 in signed 8-bit
        self.assertEqual(msg.get_bit_word(8, 8, signed=True), 127)

    def test_get_bit_word_eight_bits_unsigned(self) -> None:
        """Test extracting eight bits with unsigned interpretation."""
        msg = GanProtocolMessage(bytearray([0x80, 0x7F]))  # 10000000 01111111
        # First byte 0x80 = 128 unsigned
        self.assertEqual(msg.get_bit_word(0, 8, signed=False), 128)
        # Second byte 0x7F = 127 unsigned
        self.assertEqual(msg.get_bit_word(8, 8, signed=False), 127)

    def test_get_bit_word_sixteen_bits_big_endian_signed(self) -> None:
        """Test extracting 16 bits big-endian signed."""
        msg = GanProtocolMessage(bytearray([0x80, 0x00]))  # 1000000000000000
        # 0x8000 = -32768 in signed 16-bit big-endian
        self.assertEqual(
            msg.get_bit_word(0, 16, little_endian=False, signed=True),
            -32768,
        )

    def test_get_bit_word_sixteen_bits_little_endian_signed(self) -> None:
        """Test extracting 16 bits little-endian signed."""
        msg = GanProtocolMessage(bytearray([0x00, 0x80]))  # 0000000010000000
        # Little-endian: 0x8000 = -32768 in signed 16-bit
        self.assertEqual(
            msg.get_bit_word(0, 16, little_endian=True, signed=True),
            -32768,
        )

    def test_get_bit_word_sixteen_bits_unsigned(self) -> None:
        """Test extracting 16 bits unsigned."""
        msg = GanProtocolMessage(bytearray([0xFF, 0xFF]))  # 1111111111111111
        # 0xFFFF = 65535 unsigned
        self.assertEqual(msg.get_bit_word(0, 16, signed=False), 65535)

    def test_get_bit_word_thirty_two_bits_big_endian_signed(self) -> None:
        """Test extracting 32 bits big-endian signed."""
        msg = GanProtocolMessage(bytearray([0x80, 0x00, 0x00, 0x00]))
        # 0x80000000 = -2147483648 in signed 32-bit big-endian
        self.assertEqual(
            msg.get_bit_word(0, 32, little_endian=False, signed=True),
            -2147483648,
        )

    def test_get_bit_word_thirty_two_bits_little_endian_signed(self) -> None:
        """Test extracting 32 bits little-endian signed."""
        msg = GanProtocolMessage(bytearray([0x00, 0x00, 0x00, 0x80]))
        # Little-endian: 0x80000000 = -2147483648 in signed 32-bit
        self.assertEqual(
            msg.get_bit_word(0, 32, little_endian=True, signed=True),
            -2147483648,
        )

    def test_get_bit_word_thirty_two_bits_unsigned(self) -> None:
        """Test extracting 32 bits unsigned."""
        msg = GanProtocolMessage(bytearray([0xFF, 0xFF, 0xFF, 0xFF]))
        # 0xFFFFFFFF = 4294967295 unsigned
        self.assertEqual(msg.get_bit_word(0, 32, signed=False), 4294967295)

    def test_get_bit_word_start_bit_boundary_conditions(self) -> None:
        """Test start_bit at various boundary conditions."""
        msg = GanProtocolMessage(self.data)
        # Test at start of message
        result = msg.get_bit_word(0, 8)
        self.assertIsInstance(result, int)

        # Test near end of message (data has 20 bytes = 160 bits)
        result = msg.get_bit_word(152, 8)  # Last 8 bits
        self.assertIsInstance(result, int)

    def test_get_bit_word_invalid_bit_lengths(self) -> None:
        """Test various invalid bit lengths."""
        msg = GanProtocolMessage(self.data)

        invalid_lengths = [9, 10, 11, 12, 13, 14, 15, 17, 18, 24, 31, 33, 64]
        for length in invalid_lengths:
            with self.assertRaises(ValueError) as cm:
                msg.get_bit_word(0, length)
            self.assertEqual(str(cm.exception), 'Unsupported bit word length')

    def test_get_bit_word_zero_bit_length(self) -> None:
        """Test with zero bit length."""
        msg = GanProtocolMessage(self.small_data)
        # Zero bits should raise ValueError (empty string for int conversion)
        with self.assertRaises(ValueError):
            msg.get_bit_word(0, 0)

    def test_get_bit_word_boundary_crossing(self) -> None:
        """Test extracting bits that cross byte boundaries."""
        # Create data where we know the bit pattern
        data = bytearray([0xF0, 0x0F])  # 11110000 00001111
        msg = GanProtocolMessage(data)

        # Extract 4 bits starting at bit 4 (bits 4-7 from first byte)
        # Bits 4-7 from first byte are '0000'
        result = msg.get_bit_word(4, 4)
        self.assertEqual(result, 0)  # 0000

        # Extract 8 bits starting at bit 4 (spans across byte boundary)
        # Bits 4-11: '0000' from first byte + '0000' from second byte
        result = msg.get_bit_word(4, 8)
        self.assertEqual(result, 0)  # 00000000

        # Extract 8 bits starting at bit 8 (second byte)
        # Second byte is 00001111
        result = msg.get_bit_word(8, 8)
        self.assertEqual(result, 15)  # 00001111

    def test_binary_conversion_accuracy(self) -> None:
        """Test that binary conversion is accurate for known values."""
        # Test with known byte values
        test_cases = [
            (bytearray([0x00]), '00000000'),
            (bytearray([0xFF]), '11111111'),
            (bytearray([0x55]), '01010101'),
            (bytearray([0xAA]), '10101010'),
            (bytearray([0x0F, 0xF0]), '0000111111110000'),
        ]

        for data, expected_bits in test_cases:
            msg = GanProtocolMessage(data)
            self.assertEqual(str(msg), expected_bits)

    def test_message_with_large_data(self) -> None:
        """Test with larger data arrays."""
        # Create 100 bytes of data
        large_data = bytearray(range(100))
        msg = GanProtocolMessage(large_data)

        # Should have 800 bits total
        self.assertEqual(len(str(msg)), 800)

        # Test extracting from various positions
        self.assertIsInstance(msg.get_bit_word(0, 8), int)
        self.assertIsInstance(msg.get_bit_word(400, 16), int)
        self.assertIsInstance(msg.get_bit_word(784, 16), int)  # Last 16 bits
