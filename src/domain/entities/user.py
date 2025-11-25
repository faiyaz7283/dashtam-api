"""User domain entity for authentication.

Pure business logic, no framework dependencies.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID


@dataclass
class User:
    """User domain entity with authentication business rules.

    Pure business logic with no infrastructure dependencies.
    Represents a user account with email verification, password, and lockout.

    Business Rules:
        - Email verification required before login
        - Account locks after 5 failed login attempts
        - Lockout duration is 15 minutes
        - Failed login counter resets on successful login

    Attributes:
        id: Unique user identifier
        email: User email address (validated by Email value object)
        password_hash: Bcrypt hashed password (never plaintext)
        is_verified: Email verification status (blocks login if False)
        is_active: Account active status (deactivated users cannot login)
        failed_login_attempts: Counter for failed login attempts
        locked_until: Timestamp until which account is locked (None if not locked)
        created_at: Timestamp when user was created
        updated_at: Timestamp when user was last updated

    Example:
        >>> user = User(
        ...     id=uuid4(),
        ...     email="user@example.com",
        ...     password_hash="$2b$12$...",
        ...     is_verified=False,
        ...     is_active=True,
        ...     failed_login_attempts=0,
        ...     locked_until=None,
        ...     created_at=datetime.now(UTC),
        ...     updated_at=datetime.now(UTC),
        ... )
        >>> user.is_locked()
        False
        >>> user.increment_failed_login()
        >>> user.failed_login_attempts
        1
    """

    id: UUID
    email: str  # Should be Email value object in application layer
    password_hash: str  # Never store plaintext passwords
    is_verified: bool
    is_active: bool
    failed_login_attempts: int
    locked_until: datetime | None
    created_at: datetime
    updated_at: datetime

    def is_locked(self) -> bool:
        """Check if account is currently locked due to failed login attempts.

        Account is locked if locked_until timestamp is in the future.

        Returns:
            bool: True if account is locked, False otherwise.

        Example:
            >>> user = User(..., locked_until=None)
            >>> user.is_locked()
            False
            >>> user.locked_until = datetime.now(UTC) + timedelta(minutes=10)
            >>> user.is_locked()
            True
        """
        if self.locked_until is None:
            return False
        return datetime.now(UTC) < self.locked_until

    def increment_failed_login(self) -> None:
        """Increment failed login counter and lock account after 5 attempts.

        Business Rule: After 5 failed login attempts, lock account for 15 minutes.

        Side Effects:
            - Increments failed_login_attempts by 1
            - Sets locked_until to 15 minutes from now if attempts >= 5

        Example:
            >>> user = User(..., failed_login_attempts=4)
            >>> user.increment_failed_login()
            >>> user.failed_login_attempts
            5
            >>> user.is_locked()
            True
        """
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            # Lock for 15 minutes
            self.locked_until = datetime.now(UTC) + timedelta(minutes=15)

    def reset_failed_login(self) -> None:
        """Reset failed login counter after successful login.

        Called on successful authentication to reset lockout state.

        Side Effects:
            - Resets failed_login_attempts to 0
            - Clears locked_until (sets to None)

        Example:
            >>> user = User(..., failed_login_attempts=3, locked_until=...)
            >>> user.reset_failed_login()
            >>> user.failed_login_attempts
            0
            >>> user.locked_until
            None
        """
        self.failed_login_attempts = 0
        self.locked_until = None

    def can_login(self) -> bool:
        """Check if user can login (verified, active, not locked).

        Convenience method combining multiple checks.

        Returns:
            bool: True if user can login, False otherwise.

        Example:
            >>> user = User(..., is_verified=True, is_active=True)
            >>> user.can_login()
            True
            >>> user.is_verified = False
            >>> user.can_login()
            False
        """
        return self.is_verified and self.is_active and not self.is_locked()
