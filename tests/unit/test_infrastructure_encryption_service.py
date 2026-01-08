"""Unit tests for EncryptionService.

Tests cover:
- Factory create() with valid/invalid key lengths
- Encrypt/decrypt round-trip for various payloads
- Tamper detection (ciphertext and auth tag alteration)
- Edge cases (empty dict, large payloads, special characters)

Architecture:
- Pure unit tests (no external dependencies)
- Uses Result pattern (Success/Failure)
- Tests domain error types (EncryptionKeyError, DecryptionError, etc.)
"""

from typing import Any
import os

import pytest

from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.infrastructure.providers.encryption_service import (
    DecryptionError,
    EncryptionKeyError,
    EncryptionService,
    SerializationError,
)


# =============================================================================
# Test Constants
# =============================================================================

VALID_KEY = os.urandom(32)  # 256 bits
SHORT_KEY = os.urandom(16)  # 128 bits (too short)
LONG_KEY = os.urandom(64)  # 512 bits (too long)


# =============================================================================
# Test: Factory Creation
# =============================================================================


class TestEncryptionServiceCreate:
    """Test EncryptionService.create() factory method."""

    def test_create_with_valid_key_returns_success(self):
        """Valid 32-byte key should create service successfully."""
        result = EncryptionService.create(VALID_KEY)

        assert isinstance(result, Success)
        assert isinstance(result.value, EncryptionService)

    def test_create_with_short_key_returns_failure(self):
        """Key shorter than 32 bytes should fail."""
        result = EncryptionService.create(SHORT_KEY)

        assert isinstance(result, Failure)
        assert isinstance(result.error, EncryptionKeyError)
        assert result.error.code == ErrorCode.ENCRYPTION_KEY_INVALID
        assert result.error.details is not None
        assert "16 bytes" in result.error.message
        assert result.error.details["actual_length"] == "16"
        assert result.error.details["expected_length"] == "32"

    def test_create_with_long_key_returns_failure(self):
        """Key longer than 32 bytes should fail."""
        result = EncryptionService.create(LONG_KEY)

        assert isinstance(result, Failure)
        assert isinstance(result.error, EncryptionKeyError)
        assert "64 bytes" in result.error.message

    def test_create_with_empty_key_returns_failure(self):
        """Empty key should fail."""
        result = EncryptionService.create(b"")

        assert isinstance(result, Failure)
        assert isinstance(result.error, EncryptionKeyError)
        assert "0 bytes" in result.error.message


# =============================================================================
# Test: Encrypt/Decrypt Round-Trip
# =============================================================================


class TestEncryptionRoundTrip:
    """Test encrypt() and decrypt() produce identical data."""

    @pytest.fixture
    def service(self):
        """Provide valid encryption service."""
        result = EncryptionService.create(VALID_KEY)
        assert isinstance(result, Success)
        return result.value

    def test_roundtrip_simple_credentials(self, service):
        """Simple credentials should survive encrypt/decrypt cycle."""
        credentials = {
            "access_token": "abc123",
            "refresh_token": "xyz789",
        }

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)
        encrypted = encrypt_result.value

        decrypt_result = service.decrypt(encrypted)
        assert isinstance(decrypt_result, Success)
        assert decrypt_result.value == credentials

    def test_roundtrip_oauth_tokens(self, service):
        """Full OAuth token payload should roundtrip correctly."""
        credentials = {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
            "refresh_token": "rt_1234567890abcdef",
            "expires_in": 1800,
            "token_type": "Bearer",
            "scope": "api read write",
        }

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)

        decrypt_result = service.decrypt(encrypt_result.value)
        assert isinstance(decrypt_result, Success)
        assert decrypt_result.value == credentials

    def test_roundtrip_empty_dict(self, service):
        """Empty dict should roundtrip correctly."""
        credentials: dict[str, Any] = {}

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)

        decrypt_result = service.decrypt(encrypt_result.value)
        assert isinstance(decrypt_result, Success)
        assert decrypt_result.value == {}

    def test_roundtrip_nested_data(self, service):
        """Nested structures should roundtrip correctly."""
        credentials = {
            "tokens": {
                "access": "at123",
                "refresh": "rt456",
            },
            "metadata": {
                "provider": "schwab",
                "scopes": ["read", "write", "trade"],
            },
        }

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)

        decrypt_result = service.decrypt(encrypt_result.value)
        assert isinstance(decrypt_result, Success)
        assert decrypt_result.value == credentials

    def test_roundtrip_special_characters(self, service):
        """Special characters should roundtrip correctly."""
        credentials = {
            "token": "abc+/=123",
            "unicode": "日本語テスト",
            "emoji": "🔐🔑",
            "escaped": "line1\nline2\ttab",
        }

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)

        decrypt_result = service.decrypt(encrypt_result.value)
        assert isinstance(decrypt_result, Success)
        assert decrypt_result.value == credentials

    def test_roundtrip_large_payload(self, service):
        """Large payloads should roundtrip correctly."""
        # Simulate large response with position data
        credentials = {
            "access_token": "a" * 2000,  # Long token
            "positions": [{"symbol": f"SYM{i}", "qty": i * 100} for i in range(100)],
        }

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)

        decrypt_result = service.decrypt(encrypt_result.value)
        assert isinstance(decrypt_result, Success)
        assert decrypt_result.value == credentials

    def test_unique_iv_per_encryption(self, service):
        """Each encryption should produce different ciphertext (unique IV)."""
        credentials = {"token": "same_value"}

        # Encrypt same data twice
        result1 = service.encrypt(credentials)
        result2 = service.encrypt(credentials)

        assert isinstance(result1, Success)
        assert isinstance(result2, Success)

        # Ciphertexts should be different (different IVs)
        assert result1.value != result2.value

        # But both should decrypt to same value
        decrypt1 = service.decrypt(result1.value)
        decrypt2 = service.decrypt(result2.value)

        assert isinstance(decrypt1, Success)
        assert isinstance(decrypt2, Success)
        assert decrypt1.value == decrypt2.value == credentials


# =============================================================================
# Test: Tamper Detection
# =============================================================================


class TestTamperDetection:
    """Test that tampering is detected via GCM auth tag."""

    @pytest.fixture
    def service(self):
        """Provide valid encryption service."""
        result = EncryptionService.create(VALID_KEY)
        assert isinstance(result, Success)
        return result.value

    def test_tampered_ciphertext_detected(self, service):
        """Altering ciphertext should fail decryption."""
        credentials = {"access_token": "secret_value"}

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)
        encrypted = bytearray(encrypt_result.value)

        # Tamper with ciphertext (after IV, before auth tag)
        if len(encrypted) > 20:
            encrypted[15] ^= 0xFF  # Flip bits in ciphertext

        decrypt_result = service.decrypt(bytes(encrypted))

        assert isinstance(decrypt_result, Failure)
        assert isinstance(decrypt_result.error, DecryptionError)
        assert decrypt_result.error.code == ErrorCode.DECRYPTION_FAILED
        assert "tampered" in decrypt_result.error.message.lower()

    def test_tampered_auth_tag_detected(self, service):
        """Altering auth tag should fail decryption."""
        credentials = {"refresh_token": "rt_12345"}

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)
        encrypted = bytearray(encrypt_result.value)

        # Tamper with last byte (auth tag)
        encrypted[-1] ^= 0xFF

        decrypt_result = service.decrypt(bytes(encrypted))

        assert isinstance(decrypt_result, Failure)
        assert isinstance(decrypt_result.error, DecryptionError)

    def test_tampered_iv_detected(self, service):
        """Altering IV should fail decryption."""
        credentials = {"token": "value123"}

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)
        encrypted = bytearray(encrypt_result.value)

        # Tamper with IV (first 12 bytes)
        encrypted[0] ^= 0xFF

        decrypt_result = service.decrypt(bytes(encrypted))

        assert isinstance(decrypt_result, Failure)
        assert isinstance(decrypt_result.error, DecryptionError)

    def test_truncated_data_detected(self, service):
        """Truncated ciphertext should fail."""
        credentials = {"token": "value"}

        encrypt_result = service.encrypt(credentials)
        assert isinstance(encrypt_result, Success)
        encrypted = encrypt_result.value

        # Truncate (remove last 8 bytes)
        truncated = encrypted[:-8]

        decrypt_result = service.decrypt(truncated)

        assert isinstance(decrypt_result, Failure)
        assert isinstance(decrypt_result.error, DecryptionError)


# =============================================================================
# Test: Error Conditions
# =============================================================================


class TestEncryptionErrors:
    """Test error handling in encryption/decryption."""

    @pytest.fixture
    def service(self):
        """Provide valid encryption service."""
        result = EncryptionService.create(VALID_KEY)
        assert isinstance(result, Success)
        return result.value

    def test_decrypt_too_short_data(self, service):
        """Data shorter than MIN_ENCRYPTED_SIZE should fail."""
        # MIN_ENCRYPTED_SIZE is 28 bytes (12 IV + 16 auth tag)
        short_data = b"too_short"

        result = service.decrypt(short_data)

        assert isinstance(result, Failure)
        assert isinstance(result.error, DecryptionError)
        assert result.error.code == ErrorCode.INVALID_INPUT
        assert "too short" in result.error.message

    def test_decrypt_empty_data(self, service):
        """Empty bytes should fail decryption."""
        result = service.decrypt(b"")

        assert isinstance(result, Failure)
        assert isinstance(result.error, DecryptionError)
        assert "0 bytes" in result.error.message

    def test_decrypt_wrong_key(self):
        """Decryption with different key should fail."""
        key1 = os.urandom(32)
        key2 = os.urandom(32)

        service1_result = EncryptionService.create(key1)
        service2_result = EncryptionService.create(key2)

        assert isinstance(service1_result, Success)
        assert isinstance(service2_result, Success)

        service1 = service1_result.value
        service2 = service2_result.value

        # Encrypt with key1
        credentials = {"token": "secret"}
        encrypt_result = service1.encrypt(credentials)
        assert isinstance(encrypt_result, Success)

        # Decrypt with key2 (wrong key)
        decrypt_result = service2.decrypt(encrypt_result.value)

        assert isinstance(decrypt_result, Failure)
        assert isinstance(decrypt_result.error, DecryptionError)
        assert decrypt_result.error.code == ErrorCode.DECRYPTION_FAILED

    def test_encrypt_non_serializable_data(self, service):
        """Non-JSON-serializable data should fail encryption."""
        # Sets are not JSON serializable
        credentials: dict[str, Any] = {"items": {1, 2, 3}}

        result = service.encrypt(credentials)

        assert isinstance(result, Failure)
        assert isinstance(result.error, SerializationError)
        assert result.error.code == ErrorCode.INVALID_INPUT
        assert "serialize" in result.error.message.lower()

    def test_encrypt_circular_reference(self, service):
        """Circular references should fail encryption."""
        credentials: dict[str, Any] = {"self": None}
        credentials["self"] = credentials  # Circular reference

        result = service.encrypt(credentials)

        assert isinstance(result, Failure)
        assert isinstance(result.error, SerializationError)


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_service_is_reusable(self):
        """Service instance can be used multiple times."""
        result = EncryptionService.create(VALID_KEY)
        assert isinstance(result, Success)
        service = result.value

        # Use same service multiple times
        for i in range(10):
            creds = {"iteration": i}
            enc = service.encrypt(creds)
            assert isinstance(enc, Success)
            dec = service.decrypt(enc.value)
            assert isinstance(dec, Success)
            assert dec.value == creds

    def test_numeric_values_preserved(self):
        """Numeric types are preserved through JSON serialization."""
        result = EncryptionService.create(VALID_KEY)
        assert isinstance(result, Success)
        service = result.value

        credentials = {
            "expires_in": 1800,
            "balance": 12345.67,
            "count": 0,
            "negative": -100,
        }

        enc = service.encrypt(credentials)
        assert isinstance(enc, Success)

        dec = service.decrypt(enc.value)
        assert isinstance(dec, Success)
        assert dec.value == credentials

    def test_null_values_preserved(self):
        """Null values are preserved."""
        result = EncryptionService.create(VALID_KEY)
        assert isinstance(result, Success)
        service = result.value

        credentials = {
            "access_token": "at",
            "refresh_token": None,
            "scope": None,
        }

        enc = service.encrypt(credentials)
        assert isinstance(enc, Success)

        dec = service.decrypt(enc.value)
        assert isinstance(dec, Success)
        assert dec.value == credentials
        assert dec.value["refresh_token"] is None

    def test_boolean_values_preserved(self):
        """Boolean values are preserved."""
        result = EncryptionService.create(VALID_KEY)
        assert isinstance(result, Success)
        service = result.value

        credentials = {
            "active": True,
            "expired": False,
        }

        enc = service.encrypt(credentials)
        assert isinstance(enc, Success)

        dec = service.decrypt(enc.value)
        assert isinstance(dec, Success)
        assert dec.value["active"] is True
        assert dec.value["expired"] is False
