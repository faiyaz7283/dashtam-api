"""Integration tests for Password Reset Token service.

Tests the PasswordResetTokenService implementation with real cryptographic operations.
Following testing architecture: NO unit tests for infrastructure adapters,
only integration tests.

Architecture:
- Tests against real secrets library (no mocking)
- Tests token generation with hexadecimal format
- Tests expiration calculation (short-lived for security)
- Tests security properties (uniqueness, format validation)
"""

import pytest
from datetime import UTC, datetime
from freezegun import freeze_time

from src.infrastructure.security.password_reset_token_service import (
    PasswordResetTokenService,
)


@pytest.mark.integration
class TestPasswordResetTokenServiceIntegration:
    """Integration tests for Password Reset Token service.

    Uses real secrets library for cryptographic operations.
    No fixtures needed - service is stateless.
    """

    def test_generate_reset_token_creates_valid_token(self):
        """Test that generated token has correct format and length."""
        service = PasswordResetTokenService(expiration_minutes=15)

        token = service.generate_token()

        # Token should be 64 hex characters (32 bytes)
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_reset_token_creates_unique_tokens(self):
        """Test that multiple generations produce unique tokens."""
        service = PasswordResetTokenService()

        # Generate 20 tokens
        tokens = [service.generate_token() for _ in range(20)]

        # All should be unique
        assert len(set(tokens)) == 20

    def test_reset_token_has_high_entropy(self):
        """Test that token has sufficient entropy (32 bytes = 256 bits)."""
        service = PasswordResetTokenService()

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

    def test_reset_token_handles_edge_cases(self):
        """Test token generation handles various edge cases."""
        service = PasswordResetTokenService()

        # Generate many tokens rapidly
        tokens = [service.generate_token() for _ in range(100)]

        # All should be valid hex and unique
        assert all(len(t) == 64 for t in tokens)
        assert all(all(c in "0123456789abcdef" for c in t) for t in tokens)
        assert len(set(tokens)) == 100  # All unique

    @freeze_time("2024-01-01 12:00:00")
    def test_calculate_expiration_returns_correct_time(self):
        """Test that expiration calculation returns correct UTC time (15 minutes)."""
        expiration_minutes = 15
        service = PasswordResetTokenService(expiration_minutes=expiration_minutes)

        expires_at = service.calculate_expiration()

        # Expiration should be exactly 15 minutes from frozen time
        expected_expiration = datetime(2024, 1, 1, 12, 15, 0, tzinfo=UTC)
        assert expires_at == expected_expiration

        # Should be UTC timezone
        assert expires_at.tzinfo == UTC

    @freeze_time("2024-01-01 12:00:00")
    def test_reset_token_service_initialization(self):
        """Test service initialization with various parameters."""
        # Default expiration (15 minutes)
        service_default = PasswordResetTokenService()
        token_default = service_default.generate_token()
        assert len(token_default) == 64

        # Custom expiration times (in minutes)
        test_cases = [5, 10, 15, 30, 60]

        frozen_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        for minutes in test_cases:
            service = PasswordResetTokenService(expiration_minutes=minutes)
            expires_at = service.calculate_expiration()

            delta = expires_at - frozen_time

            # Exact match (no tolerance needed with frozen time)
            assert delta.total_seconds() == minutes * 60

    def test_reset_token_format_consistency(self):
        """Test that token format is consistent across multiple generations."""
        service = PasswordResetTokenService()

        tokens = [service.generate_token() for _ in range(50)]

        for token in tokens:
            # All tokens should be 64 characters
            assert len(token) == 64
            # All should be lowercase hex
            assert token == token.lower()
            assert all(c in "0123456789abcdef" for c in token)

    @freeze_time("2024-01-01 12:00:00")
    def test_calculate_expiration_with_different_durations(self):
        """Test expiration calculation with various durations."""
        test_durations = [
            (5, 300),  # 5 minutes = 300 seconds
            (10, 600),  # 10 minutes
            (15, 900),  # 15 minutes (default)
            (30, 1800),  # 30 minutes
            (60, 3600),  # 60 minutes = 1 hour
        ]

        frozen_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        for minutes, expected_seconds in test_durations:
            service = PasswordResetTokenService(expiration_minutes=minutes)
            expires_at = service.calculate_expiration()

            delta = (expires_at - frozen_time).total_seconds()

            # Exact match (no tolerance needed with frozen time)
            assert delta == expected_seconds
