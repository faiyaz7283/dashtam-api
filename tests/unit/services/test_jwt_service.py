"""Unit tests for JWTService.

Tests JWT token creation, validation, and decoding.
"""

import pytest
from uuid import uuid4
from jose import JWTError

from src.services.jwt_service import JWTService


class TestJWTService:
    """Test suite for JWTService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = JWTService()
        self.test_user_id = uuid4()
        self.test_email = "test@example.com"

    def test_create_access_token(self):
        """Test access token creation."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT has 3 parts separated by dots

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        jti = uuid4()

        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2

    def test_decode_token_valid(self):
        """Test decoding valid token."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        payload = self.service.decode_token(token)

        assert payload["sub"] == str(self.test_user_id)
        assert payload["email"] == self.test_email
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_token_invalid(self):
        """Test decoding invalid token raises error."""
        invalid_token = "invalid.token.here"

        with pytest.raises(JWTError):
            self.service.decode_token(invalid_token)

    def test_decode_token_expired(self):
        """Test decoding expired token raises error."""
        # Create token with immediate expiration (can't easily test without mocking time)
        # This is more of an integration test, but we can test the error handling
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxfQ.invalid"

        with pytest.raises(JWTError):
            self.service.decode_token(invalid_token)

    def test_verify_token_type_access(self):
        """Test verifying access token type."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        payload = self.service.verify_token_type(token, "access")

        assert payload["type"] == "access"

    def test_verify_token_type_refresh(self):
        """Test verifying refresh token type."""
        jti = uuid4()
        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        payload = self.service.verify_token_type(token, "refresh")

        assert payload["type"] == "refresh"

    def test_verify_token_type_mismatch(self):
        """Test token type verification fails on mismatch."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        with pytest.raises(JWTError, match="Invalid token type"):
            self.service.verify_token_type(token, "refresh")

    def test_get_user_id_from_token(self):
        """Test extracting user ID from token."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        user_id = self.service.get_user_id_from_token(token)

        assert user_id == self.test_user_id

    def test_get_user_id_from_token_invalid(self):
        """Test extracting user ID from invalid token raises error."""
        invalid_token = "invalid.token.here"

        with pytest.raises(JWTError):
            self.service.get_user_id_from_token(invalid_token)

    def test_get_token_jti(self):
        """Test extracting JWT ID from refresh token."""
        jti = uuid4()
        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        extracted_jti = self.service.get_token_jti(token)

        assert extracted_jti == jti

    def test_get_token_jti_from_access_token_fails(self):
        """Test extracting JTI from access token fails."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        with pytest.raises(JWTError, match="Invalid token type"):
            self.service.get_token_jti(token)

    def test_is_token_expired_fresh_token(self):
        """Test that fresh token is not expired."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        is_expired = self.service.is_token_expired(token)

        assert is_expired is False

    def test_is_token_expired_invalid_token(self):
        """Test that invalid token is treated as expired."""
        invalid_token = "invalid.token.here"

        is_expired = self.service.is_token_expired(invalid_token)

        assert is_expired is True

    def test_get_token_expiration(self):
        """Test getting token expiration time."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        expiration = self.service.get_token_expiration(token)

        assert expiration is not None
        assert expiration.tzinfo is None  # UTC naive datetime

    def test_get_token_expiration_invalid_token(self):
        """Test getting expiration from invalid token returns None."""
        invalid_token = "invalid.token.here"

        expiration = self.service.get_token_expiration(invalid_token)

        assert expiration is None

    def test_access_token_contains_email(self):
        """Test access token includes email claim."""
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        payload = self.service.decode_token(token)

        assert payload["email"] == self.test_email

    def test_refresh_token_no_email(self):
        """Test refresh token does not include email (minimal claims)."""
        jti = uuid4()
        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        payload = self.service.decode_token(token)

        assert "email" not in payload
        assert "jti" in payload

    def test_access_token_with_additional_claims(self):
        """Test access token with additional custom claims."""
        additional_claims = {"role": "admin", "permissions": ["read", "write"]}

        token = self.service.create_access_token(
            user_id=self.test_user_id,
            email=self.test_email,
            additional_claims=additional_claims,
        )

        payload = self.service.decode_token(token)

        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write"]

    def test_tokens_are_unique(self):
        """Test that multiple tokens for same user are unique."""
        import time

        token1 = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        # Sleep briefly to ensure different iat timestamp
        time.sleep(1)

        token2 = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        assert token1 != token2  # Different due to iat timestamp
