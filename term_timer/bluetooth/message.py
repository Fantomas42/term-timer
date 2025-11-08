"""Binary message parsing for GAN cube Bluetooth protocol."""

import struct
from collections.abc import Sequence


class GanProtocolMessage:
    def __init__(self, message: bytes | Sequence[int]) -> None:
        # Convert each byte to an 8-bit binary string and join them
        self.bits: str = ''.join(
            bin(byte + 0x100)[3:]
            for byte in message
        )

    def __str__(self) -> str:
        """Return binary string representation of message."""
        return self.bits

    def get_bit_word(self, start_bit: int, bit_length: int,
                     *, little_endian: bool = False,
                     signed: bool = False) -> int:
        if bit_length <= 8:
            # For 8 bits or less, simply parse the binary substring
            value = int(self.bits[start_bit : start_bit + bit_length], 2)
            if signed and bit_length > 1:
                # Convert to signed using two's complement
                sign_bit = 1 << (bit_length - 1)
                if value & sign_bit:
                    value -= (1 << bit_length)
            return value

        if bit_length in {16, 32}:
            # For 16 or 32 bits, create a byte array and use struct
            buf = bytearray(bit_length // 8)
            for i in range(len(buf)):
                buf[i] = int(
                    self.bits[8 * i + start_bit : 8 * i + start_bit + 8], 2,
                )

            # Format string for struct: < for little-endian, > for big-endian
            # H/I for unsigned, h/i for signed
            endian = '<' if little_endian else '>'
            if bit_length == 16:
                fmt = endian + ('h' if signed else 'H')
            else:  # 32 bits
                fmt = endian + ('i' if signed else 'I')

            result: int = struct.unpack(fmt, buf)[0]
            return result

        msg = 'Unsupported bit word length'
        raise ValueError(msg)
