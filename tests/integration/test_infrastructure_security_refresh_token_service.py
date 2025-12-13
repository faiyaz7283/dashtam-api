"""Integration tests for Refresh Token service.

Tests the RefreshTokenService implementation with real cryptographic operations.
Following testing architecture: NO unit tests for infrastructure adapters,
only integration tests.

Architecture:
- Tests against real secrets and bcrypt libraries (no mocking)
- Tests token generation and verification
- Tests security properties (uniqueness, format validation)
- Tests expiration calculation
"""

import pytest
from datetime import UTC, datetime
from freezegun import freeze_time

from src.infrastructure.security.refresh_token_service import RefreshTokenService


@pytest.mark.integration
class TestRefreshTokenServiceIntegration:
    """Integration tests for Refresh Token service.

    Uses real secrets/bcrypt libraries for cryptographic operations.
    No fixtures needed - service is stateless.
    """

    # =========================================================================
    # Token Generation Tests
    # =========================================================================

    def test_generate_token_creates_valid_tuple(self):
        """Test that generate_token returns (token, token_hash) tuple with valid formats."""
        service = RefreshTokenService(expiration_days=30)

        token, token_hash = service.generate_token()

        # Token should be urlsafe base64 (~43 chars for 32 bytes)
        assert isinstance(token, str)
        assert len(token) >= 40  # ~43 chars but allow some variance

        # Token hash should be bcrypt format
        assert isinstance(token_hash, str)
        assert token_hash.startswith("$2b$12$")
        assert len(token_hash) == 60

    def test_generate_token_creates_unique_tokens(self):
        """Test that multiple token generations produce unique tokens and hashes."""
        service = RefreshTokenService()

        # Generate 10 tokens
        results = [service.generate_token() for _ in range(10)]

        tokens = [r[0] for r in results]
        hashes = [r[1] for r in results]

        # All tokens should be unique
        assert len(set(tokens)) == 10

        # All hashes should be unique (different salts)
        assert len(set(hashes)) == 10

    def test_generate_token_creates_secure_length(self):
        """Test that generated token has secure length (32 bytes = 256 bits)."""
        service = RefreshTokenService()

        token, _ = service.generate_token()

        # 32 bytes base64-encoded is ~43 characters
        assert len(token) >= 43
        # Should be urlsafe base64 (no +, /, =)
        assert all(c.isalnum() or c in ["-", "_"] for c in token)

    def test_generate_token_hash_is_bcrypt(self):
        """Test that token hash uses bcrypt with cost factor 12."""
        service = RefreshTokenService()

        _, token_hash = service.generate_token()

        # Bcrypt format with cost 12
        assert token_hash.startswith("$2b$12$")
        assert len(token_hash) == 60

    # =========================================================================
    # Token Verification Tests
    # =========================================================================

    def test_verify_token_success(self):
        """Test successful verification of correct token."""
        service = RefreshTokenService()

        token, token_hash = service.generate_token()

        # Verify with original token
        assert service.verify_token(token, token_hash) is True

    def test_verify_token_failure_wrong_token(self):
        """Test that wrong token fails verification."""
        service = RefreshTokenService()

        token1, token_hash1 = service.generate_token()
        token2, _ = service.generate_token()

        # Verify token2 against token1's hash should fail
        assert service.verify_token(token2, token_hash1) is False

    def test_verify_token_handles_invalid_hash(self):
        """Test that invalid hash format returns False (no exception)."""
        service = RefreshTokenService()

        token, _ = service.generate_token()

        invalid_hashes = [
            "not_a_hash",
            "invalid_format",
            "$2b$invalid$",
            "",
        ]

        for invalid_hash in invalid_hashes:
            result = service.verify_token(token, invalid_hash)
            assert result is False

    def test_verify_token_handles_empty_token(self):
        """Test that empty token returns False."""
        service = RefreshTokenService()

        _, token_hash = service.generate_token()

        result = service.verify_token("", token_hash)

        assert result is False

    # =========================================================================
    # Expiration Calculation Tests
    # =========================================================================

    @freeze_time("2024-01-01 12:00:00")
    def test_calculate_expiration_returns_future_time(self):
        """Test that calculate_expiration returns time in future."""
        service = RefreshTokenService(expiration_days=30)

        expires_at = service.calculate_expiration()

        # Expiration should be exactly 30 days from frozen time
        expected_expiration = datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC)
        assert expires_at == expected_expiration

        # Should be UTC timezone
        assert expires_at.tzinfo == UTC

    @freeze_time("2024-01-01 12:00:00")
    def test_calculate_expiration_with_custom_days(self):
        """Test that expiration reflects configured expiration_days."""
        test_cases = [
            (7, 7),  # 1 week
            (14, 14),  # 2 weeks
            (30, 30),  # 30 days (default)
            (90, 90),  # 3 months
        ]

        frozen_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        for days, expected_days in test_cases:
            service = RefreshTokenService(expiration_days=days)
            expires_at = service.calculate_expiration()

            delta = expires_at - frozen_time

            # Exact match (no tolerance needed with frozen time)
            assert delta.days == expected_days
            assert delta.total_seconds() == expected_days * 24 * 60 * 60
