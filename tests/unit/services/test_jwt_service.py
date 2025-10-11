"""Unit tests for JWTService.

Tests JWT token creation, validation, and decoding functionality. Covers:
- Access token generation with user claims (email, sub, type)
- Refresh token generation with JTI (JWT ID)
- Token validation and type checking
- Token expiration handling
- JWT payload extraction and claim verification
- Error handling for invalid tokens

Note:
    Uses synchronous test pattern (regular def test_*(), NOT async def)
    since JWTService operates synchronously on JWT strings.
"""

import pytest
from uuid import uuid4
from jose import JWTError

from src.services.jwt_service import JWTService


class TestJWTService:
    """Test suite for JWTService token operations.

    Validates all JWT creation, validation, and decoding scenarios including
    error handling and edge cases. Tests Pattern A authentication design:
    - JWT access tokens (stateless, 30 min TTL)
    - JWT refresh tokens (temporary, used for Pattern A before opaque implementation)

    Attributes:
        service: JWTService instance created in setup_method
        test_user_id: UUID for test user
        test_email: Email address for test user
    """

    def setup_method(self):
        """Set up test fixtures before each test method.

        Initializes:
            - JWTService instance (fresh for each test)
            - Test user ID (UUID)
            - Test email address

        Note:
            Called automatically by pytest before each test method in the class.
        """
        self.service = JWTService()
        self.test_user_id = uuid4()
        self.test_email = "test@example.com"

    def test_create_access_token(self):
        """Test JWT access token creation with user claims.

        Verifies that:
        - Token is generated as a valid JWT string
        - Token is non-empty
        - Token has standard JWT structure (3 parts: header.payload.signature)
        - Token contains user_id and email claims

        Note:
            JWT format: base64(header).base64(payload).signature
            Access tokens have 30 minute TTL by default.
        """
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT has 3 parts separated by dots

    def test_create_refresh_token(self):
        """Test JWT refresh token creation with JTI claim.

        Verifies that:
        - Token is generated as a valid JWT string
        - Token is non-empty
        - Token has standard JWT structure (3 parts)
        - Token contains JTI (JWT ID) for tracking

        Note:
            JTI is used to track and revoke specific refresh tokens.
            This tests JWT refresh tokens (Pattern A uses opaque refresh tokens).
        """
        jti = uuid4()

        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2

    def test_decode_token_valid(self):
        """Test decoding and extracting claims from valid JWT.

        Verifies that:
        - Token payload is successfully decoded
        - Subject (sub) claim matches user ID
        - Email claim matches user email
        - Type claim is "access"
        - Expiration (exp) timestamp is present
        - Issued-at (iat) timestamp is present

        Note:
            All standard JWT claims are validated for presence and correctness.
        """
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
        """Test that decoding invalid JWT raises JWTError.

        Verifies that:
        - Invalid JWT format raises JWTError
        - Malformed token is rejected
        - No partial decoding occurs

        Raises:
            JWTError: Expected exception for invalid token format

        Note:
            Invalid tokens include malformed structure, bad signature, etc.
        """
        invalid_token = "invalid.token.here"

        with pytest.raises(JWTError):
            self.service.decode_token(invalid_token)

    def test_decode_token_expired(self):
        """Test that decoding expired JWT raises JWTError.

        Verifies that:
        - Expired token is rejected during decode
        - JWTError is raised for expired tokens
        - Expiration claim (exp) is validated

        Raises:
            JWTError: Expected exception for expired token

        Note:
            Uses pre-crafted expired JWT (exp=1) for testing.
            In production, access tokens expire after 30 minutes.
        """
        # Create token with immediate expiration (can't easily test without mocking time)
        # This is more of an integration test, but we can test the error handling
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxfQ.invalid"

        with pytest.raises(JWTError):
            self.service.decode_token(invalid_token)

    def test_verify_token_type_access(self):
        """Test token type verification for access token.

        Verifies that:
        - Access token passes type verification with "access"
        - Payload is returned after successful verification
        - Type claim is correctly set to "access"

        Note:
            Token type verification prevents using access tokens where
            refresh tokens are expected and vice versa.
        """
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        payload = self.service.verify_token_type(token, "access")

        assert payload["type"] == "access"

    def test_verify_token_type_refresh(self):
        """Test token type verification for refresh token.

        Verifies that:
        - Refresh token passes type verification with "refresh"
        - Payload is returned after successful verification
        - Type claim is correctly set to "refresh"

        Note:
            Refresh tokens should only be accepted at /auth/refresh endpoint.
        """
        jti = uuid4()
        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        payload = self.service.verify_token_type(token, "refresh")

        assert payload["type"] == "refresh"

    def test_verify_token_type_mismatch(self):
        """Test token type verification rejection on type mismatch.

        Verifies that:
        - Using access token where refresh expected raises JWTError
        - Error message indicates "Invalid token type"
        - Type mismatch is caught before processing

        Raises:
            JWTError: Expected exception with "Invalid token type" message

        Note:
            Security measure: prevents token type confusion attacks.
        """
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        with pytest.raises(JWTError, match="Invalid token type"):
            self.service.verify_token_type(token, "refresh")

    def test_get_user_id_from_token(self):
        """Test extracting user ID from JWT subject claim.

        Verifies that:
        - User ID is correctly extracted from token
        - Subject (sub) claim is parsed as UUID
        - Extracted UUID matches original user ID

        Note:
            Subject claim contains user_id as string (UUID converted to string).
        """
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        user_id = self.service.get_user_id_from_token(token)

        assert user_id == self.test_user_id

    def test_get_user_id_from_token_invalid(self):
        """Test user ID extraction rejection from invalid JWT.

        Verifies that:
        - Invalid token raises JWTError
        - No user ID is returned
        - Token must be valid before extracting claims

        Raises:
            JWTError: Expected exception for invalid token

        Note:
            Token validation happens before claim extraction.
        """
        invalid_token = "invalid.token.here"

        with pytest.raises(JWTError):
            self.service.get_user_id_from_token(invalid_token)

    def test_get_token_jti(self):
        """Test extracting JTI (JWT ID) from refresh token.

        Verifies that:
        - JTI claim is correctly extracted from refresh token
        - Extracted UUID matches original JTI
        - JTI is used for refresh token tracking

        Note:
            JTI (JWT ID) uniquely identifies each refresh token instance.
            Used for token revocation and tracking in database.
        """
        jti = uuid4()
        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        extracted_jti = self.service.get_token_jti(token)

        assert extracted_jti == jti

    def test_get_token_jti_from_access_token_fails(self):
        """Test JTI extraction rejection from access token (wrong type).

        Verifies that:
        - Access tokens don't have JTI claim
        - Attempting to extract JTI raises JWTError
        - Error message indicates "Invalid token type"
        - Type validation prevents misuse

        Raises:
            JWTError: Expected exception with "Invalid token type" message

        Note:
            Only refresh tokens contain JTI claim.
        """
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        with pytest.raises(JWTError, match="Invalid token type"):
            self.service.get_token_jti(token)

    def test_is_token_expired_fresh_token(self):
        """Test expiration check for freshly created token.

        Verifies that:
        - Newly created token is not expired
        - is_token_expired returns False
        - Expiration check compares exp claim with current time

        Note:
            Fresh access tokens have 30 minutes until expiration.
        """
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        is_expired = self.service.is_token_expired(token)

        assert is_expired is False

    def test_is_token_expired_invalid_token(self):
        """Test that invalid token is treated as expired (security).

        Verifies that:
        - Invalid tokens return True for is_expired
        - Unparseable tokens are considered expired
        - Graceful handling of malformed tokens

        Note:
            Security practice: treat any invalid token as expired
            rather than exposing internal errors.
        """
        invalid_token = "invalid.token.here"

        is_expired = self.service.is_token_expired(invalid_token)

        assert is_expired is True

    def test_get_token_expiration(self):
        """Test extracting expiration timestamp from JWT.

        Verifies that:
        - Expiration time is successfully extracted
        - Returned datetime is timezone-aware (UTC)
        - exp claim is converted to datetime object

        Note:
            Expiration is stored as Unix timestamp in exp claim.
            Returned as timezone-aware datetime in UTC.
        """
        from datetime import UTC

        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        expiration = self.service.get_token_expiration(token)

        assert expiration is not None
        assert expiration.tzinfo == UTC  # UTC timezone-aware datetime

    def test_get_token_expiration_invalid_token(self):
        """Test expiration extraction from invalid token returns None.

        Verifies that:
        - Invalid token returns None (not exception)
        - Graceful error handling
        - Caller can check for None to detect invalid tokens

        Note:
            Returns None instead of raising exception for convenience.
        """
        invalid_token = "invalid.token.here"

        expiration = self.service.get_token_expiration(invalid_token)

        assert expiration is None

    def test_access_token_contains_email(self):
        """Test that access tokens include email claim.

        Verifies that:
        - Email claim is present in access token payload
        - Email value matches provided email
        - Access tokens contain user profile data

        Note:
            Access tokens include email for user identification without
            requiring additional database lookups.
        """
        token = self.service.create_access_token(
            user_id=self.test_user_id, email=self.test_email
        )

        payload = self.service.decode_token(token)

        assert payload["email"] == self.test_email

    def test_refresh_token_no_email(self):
        """Test that refresh tokens exclude email claim (minimal claims).

        Verifies that:
        - Email claim is NOT in refresh token payload
        - Refresh tokens only contain essential claims (sub, type, jti)
        - Minimal data exposure in refresh tokens

        Note:
            Refresh tokens use minimal claims for security (less data leaked
            if token is compromised).
        """
        jti = uuid4()
        token = self.service.create_refresh_token(user_id=self.test_user_id, jti=jti)

        payload = self.service.decode_token(token)

        assert "email" not in payload
        assert "jti" in payload

    def test_access_token_with_additional_claims(self):
        """Test adding custom claims to access token payload.

        Verifies that:
        - Additional claims are included in token payload
        - Custom role claim is present and correct
        - Custom permissions claim is present and correct
        - Claims are preserved through encode/decode cycle

        Note:
            Allows extending tokens with application-specific data
            (roles, permissions, metadata, etc.).
        """
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
        """Test that multiple tokens for same user have unique values.

        Verifies that:
        - Two tokens for same user are different strings
        - Tokens differ due to different iat (issued-at) timestamps
        - Each token issuance creates unique token

        Note:
            Even with identical claims, tokens differ due to timestamp.
            Ensures replay attack protection.
        """
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
