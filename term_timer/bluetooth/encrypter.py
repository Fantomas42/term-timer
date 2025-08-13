from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import modes

INVALID_KEY = 'Key must be 16 bytes (128-bit) long'
INVALID_IV = 'Initialization Vector must be 16 bytes (128-bit) long'
INVALID_SALT = 'Salt must be 6 bytes (48-bit) long'
INVALID_DATA = 'Data must be at least 16 bytes long'


class GanGen2CubeEncrypter:
    def __init__(self, key, iv, salt):
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

    def _encrypt_chunk(self, buffer, offset):
        """Encrypt 16-byte buffer chunk starting at offset using AES-128-CBC"""
        cipher = Cipher(
            algorithms.AES(bytes(self._key)),
            modes.CBC(bytes(self._iv)),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
        chunk = encryptor.update(
            bytes(buffer[offset : offset + 16]),
        ) + encryptor.finalize()

        # Update buffer with encrypted chunk
        for i in range(16):
            buffer[offset + i] = chunk[i]

    def _decrypt_chunk(self, buffer, offset):
        """Decrypt 16-byte buffer chunk starting at offset using AES-128-CBC"""
        cipher = Cipher(
            algorithms.AES(bytes(self._key)),
            modes.CBC(bytes(self._iv)),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        chunk = decryptor.update(
            bytes(buffer[offset : offset + 16]),
        ) + decryptor.finalize()

        # Update buffer with decrypted chunk
        for i in range(16):
            buffer[offset + i] = chunk[i]

    def encrypt(self, data):
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

    def decrypt(self, data):
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
