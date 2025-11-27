"""User domain entity for authentication.

Pure business logic, no framework dependencies.

Session Management:
    - session_tier: Role-based tier determining default session limit
    - max_sessions: Optional admin override for session limit
    - get_max_sessions(): Returns effective session limit

Token Breach Rotation:
    - min_token_version: Per-user minimum acceptable token version
    - Increment to invalidate all user's tokens (password change, security event)
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

# Session tier limits (default limits by tier)
# None means unlimited sessions
SESSION_TIER_LIMITS: dict[str, int | None] = {
    "pro": None,  # Unlimited
    "premium": 10,
    "plus": 5,
    "essential": 3,
    "basic": 2,
}

# Default tier for new users
DEFAULT_SESSION_TIER = "basic"


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

        Session Management:
            session_tier: Role-based tier (basic, essential, plus, premium, pro)
            max_sessions: Admin override for session limit (None = use tier default)

        Token Breach Rotation:
            min_token_version: Per-user minimum token version (increment to invalidate tokens)

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

    # Session management (F1.3)
    session_tier: str = DEFAULT_SESSION_TIER
    max_sessions: int | None = None  # Admin override (None = use tier default)

    # Token breach rotation
    min_token_version: int = 1  # Increment to invalidate all user's tokens

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

    def get_max_sessions(self) -> int | None:
        """Get effective maximum sessions for this user.

        Priority:
        1. Admin override (max_sessions field) if set
        2. Tier-based default from SESSION_TIER_LIMITS
        3. Falls back to 'basic' tier if invalid tier

        Returns:
            int | None: Maximum sessions allowed (None = unlimited)

        Example:
            >>> user = User(..., session_tier="premium", max_sessions=None)
            >>> user.get_max_sessions()
            10
            >>> user.max_sessions = 15  # Admin override
            >>> user.get_max_sessions()
            15
            >>> user.session_tier = "ultimate"
            >>> user.max_sessions = None
            >>> user.get_max_sessions()
            None  # Unlimited
        """
        # Admin override takes precedence
        if self.max_sessions is not None:
            return self.max_sessions

        # Use tier-based default
        return SESSION_TIER_LIMITS.get(
            self.session_tier,
            SESSION_TIER_LIMITS[DEFAULT_SESSION_TIER],  # Fallback
        )

    def can_create_session(self, current_session_count: int) -> bool:
        """Check if user can create a new session.

        Args:
            current_session_count: Number of active sessions user currently has.

        Returns:
            bool: True if user can create new session, False if at limit.

        Example:
            >>> user = User(..., session_tier="basic")  # limit=2
            >>> user.can_create_session(1)
            True
            >>> user.can_create_session(2)
            False
        """
        max_sessions = self.get_max_sessions()
        if max_sessions is None:
            return True  # Unlimited
        return current_session_count < max_sessions
