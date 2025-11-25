"""RefreshTokenServiceProtocol - Domain protocol for refresh token operations.

This protocol defines the interface for refresh token generation and verification.
Infrastructure provides the concrete implementation (RefreshTokenService).

Following hexagonal architecture:
- Domain defines what it needs (protocol/port)
- Infrastructure provides implementation (adapter)
- Application layer uses protocol, not concrete implementation
"""

from datetime import datetime
from typing import Protocol


class RefreshTokenServiceProtocol(Protocol):
    """Protocol for refresh token generation and verification.

    Generates opaque refresh tokens for long-lived authentication.
    Tokens are hashed before database storage for security.

    Implementations:
        - RefreshTokenService: src/infrastructure/security/refresh_token_service.py
    """

    def generate_token(self) -> tuple[str, str]:
        """Generate refresh token and its hash.

        Returns:
            Tuple of (token, token_hash):
                - token: Plain token to return to user (urlsafe base64)
                - token_hash: Bcrypt hash to store in database
        """
        ...

    def verify_token(self, token: str, token_hash: str) -> bool:
        """Verify token against stored hash.

        Args:
            token: Plain token from user request.
            token_hash: Bcrypt hash from database.

        Returns:
            True if token matches hash, False otherwise.
        """
        ...

    def calculate_expiration(self) -> datetime:
        """Calculate expiration timestamp for new token.

        Returns:
            Expiration datetime (UTC) based on configured expiration_days.
        """
        ...
