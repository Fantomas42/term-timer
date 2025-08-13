import unittest

from term_timer.bluetooth.message import GanProtocolMessage


class TestGanProtocolMessage(unittest.TestCase):

    def setUp(self):
        hex_value = 0xAB47882CFFF873493FA2B87509ECB43AFF000000
        hex_string = hex(hex_value)[2:]  # noqa: FURB116
        if len(hex_string) % 2:
            hex_string = '0' + hex_string

        self.data = bytearray.fromhex(hex_string)

    def test_str(self):
        msg = GanProtocolMessage(self.data)
        self.assertEqual(
            str(msg),
            '1010101101000111100010000010110011111111111110000111001101001001001111111010001010111000011101010000100111101100101101000011101011111111000000000000000000000000',
        )

    def test_get_bit_words_signed_little_endian(self):
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

    def test_get_bit_words_unsigned_little_endian(self):
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

    def test_get_bit_words_invalid_size(self):
        msg = GanProtocolMessage(self.data)

        with self.assertRaises(ValueError):
            msg.get_bit_word(0, 21)
