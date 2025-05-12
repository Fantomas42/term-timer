import struct


class GanProtocolMessage:
    def __init__(self, message):
        # Convert each byte to an 8-bit binary string and join them
        self.bits = ''.join(
            bin(byte + 0x100)[3:]
            for byte in message
        )

    def __str__(self):
        return self.bits

    def get_bit_word(self, start_bit, bit_length, *, little_endian=False):
        if bit_length <= 8:
            # For 8 bits or less, simply parse the binary substring
            return int(self.bits[start_bit : start_bit + bit_length], 2)
        if bit_length in {16, 32}:
            # For 16 or 32 bits, create a byte array and use struct
            buf = bytearray(bit_length // 8)
            for i in range(len(buf)):
                buf[i] = int(
                    self.bits[8 * i + start_bit : 8 * i + start_bit + 8], 2,
                )

            # Format string for struct: < for little-endian, > for big-endian
            # H for 16-bit unsigned int, I for 32-bit unsigned int
            fmt = ('<' if little_endian else '>') + (
                'H' if bit_length == 16 else 'I'
            )
            return struct.unpack(fmt, buf)[0]

        msg = 'Unsupported bit word length'
        raise ValueError(msg)
