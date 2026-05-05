"""
AES-128 encryption and decryption for GAN cube protocols.

Each message operates on independent 16-byte blocks, so we use ECB mode with
a persistent context (avoiding per-call context allocation) and apply the IV
XOR manually — semantically equivalent to CBC for single-block operations.
"""
from collections.abc import Sequence
from typing import Final

from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import modes

INVALID_KEY: Final[str] = 'Key must be 16 bytes (128-bit) long'
INVALID_IV: Final[str] = 'Initialization Vector must be 16 bytes (128-bit) long'
INVALID_SALT: Final[str] = 'Salt must be 6 bytes (48-bit) long'
INVALID_DATA: Final[str] = 'Data must be at least 16 bytes long'


class GanGen2CubeEncrypter:
    """AES-128 encrypter for GAN Gen2 cube Bluetooth protocol."""

    def __init__(self, key: Sequence[int], iv: Sequence[int],
                 salt: Sequence[int]) -> None:
        """
        Initialize encrypter with AES key, IV, and cube-specific salt.

        Raises:
            ValueError: If key, IV, or salt have incorrect lengths.

        """
        if len(key) != 16:
            raise ValueError(INVALID_KEY)
        if len(iv) != 16:
            raise ValueError(INVALID_IV)
        if len(salt) != 6:
            raise ValueError(INVALID_SALT)

        # Apply salt to key and iv
        self._key = bytearray(key)
        self._iv = bytearray(iv)

        # Apply salt to first 6 bytes of key and iv
        for i in range(6):
            self._key[i] = (key[i] + salt[i]) % 0xFF
            self._iv[i] = (iv[i] + salt[i]) % 0xFF

        # Pre-create persistent ECB contexts — reusing them across messages
        # avoids per-call context allocation and ABC isinstance checks.
        # Single-block ECB + manual IV XOR is equivalent to single-block CBC.
        ecb = Cipher(algorithms.AES(bytes(self._key)), modes.ECB())  # noqa: S305
        self._enc_ctx = ecb.encryptor()
        self._dec_ctx = ecb.decryptor()
        self._iv_int = int.from_bytes(self._iv, 'big')

    def _encrypt_chunk(self, buffer: bytearray, offset: int) -> None:
        """Encrypt 16-byte buffer chunk starting at offset."""
        pt_int = (
            int.from_bytes(buffer[offset:offset + 16], 'big') ^ self._iv_int
        )
        chunk = self._enc_ctx.update(pt_int.to_bytes(16, 'big'))
        buffer[offset:offset + 16] = chunk

    def _decrypt_chunk(self, buffer: bytearray, offset: int) -> None:
        """Decrypt 16-byte buffer chunk starting at offset."""
        raw = self._dec_ctx.update(buffer[offset:offset + 16])
        chunk_int = int.from_bytes(raw, 'big') ^ self._iv_int
        buffer[offset:offset + 16] = chunk_int.to_bytes(16, 'big')

    def encrypt(self, data: bytearray) -> bytes:
        """
        Encrypt data using AES-128-CBC.

        Returns:
            Encrypted bytes with first and last 16-byte chunks encrypted.

        Raises:
            ValueError: If data is less than 16 bytes long.

        """
        if len(data) < 16:
            raise ValueError(INVALID_DATA)

        # Create a copy of the data
        res = bytearray(data)

        # Encrypt 16-byte chunk aligned to message start
        self._encrypt_chunk(res, 0)

        # Encrypt 16-byte chunk aligned to message end
        if len(res) > 16:
            self._encrypt_chunk(res, len(res) - 16)

        return bytes(res)

    def decrypt(self, data: bytearray) -> bytes:
        """
        Decrypt data using AES-128-CBC.

        Returns:
            Decrypted bytes with first and last 16-byte chunks decrypted.

        Raises:
            ValueError: If data is less than 16 bytes long.

        """
        if len(data) < 16:
            raise ValueError(INVALID_DATA)

        # Create a copy of the data
        res = bytearray(data)

        # Decrypt 16-byte chunk aligned to message end
        if len(res) > 16:
            self._decrypt_chunk(res, len(res) - 16)

        # Decrypt 16-byte chunk aligned to message start
        self._decrypt_chunk(res, 0)

        return bytes(res)
