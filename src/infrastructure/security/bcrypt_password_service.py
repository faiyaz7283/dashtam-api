"""Bcrypt password hashing service (adapter).

This service implements the PasswordHashingProtocol using bcrypt with cost factor 12.

Architecture:
    - Implements PasswordHashingProtocol (no inheritance required)
    - Structural typing via Protocol
    - Injected via dependency container

Security:
    - Bcrypt with cost factor 12 (~250ms per hash)
    - Adaptive algorithm (can increase cost over time)
    - Resistant to GPU/ASIC attacks (memory-hard)
    - Industry standard for password hashing

Performance:
    - Hash: ~250ms (acceptable for auth operations)
    - Verify: ~250ms (same as hash)
    - Cost factor 12 = 2^12 = 4096 iterations

Reference:
    - docs/architecture/authentication-architecture.md (Lines 853-875)
"""

import bcrypt


class BcryptPasswordService:
    """Bcrypt password hashing service.

    Implements password hashing and verification using bcrypt with cost factor 12.
    This is the production password hashing implementation.

    Usage:
        # Via dependency injection
        from src.core.container import get_password_service
        from src.domain.protocols import PasswordHashingProtocol

        password_service: PasswordHashingProtocol = get_password_service()

        # Hash password
        password_hash = password_service.hash_password("SecurePass123!")

        # Verify password
        is_valid = password_service.verify_password("SecurePass123!", password_hash)
    """

    def __init__(self, cost_factor: int = 12) -> None:
        """Initialize bcrypt password service.

        Args:
            cost_factor: Bcrypt cost factor (default: 12).
                Higher values = more secure but slower.
                12 = ~250ms per hash (recommended for 2024).
                Increase over time as hardware improves.

        Note:
            Cost factor is logarithmic: each +1 doubles computation time.
            - 10 = ~60ms
            - 11 = ~125ms
            - 12 = ~250ms (current recommendation)
            - 13 = ~500ms
            - 14 = ~1000ms
        """
        if cost_factor < 10:
            msg = "Cost factor must be at least 10 for security"
            raise ValueError(msg)
        if cost_factor > 20:
            msg = "Cost factor above 20 is impractically slow"
            raise ValueError(msg)

        self._cost_factor = cost_factor

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password using bcrypt.

        Args:
            password: Plaintext password to hash.

        Returns:
            Hashed password string (bcrypt format: $2b$12$...).
            Always 60 characters long.

        Example:
            >>> service = BcryptPasswordService(cost_factor=12)
            >>> hash1 = service.hash_password("SecurePass123!")
            >>> hash2 = service.hash_password("SecurePass123!")
            >>> hash1 != hash2  # Different salts
            True
            >>> len(hash1)
            60

        Note:
            - Each call produces different hash (random salt)
            - Hash format: $2b$<cost>$<salt><hash>
            - Salt is automatically generated
            - Hash is one-way (cannot be reversed)
        """
        # Generate salt with configured cost factor
        salt = bcrypt.gensalt(rounds=self._cost_factor)

        # Hash password with salt
        password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)

        # Return as string (bcrypt returns bytes)
        return password_hash.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a bcrypt hash.

        Args:
            password: Plaintext password to verify.
            password_hash: Hashed password from database.

        Returns:
            True if password matches hash, False otherwise.

        Example:
            >>> service = BcryptPasswordService()
            >>> password_hash = service.hash_password("SecurePass123!")
            >>> service.verify_password("SecurePass123!", password_hash)
            True
            >>> service.verify_password("WrongPassword", password_hash)
            False
            >>> service.verify_password("SecurePass123!", "invalid_hash")
            False

        Note:
            - Constant-time comparison (prevents timing attacks)
            - Returns False for invalid hash format (no exceptions)
            - Returns False if hash is not bcrypt format
            - Safe to call with untrusted input
        """
        try:
            # bcrypt.checkpw does constant-time comparison
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except (ValueError, AttributeError):
            # Invalid hash format or encoding error
            # Return False instead of raising (fail securely)
            return False
