"""Integration tests for Bcrypt password hashing service.

Tests the BcryptPasswordService implementation with real bcrypt operations.
Following testing architecture: NO unit tests for infrastructure adapters,
only integration tests.

Architecture:
- Tests against real bcrypt library (no mocking)
- Tests cryptographic operations (hashing, verification)
- Tests security properties (salt uniqueness, timing resistance)
- Tests edge cases (invalid hashes, special characters)
"""

import pytest

from src.infrastructure.security.bcrypt_password_service import BcryptPasswordService


@pytest.mark.integration
class TestBcryptPasswordServiceIntegration:
    """Integration tests for Bcrypt password service.

    Uses real bcrypt library for cryptographic operations.
    No fixtures needed - service is stateless.
    """

    # =========================================================================
    # Password Hashing Tests
    # =========================================================================

    def test_hash_password_creates_bcrypt_hash(self):
        """Test that hashed password has valid bcrypt format."""
        service = BcryptPasswordService(cost_factor=12)
        password = "SecurePass123!"

        password_hash = service.hash_password(password)

        # Bcrypt format: $2b$12$...
        assert password_hash.startswith("$2b$12$")
        assert len(password_hash) == 60

    def test_hash_password_creates_unique_salts(self):
        """Test that hashing same password twice produces different hashes (unique salts)."""
        service = BcryptPasswordService(cost_factor=12)
        password = "SecurePass123!"

        hash1 = service.hash_password(password)
        hash2 = service.hash_password(password)

        # Hashes should be different (different salts)
        assert hash1 != hash2
        # But both should be valid bcrypt hashes
        assert len(hash1) == 60
        assert len(hash2) == 60
        assert hash1.startswith("$2b$")
        assert hash2.startswith("$2b$")

    def test_hash_password_handles_special_characters(self):
        """Test hashing password with special characters."""
        service = BcryptPasswordService()
        passwords_with_special_chars = [
            "Pass!@#$%^&*()",
            "Test<>?:\";'[]{}",
            "Password**||__++==",
            "🔐Secure🔑Pass🔓",
        ]

        for password in passwords_with_special_chars:
            password_hash = service.hash_password(password)

            assert password_hash.startswith("$2b$")
            assert len(password_hash) == 60
            # Verify we can validate with the hashed password
            assert service.verify_password(password, password_hash)

    def test_hash_password_handles_unicode(self):
        """Test hashing password with unicode characters."""
        service = BcryptPasswordService()
        unicode_passwords = [
            "Pässwörd123",  # German umlauts
            "パスワード",  # Japanese
            "密码123",  # Chinese
            "Contraseña",  # Spanish
        ]

        for password in unicode_passwords:
            password_hash = service.hash_password(password)

            assert password_hash.startswith("$2b$")
            assert len(password_hash) == 60
            # Verify roundtrip works
            assert service.verify_password(password, password_hash)

    def test_hash_password_with_different_cost_factors(self):
        """Test that different cost factors all produce valid hashes."""
        cost_factors = [10, 11, 12, 13]
        password = "TestPass123"

        hashes = []
        for cost in cost_factors:
            service = BcryptPasswordService(cost_factor=cost)
            password_hash = service.hash_password(password)

            # Verify format with correct cost factor
            assert password_hash.startswith(f"$2b${cost:02d}$")
            assert len(password_hash) == 60

            hashes.append(password_hash)

        # All hashes should be different (different salts)
        assert len(set(hashes)) == len(cost_factors)

    # =========================================================================
    # Password Verification Tests
    # =========================================================================

    def test_verify_password_success(self):
        """Test successful verification of correct password."""
        service = BcryptPasswordService()
        password = "TestPassword123!"

        password_hash = service.hash_password(password)

        # Correct password should verify
        assert service.verify_password(password, password_hash) is True

    def test_verify_password_failure_wrong_password(self):
        """Test that wrong password fails verification."""
        service = BcryptPasswordService()
        password = "CorrectPassword123"
        wrong_password = "WrongPassword456"

        password_hash = service.hash_password(password)

        # Wrong password should fail
        assert service.verify_password(wrong_password, password_hash) is False

    def test_verify_password_handles_invalid_hash(self):
        """Test that invalid hash format returns False (no exception)."""
        service = BcryptPasswordService()

        invalid_hashes = [
            "not_a_bcrypt_hash",
            "invalid_format_string",
            "1234567890",
            "$2b$invalid$rest",
        ]

        for invalid_hash in invalid_hashes:
            result = service.verify_password("password", invalid_hash)
            assert result is False  # Should not raise exception

    def test_verify_password_handles_empty_hash(self):
        """Test that empty hash returns False."""
        service = BcryptPasswordService()

        result = service.verify_password("password", "")

        assert result is False

    def test_verify_password_handles_non_bcrypt_hash(self):
        """Test that non-bcrypt hash (e.g., plain text) returns False."""
        service = BcryptPasswordService()
        password = "TestPassword"

        # Try to verify with plain text (not a hash)
        result = service.verify_password(password, password)

        assert result is False

    # =========================================================================
    # Edge Cases and Security Tests
    # =========================================================================

    def test_bcrypt_service_rejects_low_cost_factor(self):
        """Test that service rejects cost factor below minimum (10)."""
        with pytest.raises(ValueError) as exc_info:
            BcryptPasswordService(cost_factor=9)

        assert "at least 10" in str(exc_info.value).lower()

    def test_bcrypt_service_rejects_high_cost_factor(self):
        """Test that service rejects impractically high cost factor."""
        with pytest.raises(ValueError) as exc_info:
            BcryptPasswordService(cost_factor=21)

        assert "above 20" in str(exc_info.value).lower()
