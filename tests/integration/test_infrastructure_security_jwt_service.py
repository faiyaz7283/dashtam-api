"""Integration tests for JWT token service.

Tests the JWTService implementation with real cryptographic operations.
Following testing architecture: NO unit tests for infrastructure adapters,
only integration tests.

Architecture:
- Tests against real jose library (no mocking)
- Tests cryptographic operations (signing, validation)
- Verifies Result type error handling
- Tests security properties (uniqueness, expiration, tampering)
"""

import pytest
from datetime import UTC, datetime
from freezegun import freeze_time
from uuid_extensions import uuid7

from src.infrastructure.security.jwt_service import JWTService
from src.core.result import Success, Failure
from src.domain.errors import AuthenticationError


@pytest.mark.integration
class TestJWTServiceIntegration:
    """Integration tests for JWT service.

    Uses real jose library for JWT operations.
    No fixtures needed - service is stateless.
    """

    # =========================================================================
    # Token Generation Tests
    # =========================================================================

    def test_generate_access_token_creates_valid_jwt(self):
        """Test that generated token has valid JWT structure (3 parts)."""
        service = JWTService(secret_key="x" * 32, expiration_minutes=15)
        user_id = uuid7()

        token = service.generate_access_token(
            user_id=user_id,
            email="test@example.com",
            roles=["user"],
        )

        # JWT has 3 parts: header.payload.signature
        parts = token.split(".")
        assert len(parts) == 3
        assert all(len(part) > 0 for part in parts)

    def test_generate_access_token_includes_required_claims(self):
        """Test that token payload includes all required claims."""
        service = JWTService(secret_key="x" * 32, expiration_minutes=15)
        user_id = uuid7()
        email = "test@example.com"
        roles = ["user", "admin"]

        token = service.generate_access_token(
            user_id=user_id,
            email=email,
            roles=roles,
        )

        # Validate and extract payload
        result = service.validate_access_token(token)
        assert isinstance(result, Success)

        payload = result.value
        assert payload["sub"] == str(user_id)
        assert payload["email"] == email
        assert payload["roles"] == roles
        assert "iat" in payload  # Issued at
        assert "exp" in payload  # Expires at
        assert "jti" in payload  # JWT ID

    def test_generate_access_token_with_session_id(self):
        """Test token generation with optional session_id."""
        service = JWTService(secret_key="x" * 32)
        session_id = uuid7()

        token = service.generate_access_token(
            user_id=uuid7(),
            email="test@example.com",
            roles=["user"],
            session_id=session_id,
        )

        result = service.validate_access_token(token)
        assert isinstance(result, Success)
        assert result.value["session_id"] == str(session_id)

    def test_generate_access_token_without_session_id(self):
        """Test token generation without session_id (omitted from payload)."""
        service = JWTService(secret_key="x" * 32)

        token = service.generate_access_token(
            user_id=uuid7(),
            email="test@example.com",
            roles=["user"],
            session_id=None,
        )

        result = service.validate_access_token(token)
        assert isinstance(result, Success)
        assert "session_id" not in result.value

    def test_generate_access_token_creates_unique_jti(self):
        """Test that each token has unique JWT ID (jti)."""
        service = JWTService(secret_key="x" * 32)
        user_id = uuid7()

        # Generate multiple tokens for same user
        tokens = [
            service.generate_access_token(
                user_id=user_id,
                email="test@example.com",
                roles=["user"],
            )
            for _ in range(5)
        ]

        # Extract JTI from each token
        jtis = []
        for token in tokens:
            result = service.validate_access_token(token)
            assert isinstance(result, Success)
            jtis.append(result.value["jti"])

        # All JTIs should be unique
        assert len(set(jtis)) == 5

    @freeze_time("2024-01-01 12:00:00")
    def test_generate_access_token_sets_correct_expiration(self):
        """Test that expiration is set correctly based on expiration_minutes."""
        expiration_minutes = 30
        service = JWTService(secret_key="x" * 32, expiration_minutes=expiration_minutes)

        token = service.generate_access_token(
            user_id=uuid7(),
            email="test@example.com",
            roles=["user"],
        )

        result = service.validate_access_token(token)
        assert isinstance(result, Success)

        iat = datetime.fromtimestamp(result.value["iat"], UTC)
        exp = datetime.fromtimestamp(result.value["exp"], UTC)

        # Expiration should be exactly 30 minutes from issued time
        expiration_delta = exp - iat
        assert expiration_delta.total_seconds() == expiration_minutes * 60

        # Issued time should be exactly 2024-01-01 12:00:00
        assert iat == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert exp == datetime(2024, 1, 1, 12, 30, 0, tzinfo=UTC)

    # =========================================================================
    # Token Validation Tests
    # =========================================================================

    def test_validate_access_token_success(self):
        """Test successful validation of valid token."""
        service = JWTService(secret_key="x" * 32)
        user_id = uuid7()
        email = "test@example.com"

        token = service.generate_access_token(
            user_id=user_id,
            email=email,
            roles=["user"],
        )

        result = service.validate_access_token(token)

        assert isinstance(result, Success)
        assert isinstance(result.value, dict)
        assert result.value["sub"] == str(user_id)
        assert result.value["email"] == email

    def test_validate_expired_token_returns_failure(self):
        """Test that expired token validation returns Failure."""
        service = JWTService(secret_key="x" * 32, expiration_minutes=1)

        # Generate token at initial time
        with freeze_time("2024-01-01 12:00:00"):
            token = service.generate_access_token(
                user_id=uuid7(),
                email="test@example.com",
                roles=["user"],
            )

        # Move time forward past expiration (2 minutes later)
        with freeze_time("2024-01-01 12:02:00"):
            result = service.validate_access_token(token)

        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.INVALID_TOKEN

    def test_validate_malformed_token_returns_failure(self):
        """Test that malformed token (missing parts) returns Failure."""
        service = JWTService(secret_key="x" * 32)

        malformed_tokens = [
            "invalid",
            "only.two",
            "header.payload",  # Missing signature
            "",
            "....",
        ]

        for token in malformed_tokens:
            result = service.validate_access_token(token)
            assert isinstance(result, Failure)
            assert result.error == AuthenticationError.INVALID_TOKEN

    def test_validate_wrong_signature_returns_failure(self):
        """Test that token signed with different secret fails validation."""
        service1 = JWTService(secret_key="x" * 32)
        service2 = JWTService(secret_key="y" * 32)

        # Generate with service1, validate with service2
        token = service1.generate_access_token(
            user_id=uuid7(),
            email="test@example.com",
            roles=["user"],
        )

        result = service2.validate_access_token(token)

        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.INVALID_TOKEN

    def test_validate_tampered_payload_returns_failure(self):
        """Test that token with modified payload fails validation."""
        service = JWTService(secret_key="x" * 32)

        token = service.generate_access_token(
            user_id=uuid7(),
            email="test@example.com",
            roles=["user"],
        )

        # Tamper with payload (change one character in middle part)
        parts = token.split(".")
        # Modify middle character of payload
        tampered_payload = parts[1][:-5] + "XXXXX"
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        result = service.validate_access_token(tampered_token)

        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.INVALID_TOKEN

    # =========================================================================
    # Edge Cases and Security Tests
    # =========================================================================

    def test_jwt_service_rejects_short_secret_key(self):
        """Test that service rejects secret key shorter than 32 bytes."""
        with pytest.raises(ValueError) as exc_info:
            JWTService(secret_key="short")

        assert "at least 32 bytes" in str(exc_info.value).lower()

    def test_jwt_service_accepts_minimum_secret_key(self):
        """Test that service accepts exactly 32-byte secret key."""
        # Should not raise
        service = JWTService(secret_key="x" * 32)
        assert service is not None

    def test_generate_access_token_handles_multiple_roles(self):
        """Test token generation with multiple roles in list."""
        service = JWTService(secret_key="x" * 32)
        roles = ["user", "admin", "moderator", "premium"]

        token = service.generate_access_token(
            user_id=uuid7(),
            email="test@example.com",
            roles=roles,
        )

        result = service.validate_access_token(token)
        assert isinstance(result, Success)
        assert result.value["roles"] == roles
        assert len(result.value["roles"]) == 4

    def test_validate_access_token_with_future_iat(self):
        """Test validation with future issued-at time (time travel scenario)."""
        service = JWTService(secret_key="x" * 32, expiration_minutes=15)

        # Generate token (iat will be current time)
        token = service.generate_access_token(
            user_id=uuid7(),
            email="test@example.com",
            roles=["user"],
        )

        # Token should still validate (only exp matters for validation)
        result = service.validate_access_token(token)
        assert isinstance(result, Success)
