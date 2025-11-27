"""SecurityConfig domain entity for token breach rotation.

Pure business logic, no framework dependencies.

Token Breach Rotation:
    - global_min_token_version: Minimum acceptable token version globally
    - grace_period_seconds: Time window to allow old tokens after rotation
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SecurityConfig:
    """Security configuration domain entity.

    Singleton configuration for global token version management.
    Used during token validation to check minimum version requirements.

    Token Validation Rule:
        token_version >= max(global_min_token_version, user.min_token_version)

    Attributes:
        id: Always 1 (singleton).
        global_min_token_version: Minimum acceptable token version globally.
        grace_period_seconds: Seconds to allow old tokens after rotation.
        last_rotation_at: When global rotation was last triggered.
        last_rotation_reason: Why global rotation was triggered.
        created_at: When config was created.
        updated_at: When config was last modified.

    Example:
        >>> config = SecurityConfig(
        ...     id=1,
        ...     global_min_token_version=1,
        ...     grace_period_seconds=300,
        ...     last_rotation_at=None,
        ...     last_rotation_reason=None,
        ...     created_at=datetime.now(UTC),
        ...     updated_at=datetime.now(UTC),
        ... )
        >>> config.is_within_grace_period(rotation_time)
        True
    """

    id: int
    global_min_token_version: int
    grace_period_seconds: int
    last_rotation_at: datetime | None
    last_rotation_reason: str | None
    created_at: datetime
    updated_at: datetime

    def is_within_grace_period(self, reference_time: datetime) -> bool:
        """Check if current time is within grace period after last rotation.

        Grace period allows gradual token invalidation rather than
        immediate mass logout of all users.

        Args:
            reference_time: Current time to check against.

        Returns:
            bool: True if within grace period, False otherwise.
                  Returns False if no rotation has occurred.

        Example:
            >>> config.last_rotation_at = datetime.now(UTC)
            >>> config.grace_period_seconds = 300
            >>> config.is_within_grace_period(datetime.now(UTC))
            True  # Within 5 minutes
        """
        if self.last_rotation_at is None:
            return False

        elapsed = (reference_time - self.last_rotation_at).total_seconds()
        return elapsed <= self.grace_period_seconds

    def should_reject_token_version(
        self,
        token_version: int,
        user_min_version: int,
        current_time: datetime,
    ) -> bool:
        """Check if a token should be rejected based on version requirements.

        Implements the token validation rule with grace period support.

        Args:
            token_version: Version of the token being validated.
            user_min_version: User's minimum acceptable token version.
            current_time: Current time for grace period check.

        Returns:
            bool: True if token should be rejected, False if valid.

        Example:
            >>> config.global_min_token_version = 2
            >>> config.should_reject_token_version(
            ...     token_version=1,
            ...     user_min_version=1,
            ...     current_time=datetime.now(UTC),
            ... )
            True  # Token version 1 < global minimum 2
        """
        required_version = max(self.global_min_token_version, user_min_version)

        if token_version >= required_version:
            return False  # Token is valid

        # Token version is below required - check grace period
        if self.is_within_grace_period(current_time):
            # Allow old tokens during grace period
            # But only if they meet the PREVIOUS version requirement
            previous_required = required_version - 1
            return token_version < previous_required

        return True  # Reject - below minimum and outside grace period
