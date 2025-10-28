"""JWT service for token generation and validation.

This service handles all JWT operations including:
- Creating access tokens with user claims
- Creating refresh tokens
- Decoding and validating tokens
- Extracting user information from tokens

Note: This service is synchronous (uses `def` instead of `async def`)
because JWT operations are pure CPU-bound work with no I/O.
See docs/development/architecture/async-vs-sync-patterns.md for details.
"""

from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt

from src.core.config import get_settings


class JWTService:
    """Service for JWT token operations.

    This service provides JWT encoding and decoding functionality
    using python-jose. All methods are synchronous because JWT
    operations are pure CPU work with no I/O operations.

    Token Types:
        - Access Token: Short-lived (30 min default), used for API authentication
        - Refresh Token: Long-lived (30 days default), used to get new access tokens

    Token Claims:
        - sub (subject): User ID
        - email: User email address
        - type: Token type (access/refresh)
        - exp (expiration): Token expiration timestamp
        - iat (issued at): Token creation timestamp
        - jti (JWT ID): Unique token identifier (for refresh tokens)

    Attributes:
        secret_key: Secret key for signing tokens
        algorithm: Signing algorithm (HS256)
        access_token_expire_minutes: Access token TTL
        refresh_token_expire_days: Refresh token TTL
    """

    def __init__(self):
        """Initialize JWT service with configuration from settings."""
        settings = get_settings()
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(
        self,
        user_id: UUID,
        email: str,
        refresh_token_id: Optional[UUID] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new access token for user authentication.

        Access tokens are short-lived (default: 30 minutes) and used
        for authenticating API requests. They contain user identity
        information but should not contain sensitive data.

        Args:
            user_id: Unique user identifier
            email: User's email address
            refresh_token_id: Optional refresh token UUID (adds jti claim for session management)
            additional_claims: Optional additional claims to include

        Returns:
            Encoded JWT access token string

        Example:
            >>> service = JWTService()
            >>> from uuid import uuid4
            >>> user_id = uuid4()
            >>> token = service.create_access_token(user_id, "user@example.com")
            >>> len(token) > 0
            True

        Notes:
            - Adding refresh_token_id as jti enables current session detection
            - Existing tokens without jti still work (graceful degradation)
            - jti = JWT ID (RFC 7519 standard claim)
        """
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)

        # Base claims for access token
        claims = {
            "sub": str(user_id),
            "email": email,
            "type": "access",
            "exp": expire,
            "iat": now,
        }

        # Add jti claim if refresh_token_id provided (links access token to session)
        if refresh_token_id:
            claims["jti"] = str(refresh_token_id)

        # Add any additional claims
        if additional_claims:
            claims.update(additional_claims)

        # Encode and return token
        return jwt.encode(claims, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: UUID, jti: UUID) -> str:
        """Create a new refresh token (DEPRECATED).

        **DEPRECATED**: This method is deprecated. The application now uses
        opaque (random) refresh tokens instead of JWT refresh tokens.
        This follows industry standard Pattern A (JWT access + opaque refresh).

        Refresh tokens should be generated using secrets.token_urlsafe()
        and stored as hashed values in the database. See AuthService._create_refresh_token().

        This method is kept for backwards compatibility with existing tests only.

        Args:
            user_id: Unique user identifier
            jti: Unique token identifier

        Returns:
            Encoded JWT refresh token string (for testing only)

        Note:
            DO NOT use this for production authentication flows.
            Use AuthService._create_refresh_token() instead.
        """
        now = datetime.now(UTC)
        expire = now + timedelta(days=self.refresh_token_expire_days)

        claims = {
            "sub": str(user_id),
            "type": "refresh",
            "jti": str(jti),  # Unique token ID for database tracking
            "exp": expire,
            "iat": now,
        }

        return jwt.encode(claims, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token.

        This method decodes the token, verifies its signature, and
        checks that it hasn't expired. If validation fails, a
        JWTError exception is raised.

        Args:
            token: Encoded JWT token string

        Returns:
            Dictionary of token claims (sub, email, type, exp, etc.)

        Raises:
            JWTError: If token is invalid, expired, or signature doesn't match

        Example:
            >>> service = JWTService()
            >>> from uuid import uuid4
            >>> user_id = uuid4()
            >>> token = service.create_access_token(user_id, "user@example.com")
            >>> claims = service.decode_token(token)
            >>> claims["email"]
            'user@example.com'
            >>> claims["type"]
            'access'
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            # Re-raise with more context
            raise JWTError(f"Token validation failed: {str(e)}")

    def verify_token_type(self, token: str, expected_type: str) -> Dict[str, Any]:
        """Decode token and verify it's of the expected type.

        Use this to ensure tokens are being used correctly:
        - Access tokens for API authentication
        - Refresh tokens for token refresh

        Args:
            token: Encoded JWT token string
            expected_type: Expected token type ("access" or "refresh")

        Returns:
            Dictionary of token claims

        Raises:
            JWTError: If token is invalid or wrong type

        Example:
            >>> service = JWTService()
            >>> from uuid import uuid4
            >>> user_id = uuid4()
            >>> token = service.create_access_token(user_id, "user@example.com")
            >>> claims = service.verify_token_type(token, "access")
            >>> claims["type"]
            'access'

            >>> service.verify_token_type(token, "refresh")
            Traceback (most recent call last):
            ...
            jose.exceptions.JWTError: Invalid token type: expected refresh, got access
        """
        payload = self.decode_token(token)

        token_type = payload.get("type")
        if token_type != expected_type:
            raise JWTError(
                f"Invalid token type: expected {expected_type}, got {token_type}"
            )

        return payload

    def get_user_id_from_token(self, token: str) -> UUID:
        """Extract user ID from a valid token.

        Convenience method to get user ID without manually parsing claims.

        Args:
            token: Encoded JWT token string

        Returns:
            User ID as UUID

        Raises:
            JWTError: If token is invalid or missing subject claim

        Example:
            >>> service = JWTService()
            >>> from uuid import uuid4
            >>> user_id = uuid4()
            >>> token = service.create_access_token(user_id, "user@example.com")
            >>> extracted_id = service.get_user_id_from_token(token)
            >>> extracted_id == user_id
            True
        """
        payload = self.decode_token(token)

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise JWTError("Token missing subject (user ID) claim")

        try:
            return UUID(user_id_str)
        except ValueError as e:
            raise JWTError(f"Invalid user ID format in token: {str(e)}")

    def get_token_jti(self, token: str) -> UUID:
        """Extract JWT ID (jti) from a refresh token.

        The jti claim is used to track refresh tokens in the database
        and enable token revocation.

        Args:
            token: Encoded refresh token string

        Returns:
            Token ID as UUID

        Raises:
            JWTError: If token is invalid or missing jti claim

        Example:
            >>> service = JWTService()
            >>> from uuid import uuid4
            >>> user_id = uuid4()
            >>> jti = uuid4()
            >>> token = service.create_refresh_token(user_id, jti)
            >>> extracted_jti = service.get_token_jti(token)
            >>> extracted_jti == jti
            True
        """
        # Verify it's a refresh token
        payload = self.verify_token_type(token, "refresh")

        jti_str = payload.get("jti")
        if not jti_str:
            raise JWTError("Refresh token missing jti (token ID) claim")

        try:
            return UUID(jti_str)
        except ValueError as e:
            raise JWTError(f"Invalid token ID format: {str(e)}")

    def is_token_expired(self, token: str) -> bool:
        """Check if a token is expired without raising an exception.

        Useful for checking token status without catching exceptions.

        Args:
            token: Encoded JWT token string

        Returns:
            True if token is expired, False if still valid

        Note:
            If the token is malformed or has invalid signature,
            this will return True (treating invalid as expired).

        Example:
            >>> service = JWTService()
            >>> from uuid import uuid4
            >>> user_id = uuid4()
            >>> token = service.create_access_token(user_id, "user@example.com")
            >>> service.is_token_expired(token)
            False
        """
        try:
            payload = self.decode_token(token)

            # Check if exp claim exists
            exp = payload.get("exp")
            if not exp:
                return True

            # Compare expiration time with current time
            exp_datetime = datetime.fromtimestamp(exp, UTC)
            return datetime.now(UTC) >= exp_datetime

        except JWTError:
            # Treat any decode error as expired
            return True

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """Get the expiration time of a token.

        Args:
            token: Encoded JWT token string

        Returns:
            Expiration datetime, or None if token is invalid

        Example:
            >>> service = JWTService()
            >>> from uuid import uuid4
            >>> user_id = uuid4()
            >>> token = service.create_access_token(user_id, "user@example.com")
            >>> exp = service.get_token_expiration(token)
            >>> exp is not None
            True
        """
        try:
            payload = self.decode_token(token)
            exp = payload.get("exp")

            if exp:
                return datetime.fromtimestamp(exp, UTC)
            return None

        except JWTError:
            return None
