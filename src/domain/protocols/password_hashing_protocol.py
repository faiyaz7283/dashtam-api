"""Password hashing protocol for domain layer.

This protocol defines the interface for password hashing and verification.
Infrastructure layer provides concrete implementations (bcrypt, argon2, etc.).

Architecture:
    - Domain defines protocol (port)
    - Infrastructure implements adapter (BcryptPasswordService)
    - No framework dependencies in domain
"""

from typing import Protocol


class PasswordHashingProtocol(Protocol):
    """Password hashing and verification interface.

    Implementations:
        - BcryptPasswordService: bcrypt with cost factor 12 (production)
        - Argon2PasswordService: argon2 (future alternative)

    Usage:
        # Domain/Application layer depends on protocol
        def __init__(self, password_service: PasswordHashingProtocol):
            self.password_service = password_service

        # Hash password
        password_hash = self.password_service.hash_password("SecurePass123!")

        # Verify password
        is_valid = self.password_service.verify_password("SecurePass123!", password_hash)
    """

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password.

        Args:
            password: Plaintext password to hash.

        Returns:
            Hashed password string (bcrypt format: $2b$12$...).

        Note:
            - NEVER store plaintext passwords
            - Hash is one-way (cannot be reversed)
            - Same password produces different hashes (random salt)
        """
        ...

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a hash.

        Args:
            password: Plaintext password to verify.
            password_hash: Hashed password from database.

        Returns:
            True if password matches hash, False otherwise.

        Note:
            - Constant-time comparison (prevents timing attacks)
            - Returns False for invalid hash format (no exceptions)
        """
        ...
