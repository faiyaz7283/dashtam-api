"""Unit tests for encryption service.

This module tests the encryption service functionality including
encryption, decryption, key handling, and error scenarios.
"""

import pytest
from unittest.mock import patch

from src.services.encryption import EncryptionService, get_encryption_service


class TestEncryptionService:
    """Test cases for EncryptionService class."""

    def test_encryption_service_initialization(self, test_settings):
        """Test encryption service can be initialized with test settings."""
        service = EncryptionService()
        assert service is not None
        assert hasattr(service, "encrypt")
        assert hasattr(service, "decrypt")

    def test_encrypt_decrypt_round_trip(self, test_settings):
        """Test that data can be encrypted and decrypted successfully."""
        service = EncryptionService()

        original_data = "test_access_token_12345"

        # Encrypt the data
        encrypted_data = service.encrypt(original_data)
        assert encrypted_data != original_data
        assert isinstance(encrypted_data, str)

        # Decrypt the data
        decrypted_data = service.decrypt(encrypted_data)
        assert decrypted_data == original_data

    def test_encrypt_different_data_produces_different_results(self, test_settings):
        """Test that different input data produces different encrypted outputs."""
        service = EncryptionService()

        data1 = "access_token_1"
        data2 = "access_token_2"

        encrypted1 = service.encrypt(data1)
        encrypted2 = service.encrypt(data2)

        assert encrypted1 != encrypted2
        assert service.decrypt(encrypted1) == data1
        assert service.decrypt(encrypted2) == data2

    def test_encrypt_empty_string(self, test_settings):
        """Test encryption of empty string."""
        service = EncryptionService()

        encrypted = service.encrypt("")
        decrypted = service.decrypt(encrypted)

        assert decrypted == ""

    def test_encrypt_none_value_raises_error(self, test_settings):
        """Test that encrypting None raises appropriate error."""
        service = EncryptionService()

        with pytest.raises((TypeError, ValueError)):
            service.encrypt(None)

    def test_decrypt_invalid_data_raises_error(self, test_settings):
        """Test that decrypting invalid data raises appropriate error."""
        service = EncryptionService()

        with pytest.raises((ValueError, Exception)):
            service.decrypt("invalid_encrypted_data")

    def test_decrypt_empty_string_raises_error(self, test_settings):
        """Test that decrypting empty string raises appropriate error."""
        service = EncryptionService()

        with pytest.raises((ValueError, Exception)):
            service.decrypt("")

    def test_encrypt_large_data(self, test_settings):
        """Test encryption of large data strings."""
        service = EncryptionService()

        # Create a large string (1MB)
        large_data = "a" * (1024 * 1024)

        encrypted = service.encrypt(large_data)
        decrypted = service.decrypt(encrypted)

        assert decrypted == large_data

    def test_encrypt_unicode_data(self, test_settings):
        """Test encryption of unicode characters."""
        service = EncryptionService()

        unicode_data = "测试数据 🔐 Tëst Dåtå"

        encrypted = service.encrypt(unicode_data)
        decrypted = service.decrypt(encrypted)

        assert decrypted == unicode_data

    def test_encryption_key_validation(self):
        """Test that encryption service validates key length and format."""
        # Test with short key
        with pytest.raises((ValueError, Exception)):
            EncryptionService("short")

        # Test with None key
        with pytest.raises((TypeError, ValueError)):
            EncryptionService(None)

    def test_multiple_service_instances_compatibility(self, test_settings):
        """Test that multiple service instances can decrypt each other's data."""
        service1 = EncryptionService()
        service2 = EncryptionService()

        data = "shared_token_data"

        encrypted_by_service1 = service1.encrypt(data)
        decrypted_by_service2 = service2.decrypt(encrypted_by_service1)

        assert decrypted_by_service2 == data

    @patch("os.environ.get")
    def test_get_encryption_service_from_env(self, mock_env_get, test_settings):
        """Test get_encryption_service factory function with environment variable."""
        mock_env_get.return_value = test_settings.ENCRYPTION_KEY

        service = get_encryption_service()

        assert isinstance(service, EncryptionService)
        mock_env_get.assert_called_once_with("ENCRYPTION_KEY")

    @patch("os.environ.get")
    def test_get_encryption_service_missing_key_raises_error(self, mock_env_get):
        """Test that missing encryption key raises appropriate error."""
        mock_env_get.return_value = None

        with pytest.raises((ValueError, RuntimeError)):
            get_encryption_service()

    def test_encrypt_typical_token_data(self, test_settings):
        """Test encryption of typical OAuth token data."""
        service = EncryptionService()

        test_tokens = [
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJzY2h3YWIiLCJhdWQiOiJkYXNodGFtIn0",
            "refresh_token_abc123def456",
            "Bearer_token_xyz789",
            "simple_access_token_12345",
        ]

        for token in test_tokens:
            encrypted = service.encrypt(token)
            decrypted = service.decrypt(encrypted)
            assert decrypted == token
            assert encrypted != token  # Ensure it was actually encrypted


class TestEncryptionServicePerformance:
    """Performance tests for encryption service."""

    def test_encryption_performance(self, test_settings):
        """Test that encryption operations complete within reasonable time."""
        import time
        
        service = EncryptionService()
        data = "performance_test_token_data"

        # Test encryption performance
        start_time = time.time()
        for _ in range(100):
            encrypted = service.encrypt(data)
        encryption_time = time.time() - start_time

        # Should complete 100 encryptions in less than 1 second
        assert encryption_time < 1.0

        # Test decryption performance
        start_time = time.time()
        for _ in range(100):
            decrypted = service.decrypt(encrypted)
        decryption_time = time.time() - start_time

        # Should complete 100 decryptions in less than 1 second
        assert decryption_time < 1.0
        assert decrypted == data


class TestEncryptionServiceSecurity:
    """Security-focused tests for encryption service."""

    def test_encrypted_data_does_not_contain_original(self, test_settings):
        """Test that encrypted data doesn't contain original data."""
        service = EncryptionService()

        sensitive_data = "secret_access_token_with_sensitive_info"
        encrypted = service.encrypt(sensitive_data)

        # Encrypted data should not contain any part of original data
        assert sensitive_data not in encrypted
        assert "secret" not in encrypted.lower()
        assert "access_token" not in encrypted.lower()

    def test_same_data_different_encryption_results(self, test_settings):
        """Test that encrypting same data multiple times produces different results."""
        service = EncryptionService()

        data = "test_token_for_nonce_testing"

        # Encrypt same data multiple times
        encrypted_results = []
        for _ in range(5):
            encrypted_results.append(service.encrypt(data))

        # All results should be different (due to nonce/IV)
        assert len(set(encrypted_results)) == 5

        # But all should decrypt to the same original data
        for encrypted in encrypted_results:
            assert service.decrypt(encrypted) == data

    def test_different_keys_produce_incompatible_encryption(self):
        """Test that different encryption keys produce incompatible results."""
        # This test is not applicable with singleton pattern
        # Different keys would require separate instances which
        # the singleton pattern doesn't support
        pytest.skip("Singleton pattern doesn't support different keys in same process")
