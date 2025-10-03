"""Unit tests for encryption service.

These tests verify the encryption/decryption functionality without
any database or external dependencies. They are fast and isolated.
"""

import pytest

from src.services.encryption import EncryptionService


class TestEncryptionService:
    """Test suite for EncryptionService."""

    def test_encrypt_decrypt_string(self):
        """Test encrypting and decrypting a simple string."""
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
        """Test encrypting an empty string."""
        service = EncryptionService()

        encrypted = service.encrypt("")
        assert encrypted == ""

        decrypted = service.decrypt("")
        assert decrypted == ""

    def test_encrypt_unicode_string(self):
        """Test encrypting strings with unicode characters."""
        service = EncryptionService()
        plaintext = "Hello 世界 🌍 café"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_long_string(self):
        """Test encrypting a long string."""
        service = EncryptionService()
        plaintext = "a" * 10000

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext
        assert len(encrypted) > len(plaintext)

    def test_encrypt_dict(self):
        """Test encrypting a dictionary with string values."""
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
        """Test checking if a string is encrypted."""
        service = EncryptionService()

        plaintext = "not_encrypted"
        encrypted = service.encrypt(plaintext)

        assert not service.is_encrypted(plaintext)
        assert service.is_encrypted(encrypted)
        assert not service.is_encrypted("")

    def test_singleton_pattern(self):
        """Test that EncryptionService follows singleton pattern."""
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
        """Test that decrypting invalid data raises an exception."""
        service = EncryptionService()

        with pytest.raises(Exception, match="Failed to decrypt data"):
            service.decrypt("not_a_valid_encrypted_string")

    def test_different_encryptions_same_plaintext(self):
        """Test that encrypting the same plaintext twice produces different ciphertexts."""
        service = EncryptionService()
        plaintext = "same_token"

        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)

        # Should be different due to nonce/IV
        assert encrypted1 != encrypted2

        # But both should decrypt to same plaintext
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext
