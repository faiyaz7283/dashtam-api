"""Integration tests for Email Verification Token service.

Tests the EmailVerificationTokenService implementation with real cryptographic operations.
Following testing architecture: NO unit tests for infrastructure adapters,
only integration tests.

Architecture:
- Tests against real secrets library (no mocking)
- Tests token generation with hexadecimal format
- Tests expiration calculation
- Tests security properties (uniqueness, format validation)
"""

import pytest
from datetime import UTC, datetime, timedelta

from src.infrastructure.security.email_verification_token_service import (
    EmailVerificationTokenService,
)


@pytest.mark.integration
class TestEmailVerificationTokenServiceIntegration:
    """Integration tests for Email Verification Token service.

    Uses real secrets library for cryptographic operations.
    No fixtures needed - service is stateless.
    """

    def test_generate_verification_token_creates_valid_token(self):
        """Test that generated token has correct format and length."""
        service = EmailVerificationTokenService(expiration_hours=24)

        token = service.generate_token()

        # Token should be 64 hex characters (32 bytes)
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_verification_token_creates_unique_tokens(self):
        """Test that multiple generations produce unique tokens."""
        service = EmailVerificationTokenService()

        # Generate 20 tokens
        tokens = [service.generate_token() for _ in range(20)]

        # All should be unique
        assert len(set(tokens)) == 20

    def test_verification_token_has_high_entropy(self):
        """Test that token has sufficient entropy (32 bytes = 256 bits)."""
        service = EmailVerificationTokenService()

        token = service.generate_token()

        # 32 bytes = 256 bits of entropy
        # When encoded as hex, each byte = 2 characters
        # So 32 bytes = 64 hex characters
        assert len(token) == 64

        # All possible hex digits should appear in a sample of tokens
        all_chars = set()
        for _ in range(100):
            all_chars.update(set(service.generate_token()))

        # Should have all 16 hex digits
        expected_chars = set("0123456789abcdef")
        assert all_chars == expected_chars

    def test_verification_token_handles_edge_cases(self):
        """Test token generation handles various edge cases."""
        service = EmailVerificationTokenService()

        # Generate many tokens rapidly
        tokens = [service.generate_token() for _ in range(100)]

        # All should be valid hex and unique
        assert all(len(t) == 64 for t in tokens)
        assert all(all(c in "0123456789abcdef" for c in t) for t in tokens)
        assert len(set(tokens)) == 100  # All unique

    def test_calculate_expiration_returns_correct_time(self):
        """Test that expiration calculation returns correct UTC time."""
        expiration_hours = 24
        service = EmailVerificationTokenService(expiration_hours=expiration_hours)

        before = datetime.now(UTC)
        expires_at = service.calculate_expiration()
        after = datetime.now(UTC)

        # Expiration should be ~24 hours from now
        expected_expiration = before + timedelta(hours=expiration_hours)

        # Allow 1 second tolerance
        assert expires_at >= expected_expiration - timedelta(seconds=1)
        assert expires_at <= after + timedelta(hours=expiration_hours) + timedelta(
            seconds=1
        )

        # Should be UTC timezone
        assert expires_at.tzinfo == UTC

    def test_verification_token_service_initialization(self):
        """Test service initialization with various parameters."""
        # Default expiration (24 hours)
        service_default = EmailVerificationTokenService()
        token_default = service_default.generate_token()
        assert len(token_default) == 64

        # Custom expiration times
        test_cases = [1, 6, 12, 24, 48, 72]  # hours

        for hours in test_cases:
            service = EmailVerificationTokenService(expiration_hours=hours)

            before = datetime.now(UTC)
            expires_at = service.calculate_expiration()

            delta = expires_at - before

            # Allow 1 second tolerance
            assert abs(delta.total_seconds() - (hours * 3600)) < 2

    def test_verification_token_format_consistency(self):
        """Test that token format is consistent across multiple generations."""
        service = EmailVerificationTokenService()

        tokens = [service.generate_token() for _ in range(50)]

        for token in tokens:
            # All tokens should be 64 characters
            assert len(token) == 64
            # All should be lowercase hex
            assert token == token.lower()
            assert all(c in "0123456789abcdef" for c in token)

    def test_calculate_expiration_with_different_durations(self):
        """Test expiration calculation with various durations."""
        test_durations = [
            (1, 3600),  # 1 hour = 3600 seconds
            (6, 21600),  # 6 hours
            (24, 86400),  # 24 hours
            (48, 172800),  # 48 hours
        ]

        for hours, expected_seconds in test_durations:
            service = EmailVerificationTokenService(expiration_hours=hours)

            before = datetime.now(UTC)
            expires_at = service.calculate_expiration()

            delta = (expires_at - before).total_seconds()

            # Allow 1 second tolerance
            assert abs(delta - expected_seconds) < 2
