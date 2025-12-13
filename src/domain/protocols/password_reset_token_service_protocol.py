"""PasswordResetTokenServiceProtocol - Domain protocol for password reset token operations.

This protocol defines the interface for password reset token generation.
Infrastructure provides the concrete implementation (PasswordResetTokenService).

Following hexagonal architecture:
- Domain defines what it needs (protocol/port)
- Infrastructure provides implementation (adapter)
- Application layer uses protocol, not concrete implementation
"""

from datetime import datetime
from typing import Protocol


class PasswordResetTokenServiceProtocol(Protocol):
    """Protocol for password reset token generation.

    Generates unguessable tokens for password reset links.
    Very short-lived (15 minutes) for security.

    Implementations:
        - PasswordResetTokenService: src/infrastructure/security/password_reset_token_service.py
    """

    def generate_token(self) -> str:
        """Generate password reset token.

        Returns:
            64-character hex string (32 bytes of entropy).
        """
        ...

    def calculate_expiration(self) -> datetime:
        """Calculate expiration timestamp for new token.

        Returns:
            Expiration datetime (UTC) based on configured expiration_minutes.
        """
        ...
