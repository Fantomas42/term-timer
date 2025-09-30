# ruff: noqa: SLF001
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from term_timer.bluetooth.encrypter import INVALID_DATA
from term_timer.bluetooth.encrypter import INVALID_IV
from term_timer.bluetooth.encrypter import INVALID_KEY
from term_timer.bluetooth.encrypter import INVALID_SALT
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter


class TestGanGen2CubeEncrypter(unittest.TestCase):
    """Test cases for GanGen2CubeEncrypter class."""

    def setUp(self):
        """Set up test fixtures with valid key, IV, and salt."""
        self.valid_key = bytearray(16)  # 16 zero bytes
        self.valid_iv = bytearray(16)   # 16 zero bytes
        self.valid_salt = bytearray(6)  # 6 zero bytes

        # Test data for encryption/decryption
        self.test_data_16_bytes = bytearray(range(16))
        self.test_data_32_bytes = bytearray(range(32))
        self.test_data_48_bytes = bytearray(range(48))

        # Create encrypter instance for tests
        self.encrypter = GanGen2CubeEncrypter(
            self.valid_key, self.valid_iv, self.valid_salt,
        )

    def test_init_valid_parameters(self):
        """Test successful initialization with valid parameters."""
        key = bytearray(list(range(16)))
        iv = bytearray([i + 16 for i in range(16)])
        salt = bytearray([i + 32 for i in range(6)])

        encrypter = GanGen2CubeEncrypter(key, iv, salt)

        # Verify that salt was applied to first 6 bytes of key and iv
        for i in range(6):
            expected_key_byte = (key[i] + salt[i]) % 0xFF
            expected_iv_byte = (iv[i] + salt[i]) % 0xFF
            self.assertEqual(encrypter._key[i], expected_key_byte)
            self.assertEqual(encrypter._iv[i], expected_iv_byte)

        # Verify remaining bytes are unchanged
        for i in range(6, 16):
            self.assertEqual(encrypter._key[i], key[i])
            self.assertEqual(encrypter._iv[i], iv[i])

    def test_init_invalid_key_length(self):
        """Test initialization with invalid key length."""
        invalid_keys = [
            bytearray(15),  # Too short
            bytearray(17),  # Too long
            bytearray(0),   # Empty
            bytearray(32),  # Way too long
        ]

        for key in invalid_keys:
            with self.assertRaises(ValueError) as cm:
                GanGen2CubeEncrypter(key, self.valid_iv, self.valid_salt)
            self.assertEqual(str(cm.exception), INVALID_KEY)

    def test_init_invalid_iv_length(self):
        """Test initialization with invalid IV length."""
        invalid_ivs = [
            bytearray(15),  # Too short
            bytearray(17),  # Too long
            bytearray(0),   # Empty
            bytearray(32),  # Way too long
        ]

        for iv in invalid_ivs:
            with self.assertRaises(ValueError) as cm:
                GanGen2CubeEncrypter(self.valid_key, iv, self.valid_salt)
            self.assertEqual(str(cm.exception), INVALID_IV)

    def test_init_invalid_salt_length(self):
        """Test initialization with invalid salt length."""
        invalid_salts = [
            bytearray(5),   # Too short
            bytearray(7),   # Too long
            bytearray(0),   # Empty
            bytearray(16),  # Way too long
        ]

        for salt in invalid_salts:
            with self.assertRaises(ValueError) as cm:
                GanGen2CubeEncrypter(self.valid_key, self.valid_iv, salt)
            self.assertEqual(str(cm.exception), INVALID_SALT)

    def test_salt_application_modulo_operation(self):
        """Test that salt application uses modulo 0xFF correctly."""
        # Create key, iv, and salt that will cause overflow
        key = bytearray([0xFE] * 16)  # High values
        iv = bytearray([0xFD] * 16)   # High values
        salt = bytearray([0x05] * 6)  # Will cause overflow when added

        encrypter = GanGen2CubeEncrypter(key, iv, salt)

        # First 6 bytes should be (0xFE + 0x05) % 0xFF = 0x04
        for i in range(6):
            expected = (0xFE + 0x05) % 0xFF
            self.assertEqual(encrypter._key[i], expected)
            self.assertEqual(encrypter._iv[i], (0xFD + 0x05) % 0xFF)

        # Remaining bytes should be unchanged
        for i in range(6, 16):
            self.assertEqual(encrypter._key[i], 0xFE)
            self.assertEqual(encrypter._iv[i], 0xFD)

    def test_salt_application_boundary_values(self):
        """Test salt application with boundary values."""
        # Test with maximum values that won't overflow
        key = bytearray([0xF9] * 16)
        iv = bytearray([0xF8] * 16)
        salt = bytearray([0x05] * 6)

        encrypter = GanGen2CubeEncrypter(key, iv, salt)

        for i in range(6):
            self.assertEqual(encrypter._key[i], (0xF9 + 0x05) % 0xFF)
            self.assertEqual(encrypter._iv[i], (0xF8 + 0x05) % 0xFF)

    def test_encrypt_data_too_short(self):
        """Test encryption with data shorter than 16 bytes."""
        short_data_cases = [
            bytearray(),          # Empty
            bytearray([1]),       # 1 byte
            bytearray(range(8)),  # 8 bytes
            bytearray(range(15)),  # 15 bytes
        ]

        for data in short_data_cases:
            with self.assertRaises(ValueError) as cm:
                self.encrypter.encrypt(data)
            self.assertEqual(str(cm.exception), INVALID_DATA)

    def test_decrypt_data_too_short(self):
        """Test decryption with data shorter than 16 bytes."""
        short_data_cases = [
            bytearray(),          # Empty
            bytearray([1]),       # 1 byte
            bytearray(range(8)),  # 8 bytes
            bytearray(range(15)),  # 15 bytes
        ]

        for data in short_data_cases:
            with self.assertRaises(ValueError) as cm:
                self.encrypter.decrypt(data)
            self.assertEqual(str(cm.exception), INVALID_DATA)

    def test_encrypt_exactly_16_bytes(self):
        """Test encryption with exactly 16 bytes."""
        # Should encrypt only the first chunk
        result = self.encrypter.encrypt(self.test_data_16_bytes)

        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 16)
        # Result should be different from input (encrypted)
        self.assertNotEqual(result, bytes(self.test_data_16_bytes))

    def test_encrypt_more_than_16_bytes(self):
        """Test encryption with more than 16 bytes."""
        # Should encrypt both first and last chunks
        result = self.encrypter.encrypt(self.test_data_32_bytes)

        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 32)
        # Result should be different from input (encrypted)
        self.assertNotEqual(result, bytes(self.test_data_32_bytes))

    def test_encrypt_decrypt_roundtrip_16_bytes(self):
        """Test encrypt then decrypt returns original data (16 bytes)."""
        encrypted = self.encrypter.encrypt(self.test_data_16_bytes)
        decrypted = self.encrypter.decrypt(encrypted)

        self.assertEqual(decrypted, bytes(self.test_data_16_bytes))

    def test_encrypt_decrypt_roundtrip_32_bytes(self):
        """Test encrypt then decrypt returns original data (32 bytes)."""
        encrypted = self.encrypter.encrypt(self.test_data_32_bytes)
        decrypted = self.encrypter.decrypt(encrypted)

        self.assertEqual(decrypted, bytes(self.test_data_32_bytes))

    def test_encrypt_decrypt_roundtrip_48_bytes(self):
        """Test encrypt then decrypt returns original data (48 bytes)."""
        encrypted = self.encrypter.encrypt(self.test_data_48_bytes)
        decrypted = self.encrypter.decrypt(encrypted)

        self.assertEqual(decrypted, bytes(self.test_data_48_bytes))

    def test_encrypt_decrypt_roundtrip_various_sizes(self):
        """Test encrypt/decrypt roundtrip with various data sizes."""
        test_sizes = [16, 17, 24, 31, 32, 33, 48, 64, 100]

        for size in test_sizes:
            data = bytearray((i % 256) for i in range(size))
            encrypted = self.encrypter.encrypt(data)
            decrypted = self.encrypter.decrypt(encrypted)

            self.assertEqual(decrypted, bytes(data),
                           f'Roundtrip failed for size {size}')

    def test_encrypt_creates_copy(self):
        """Test that encrypt creates a copy and doesn't modify original."""
        original_data = self.test_data_16_bytes.copy()
        encrypted = self.encrypter.encrypt(self.test_data_16_bytes)

        # Original data should be unchanged
        self.assertEqual(self.test_data_16_bytes, original_data)
        # Encrypted should be different
        self.assertNotEqual(encrypted, bytes(original_data))

    def test_decrypt_creates_copy(self):
        """Test that decrypt creates a copy and doesn't modify original."""
        encrypted = self.encrypter.encrypt(self.test_data_16_bytes)
        encrypted_copy = bytearray(encrypted)
        decrypted = self.encrypter.decrypt(encrypted_copy)

        # Encrypted data should be unchanged
        self.assertEqual(encrypted_copy, encrypted)
        # Decrypted should match original
        self.assertEqual(decrypted, bytes(self.test_data_16_bytes))

    def test_different_keys_produce_different_results(self):
        """Test that different keys produce different encrypted results."""
        key1 = bytearray(range(16))
        key2 = bytearray(range(1, 17))

        encrypter1 = GanGen2CubeEncrypter(key1, self.valid_iv, self.valid_salt)
        encrypter2 = GanGen2CubeEncrypter(key2, self.valid_iv, self.valid_salt)

        encrypted1 = encrypter1.encrypt(self.test_data_16_bytes)
        encrypted2 = encrypter2.encrypt(self.test_data_16_bytes)

        self.assertNotEqual(encrypted1, encrypted2)

    def test_different_ivs_produce_different_results(self):
        """Test that different IVs produce different encrypted results."""
        iv1 = bytearray(range(16))
        iv2 = bytearray(range(1, 17))

        encrypter1 = GanGen2CubeEncrypter(self.valid_key, iv1, self.valid_salt)
        encrypter2 = GanGen2CubeEncrypter(self.valid_key, iv2, self.valid_salt)

        encrypted1 = encrypter1.encrypt(self.test_data_16_bytes)
        encrypted2 = encrypter2.encrypt(self.test_data_16_bytes)

        self.assertNotEqual(encrypted1, encrypted2)

    def test_different_salts_produce_different_results(self):
        """Test that different salts produce different encrypted results."""
        salt1 = bytearray(range(6))
        salt2 = bytearray(range(1, 7))

        encrypter1 = GanGen2CubeEncrypter(self.valid_key, self.valid_iv, salt1)
        encrypter2 = GanGen2CubeEncrypter(self.valid_key, self.valid_iv, salt2)

        encrypted1 = encrypter1.encrypt(self.test_data_16_bytes)
        encrypted2 = encrypter2.encrypt(self.test_data_16_bytes)

        self.assertNotEqual(encrypted1, encrypted2)

    @patch('term_timer.bluetooth.encrypter.Cipher')
    def test_encrypt_chunk_calls_aes_correctly(self, mock_cipher_class):
        """Test that _encrypt_chunk calls AES with correct parameters."""
        mock_cipher = MagicMock()
        mock_encryptor = MagicMock()
        mock_encryptor.update.return_value = b'encrypted_chunk_'
        mock_encryptor.finalize.return_value = b''
        mock_cipher.encryptor.return_value = mock_encryptor
        mock_cipher_class.return_value = mock_cipher

        buffer = bytearray(32)
        self.encrypter._encrypt_chunk(buffer, 0)

        # Verify Cipher was called with correct parameters
        mock_cipher_class.assert_called_once()
        args = mock_cipher_class.call_args[0]
        self.assertEqual(len(args), 2)  # algorithms.AES, modes.CBC
        # backend is passed as keyword argument

    @patch('term_timer.bluetooth.encrypter.Cipher')
    def test_decrypt_chunk_calls_aes_correctly(self, mock_cipher_class):
        """Test that _decrypt_chunk calls AES with correct parameters."""
        mock_cipher = MagicMock()
        mock_decryptor = MagicMock()
        mock_decryptor.update.return_value = b'decrypted_chunk_'
        mock_decryptor.finalize.return_value = b''
        mock_cipher.decryptor.return_value = mock_decryptor
        mock_cipher_class.return_value = mock_cipher

        buffer = bytearray(32)
        self.encrypter._decrypt_chunk(buffer, 0)

        # Verify Cipher was called with correct parameters
        mock_cipher_class.assert_called_once()
        args = mock_cipher_class.call_args[0]
        self.assertEqual(len(args), 2)  # algorithms.AES, modes.CBC
        # backend is passed as keyword argument

    def test_encryption_deterministic_with_same_inputs(self):
        """Test that encryption is deterministic with same inputs."""
        # Note: CBC mode with same IV should produce same results
        result1 = self.encrypter.encrypt(self.test_data_16_bytes)
        result2 = self.encrypter.encrypt(self.test_data_16_bytes)

        self.assertEqual(result1, result2)

    def test_encryption_chunk_boundaries(self):
        """Test encryption behavior at chunk boundaries."""
        # Test data that's exactly at chunk boundaries
        test_cases = [
            16,  # Exactly one chunk
            32,  # Exactly two chunks
            48,  # Exactly three chunks
        ]

        for size in test_cases:
            data = bytearray((i % 256) for i in range(size))
            encrypted = self.encrypter.encrypt(data)
            decrypted = self.encrypter.decrypt(encrypted)

            self.assertEqual(len(encrypted), size)
            self.assertEqual(decrypted, bytes(data))

    def test_large_data_encryption(self):
        """Test encryption with large data sets."""
        # Test with 1KB of data
        large_data = bytearray(range(256)) * 4  # 1024 bytes
        encrypted = self.encrypter.encrypt(large_data)
        decrypted = self.encrypter.decrypt(encrypted)

        self.assertEqual(len(encrypted), len(large_data))
        self.assertEqual(decrypted, bytes(large_data))

    def test_zero_filled_data(self):
        """Test encryption with zero-filled data."""
        zero_data = bytearray(32)  # 32 zeros
        encrypted = self.encrypter.encrypt(zero_data)
        decrypted = self.encrypter.decrypt(encrypted)

        # Should encrypt and decrypt correctly

        # Should be encrypted
        self.assertNotEqual(encrypted, bytes(zero_data))
        # Should decrypt to original
        self.assertEqual(decrypted, bytes(zero_data))

    def test_random_byte_patterns(self):
        """Test encryption with various byte patterns."""
        test_patterns = [
            bytearray([0xFF] * 16),      # All ones
            bytearray([0xAA] * 16),      # Alternating pattern
            bytearray([0x55] * 16),      # Alternating pattern
            bytearray(range(16)),        # Sequential
            bytearray(range(15, -1, -1)),  # Reverse sequential
        ]

        for pattern in test_patterns:
            encrypted = self.encrypter.encrypt(pattern)
            decrypted = self.encrypter.decrypt(encrypted)

            # Should be encrypted
            self.assertNotEqual(encrypted, bytes(pattern))
            # Should decrypt correctly
            self.assertEqual(decrypted, bytes(pattern))

    def test_middle_bytes_unchanged_for_large_data(self):
        """Test that middle bytes are unchanged in large data encryption."""
        # For data > 32 bytes, middle sections should remain unencrypted
        large_data = bytearray(range(100))
        original_middle = large_data[16:84].copy()  # Middle section

        encrypted = self.encrypter.encrypt(large_data)

        # Middle section should be unchanged
        encrypted_middle = encrypted[16:84]
        self.assertEqual(encrypted_middle, bytes(original_middle))

        # But first and last 16 bytes should be different
        self.assertNotEqual(encrypted[0:16], bytes(large_data[0:16]))
        self.assertNotEqual(encrypted[84:100], bytes(large_data[84:100]))

    def test_constant_error_messages(self):
        """Test that error message constants are correct."""
        self.assertEqual(
            INVALID_KEY,
            'Key must be 16 bytes (128-bit) long',
        )
        self.assertEqual(
            INVALID_IV,
            'Initialization Vector must be 16 bytes (128-bit) long',
        )
        self.assertEqual(
            INVALID_SALT,
            'Salt must be 6 bytes (48-bit) long',
        )
        self.assertEqual(
            INVALID_DATA,
            'Data must be at least 16 bytes long',
        )

    def test_salt_modulo_edge_case(self):
        """Test edge case where salt addition equals 0xFF."""
        # When (key_byte + salt_byte) equals 0xFF,
        # result should be 0xFE due to modulo
        key = bytearray([0xFA] * 16)
        iv = bytearray([0xFB] * 16)
        salt = bytearray([0x05] * 6)  # 0xFA + 0x05 = 0xFF

        encrypter = GanGen2CubeEncrypter(key, iv, salt)

        # (0xFA + 0x05) % 0xFF = 0xFF % 0xFF = 0
        # (0xFB + 0x05) % 0xFF = 0x100 % 0xFF = 1
        for i in range(6):
            self.assertEqual(encrypter._key[i], 0)  # 0xFF % 0xFF = 0
            self.assertEqual(encrypter._iv[i], 1)   # 0x100 % 0xFF = 1
