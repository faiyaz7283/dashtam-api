"""Unit tests for EncryptionService.

Tests AES-256 Fernet encryption/decryption functionality used for securing
OAuth tokens and sensitive data. Covers:
- String encryption/decryption (plaintext, unicode, long strings)
- Dictionary encryption (selective string field encryption)
- Encryption validation (is_encrypted checks)
- Singleton pattern implementation
- Error handling for invalid encrypted data
- Convenience functions for token encryption

Note:
    Uses synchronous test pattern (regular def test_*(), NOT async def)
    since EncryptionService operates synchronously with Fernet.
    Tests are isolated without database or external dependencies.
"""

import pytest

from src.services.encryption import (
    EncryptionService,
    get_encryption_service,
    encrypt_token,
    decrypt_token,
)


class TestEncryptionService:
    """Test suite for EncryptionService encryption operations.
    
    Validates AES-256 Fernet encryption/decryption for token security.
    Tests cover basic operations, edge cases, singleton behavior, and error handling.
    """

    def test_encrypt_decrypt_string(self):
        """Test basic string encryption and decryption roundtrip.
        
        Verifies that:
        - Encrypted string differs from plaintext
        - Encrypted string starts with Fernet prefix "gAAAAA"
        - Decryption returns original plaintext
        - Roundtrip encryption maintains data integrity
        
        Note:
            Fernet uses AES-256-CBC with HMAC authentication.
        """
        service = EncryptionService()
        plaintext = "my_secret_token_12345"

        # Encrypt
        encrypted = service.encrypt(plaintext)

        # Should be different from original
        assert encrypted != plaintext
        # Should start with Fernet token prefix
        assert encrypted.startswith("gAAAAA")

        # Decrypt
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_empty_string(self):
        """Test empty string handling (special case).
        
        Verifies that:
        - Empty string encrypts to empty string (optimization)
        - Empty string decrypts to empty string
        - No encryption overhead for empty values
        
        Note:
            Empty strings are not encrypted (performance optimization).
        """
        service = EncryptionService()

        encrypted = service.encrypt("")
        assert encrypted == ""

        decrypted = service.decrypt("")
        assert decrypted == ""

    def test_encrypt_unicode_string(self):
        """Test encryption of unicode characters (international support).
        
        Verifies that:
        - Unicode characters are properly encrypted
        - UTF-8 encoding is handled correctly
        - Decryption preserves unicode characters
        - Emojis and special characters work correctly
        
        Note:
            Tests characters from multiple scripts: Chinese, emoji, accented.
        """
        service = EncryptionService()
        plaintext = "Hello 世界 🌍 café"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_long_string(self):
        """Test encryption of long strings (10,000 characters).
        
        Verifies that:
        - Long strings are encrypted without errors
        - Decryption works for large payloads
        - Encrypted size is larger than plaintext (overhead)
        - No length limitations in practice
        
        Note:
            Tests with 10,000 char string to validate large token handling.
        """
        service = EncryptionService()
        plaintext = "a" * 10000

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext
        assert len(encrypted) > len(plaintext)

    def test_encrypt_dict(self):
        """Test selective encryption of dictionary string fields.
        
        Verifies that:
        - String values are encrypted (access_token, refresh_token, etc.)
        - Non-string values remain unencrypted (expires_in, counts)
        - Decryption restores original dictionary
        - Mixed data types handled correctly
        
        Note:
            Only string fields are encrypted; integers, booleans preserved.
            Used for OAuth token response encryption.
        """
        service = EncryptionService()
        data = {
            "access_token": "token123",
            "refresh_token": "refresh456",
            "id_token": "id789",
            "expires_in": 3600,  # Non-string value
        }

        encrypted = service.encrypt_dict(data)

        # String values should be encrypted
        assert encrypted["access_token"] != data["access_token"]
        assert encrypted["refresh_token"] != data["refresh_token"]
        assert encrypted["id_token"] != data["id_token"]

        # Non-string values should remain unchanged
        assert encrypted["expires_in"] == data["expires_in"]

        # Decrypt back
        decrypted = service.decrypt_dict(encrypted)
        assert decrypted == data

    def test_is_encrypted(self):
        """Test encryption detection by Fernet format.
        
        Verifies that:
        - Plaintext returns False for is_encrypted
        - Encrypted string returns True
        - Empty string returns False
        - Fernet prefix "gAAAAA" is recognized
        
        Note:
            Detection based on Fernet token format prefix.
        """
        service = EncryptionService()

        plaintext = "not_encrypted"
        encrypted = service.encrypt(plaintext)

        assert not service.is_encrypted(plaintext)
        assert service.is_encrypted(encrypted)
        assert not service.is_encrypted("")

    def test_singleton_pattern(self):
        """Test EncryptionService singleton pattern implementation.
        
        Verifies that:
        - Multiple instantiations return same instance
        - All instances share same cipher key
        - Encryption by one instance can be decrypted by another
        - Single encryption key across application
        
        Note:
            Singleton ensures consistent encryption key from ENCRYPTION_KEY env var.
        """
        service1 = EncryptionService()
        service2 = EncryptionService()

        # Should be same instance
        assert service1 is service2

        # Should use same cipher
        plaintext = "test_token"
        encrypted1 = service1.encrypt(plaintext)
        decrypted2 = service2.decrypt(encrypted1)

        assert decrypted2 == plaintext

    def test_decrypt_invalid_data_raises_exception(self):
        """Test decryption error handling for invalid ciphertext.
        
        Verifies that:
        - Invalid encrypted string raises exception
        - Error message mentions "Failed to decrypt data"
        - Malformed Fernet tokens are rejected
        - No silent failures or corrupted output
        
        Raises:
            Exception: Expected exception with "Failed to decrypt data" message
        
        Note:
            Fernet validates HMAC before decryption, preventing tampering.
        """
        service = EncryptionService()

        with pytest.raises(Exception, match="Failed to decrypt data"):
            service.decrypt("not_a_valid_encrypted_string")

    def test_different_encryptions_same_plaintext(self):
        """Test encryption uniqueness due to random IV/nonce.
        
        Verifies that:
        - Same plaintext produces different ciphertexts each time
        - Randomization prevents pattern analysis
        - Both ciphertexts decrypt to same plaintext
        - IV/nonce is included in Fernet token
        
        Note:
            Critical security property: prevents ciphertext pattern analysis.
            Fernet includes random IV in token for uniqueness.
        """
        service = EncryptionService()
        plaintext = "same_token"

        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)

        # Should be different due to nonce/IV
        assert encrypted1 != encrypted2

        # But both should decrypt to same plaintext
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext

    def test_decrypt_dict_with_non_string_values(self):
        """Test dictionary decryption with mixed value types.
        
        Verifies that:
        - Encrypted strings are decrypted correctly
        - Integers remain unchanged (not decrypted)
        - Booleans remain unchanged
        - Empty strings are handled correctly
        - Mixed types coexist in same dictionary
        
        Note:
            Only string fields are decrypted; other types passed through.
        """
        service = EncryptionService()
        encrypted_data = {
            "access_token": service.encrypt("token123"),
            "expires_in": 3600,
            "count": 5,
            "is_active": True,
            "empty_string": "",
        }

        decrypted = service.decrypt_dict(encrypted_data)

        # String value should be decrypted
        assert decrypted["access_token"] == "token123"
        # Non-string values should remain unchanged
        assert decrypted["expires_in"] == 3600
        assert decrypted["count"] == 5
        assert decrypted["is_active"] is True
        assert decrypted["empty_string"] == ""

    def test_decrypt_dict_with_invalid_encrypted_values(self):
        """Test graceful handling of invalid encrypted values in dictionary.
        
        Verifies that:
        - Valid encrypted strings are decrypted
        - Invalid encrypted strings remain unchanged (no exception)
        - Graceful degradation for corrupted data
        - Partial decryption succeeds for mixed valid/invalid data
        
        Note:
            Prevents one corrupted field from breaking entire dictionary.
        """
        service = EncryptionService()
        data = {
            "valid_token": service.encrypt("token123"),
            "invalid_token": "not_encrypted",
        }

        decrypted = service.decrypt_dict(data)

        # Valid token should be decrypted
        assert decrypted["valid_token"] == "token123"
        # Invalid token should remain unchanged (not raise exception)
        assert decrypted["invalid_token"] == "not_encrypted"

    def test_get_instance_classmethod(self):
        """Test get_instance() class method for singleton access.
        
        Verifies that:
        - get_instance() returns singleton instance
        - Multiple calls return same instance
        - Instance is properly initialized
        - Class method provides alternative access pattern
        
        Note:
            Both __init__() and get_instance() return same singleton.
        """
        # Clear any existing instance
        EncryptionService._instance = None

        instance1 = EncryptionService.get_instance()
        instance2 = EncryptionService.get_instance()

        assert instance1 is not None
        assert instance1 is instance2

    def test_is_encrypted_with_fernet_prefix(self):
        """Test Fernet token format recognition by prefix.
        
        Verifies that:
        - Encrypted tokens start with "gAAAAA" prefix
        - is_encrypted correctly identifies Fernet format
        - Prefix detection is reliable
        
        Note:
            "gAAAAA" is base64 encoding of Fernet version byte (0x80).
        """
        service = EncryptionService()
        encrypted = service.encrypt("test_token")

        # Should recognize by prefix
        assert encrypted.startswith("gAAAAA")
        assert service.is_encrypted(encrypted)


class TestEncryptionConvenienceFunctions:
    """Test suite for module-level convenience functions.
    
    Tests convenience wrappers: get_encryption_service(), encrypt_token(),
    and decrypt_token() for simplified token encryption API.
    """

    def test_get_encryption_service(self):
        """Test get_encryption_service() module-level function.
        
        Verifies that:
        - Function returns EncryptionService instance
        - Multiple calls return same instance (singleton)
        - Global service variable is properly managed
        
        Note:
            Convenience function for accessing singleton without instantiation.
        """
        from src.services import encryption

        # Clear global service
        encryption._encryption_service = None

        service1 = get_encryption_service()
        service2 = get_encryption_service()

        assert service1 is not None
        assert service1 is service2

    def test_encrypt_token_convenience_function(self):
        """Test encrypt_token() convenience wrapper function.
        
        Verifies that:
        - Function encrypts plaintext token
        - Returns Fernet-formatted ciphertext
        - Simplifies encryption API (no service instantiation)
        
        Note:
            Wrapper around EncryptionService.encrypt() for common use case.
        """
        plaintext = "test_token_123"
        encrypted = encrypt_token(plaintext)

        assert encrypted != plaintext
        assert encrypted.startswith("gAAAAA")

    def test_decrypt_token_convenience_function(self):
        """Test decrypt_token() convenience wrapper function.
        
        Verifies that:
        - Function decrypts Fernet ciphertext
        - Returns original plaintext
        - Roundtrip works with encrypt_token()
        
        Note:
            Wrapper around EncryptionService.decrypt() for common use case.
        """
        plaintext = "test_token_123"
        encrypted = encrypt_token(plaintext)
        decrypted = decrypt_token(encrypted)

        assert decrypted == plaintext

    def test_encrypt_decrypt_token_roundtrip(self):
        """Test full encryption/decryption roundtrip via convenience API.
        
        Verifies that:
        - encrypt_token() and decrypt_token() work together
        - Original plaintext is recovered
        - Ciphertext differs from plaintext
        - Complete workflow functions correctly
        
        Note:
            Tests the simplified API most developers will use.
        """
        original = "my_secret_token"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)

        assert decrypted == original
        assert encrypted != original
