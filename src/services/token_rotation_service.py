"""Token rotation service for breach response.

This service handles token versioning and rotation for both per-user
and global security events. Implements hybrid token rotation strategy
(Approach 3) with audit trail and grace period support.

Architecture:
- Single Responsibility: Only handles token rotation logic
- Dependency Injection: Accepts AsyncSession, not coupled to database
- Strategy Pattern: Supports both user and global rotation strategies
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from sqlalchemy import update

from src.models.user import User
from src.models.auth import RefreshToken
from src.models.security_config import SecurityConfig

logger = logging.getLogger(__name__)


@dataclass
class TokenRotationResult:
    """Result of token rotation operation.

    Attributes:
        rotation_type: Type of rotation ('USER' or 'GLOBAL').
        user_id: User ID (for USER rotation, None for GLOBAL).
        old_version: Previous version number.
        new_version: New version number.
        tokens_revoked: Number of tokens revoked.
        users_affected: Number of users affected (GLOBAL only).
        reason: Why rotation was performed.
        initiated_by: Who initiated rotation (GLOBAL only).
        grace_period_minutes: Grace period before full revocation.
    """

    rotation_type: Literal["USER", "GLOBAL"]
    old_version: int
    new_version: int
    tokens_revoked: int
    reason: str
    user_id: Optional[UUID] = None
    users_affected: Optional[int] = None
    initiated_by: Optional[str] = None
    grace_period_minutes: Optional[int] = None


class TokenRotationService:
    """Service for token versioning and rotation.

    Implements hybrid token rotation strategy with both per-user and
    global rotation capabilities. Follows SOLID principles:

    - Single Responsibility: Only token rotation logic
    - Open-Closed: Extendable rotation strategies
    - Liskov Substitution: Works with any AsyncSession implementation
    - Interface Segregation: Minimal public API
    - Dependency Inversion: Depends on abstractions (AsyncSession)

    Example:
        >>> service = TokenRotationService(session)
        >>> result = await service.rotate_user_tokens(
        ...     user_id=uuid,
        ...     reason="Password changed"
        ... )
        >>> print(f"Revoked {result.tokens_revoked} tokens")
    """

    def __init__(self, session: AsyncSession):
        """Initialize service with database session.

        Args:
            session: Async database session for queries.
        """
        self.session = session

    async def get_security_config(self) -> SecurityConfig:
        """Get global security configuration singleton.

        Returns:
            SecurityConfig singleton instance.

        Raises:
            RuntimeError: If security_config table is empty (should never happen).
        """
        result = await self.session.execute(select(SecurityConfig))
        config = result.scalar_one_or_none()

        if not config:
            # This should never happen (migration inserts row)
            raise RuntimeError("security_config table is empty (database corruption?)")

        return config

    async def rotate_user_tokens(
        self,
        user_id: UUID,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenRotationResult:
        """Rotate all tokens for a specific user (targeted rotation).

        Use cases:
        - Password change
        - User requests logout from all devices
        - Suspicious activity detected for user
        - User-specific security event

        Algorithm:
        1. Get max token version currently in use by user
        2. Set user's min_token_version to max + 1
        3. Mark all tokens below new minimum as revoked

        Args:
            user_id: UUID of user whose tokens to rotate.
            reason: Human-readable reason for rotation (audit trail).
            ip_address: Client IP address for audit trail.
            user_agent: Client User-Agent for audit trail.

        Returns:
            TokenRotationResult with rotation details.

        Example:
            >>> result = await service.rotate_user_tokens(
            ...     user_id=uuid.UUID("..."),
            ...     reason="Password changed by user"
            ... )
            >>> print(f"Version {result.old_version} → {result.new_version}")
        """
        # Get user's current minimum version
        result = await self.session.execute(
            select(User.min_token_version).where(User.id == user_id)
        )
        old_version = result.scalar_one()

        # Get max token version currently in use (0 if no tokens)
        result = await self.session.execute(
            select(func.max(RefreshToken.token_version)).where(
                RefreshToken.user_id == user_id
            )
        )
        max_version = result.scalar() or 0

        # New minimum is max + 1 (invalidates all existing tokens)
        new_min_version = max(old_version, max_version) + 1

        # Update user's minimum version
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(min_token_version=new_min_version)
        )

        # Revoke all tokens below new minimum
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_version < new_min_version,
                ~RefreshToken.is_revoked,
            )
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
            .returning(RefreshToken.id)
        )
        revoked_tokens = result.scalars().all()

        await self.session.commit()

        logger.info(
            f"USER token rotation: user_id={user_id}, "
            f"version {old_version} → {new_min_version}, "
            f"revoked {len(revoked_tokens)} tokens, "
            f"reason='{reason}'"
        )

        return TokenRotationResult(
            rotation_type="USER",
            user_id=user_id,
            old_version=old_version,
            new_version=new_min_version,
            tokens_revoked=len(revoked_tokens),
            reason=reason,
        )

    async def rotate_all_tokens_global(
        self,
        reason: str,
        initiated_by: str,
        grace_period_minutes: int = 15,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenRotationResult:
        """Rotate ALL tokens system-wide (nuclear option for major breaches).

        Use cases:
        - Encryption key compromise
        - Database breach requiring mass logout
        - Critical security vulnerability discovered
        - Regulatory compliance requirement

        Algorithm:
        1. Increment global_min_token_version by 1
        2. Count affected tokens and users (for reporting)
        3. Mark all old tokens as revoked (with grace period)
        4. Log critical security event with full audit trail

        Args:
            reason: Why global rotation was initiated (audit trail).
            initiated_by: Who initiated (e.g., "ADMIN:john@example.com").
            grace_period_minutes: Minutes before full revocation (default 15).
            ip_address: Client IP address for audit trail.
            user_agent: Client User-Agent for audit trail.

        Returns:
            TokenRotationResult with global rotation details.

        Example:
            >>> result = await service.rotate_all_tokens_global(
            ...     reason="Encryption key rotated",
            ...     initiated_by="ADMIN:security@example.com",
            ...     grace_period_minutes=15
            ... )
            >>> print(f"Affected {result.users_affected} users")

        Warning:
            This is a nuclear option. All users will be logged out.
            Use only for genuine security emergencies.
        """
        # Get current global configuration
        config = await self.get_security_config()
        old_version = config.global_min_token_version
        new_version = old_version + 1

        # Update global minimum version
        await self.session.execute(
            update(SecurityConfig).values(
                global_min_token_version=new_version,
                updated_at=datetime.now(timezone.utc),
                updated_by=initiated_by,
                reason=reason,
            )
        )

        # Count tokens that will be invalidated
        result = await self.session.execute(
            select(func.count(RefreshToken.id)).where(
                RefreshToken.global_version_at_issuance < new_version,
                ~RefreshToken.is_revoked,
            )
        )
        affected_tokens = result.scalar()

        # Count affected users
        result = await self.session.execute(
            select(func.count(func.distinct(RefreshToken.user_id))).where(
                RefreshToken.global_version_at_issuance < new_version,
                ~RefreshToken.is_revoked,
            )
        )
        affected_users = result.scalar()

        # Mark all old tokens as revoked (with grace period)
        revocation_time = datetime.now(timezone.utc) + timedelta(
            minutes=grace_period_minutes
        )
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.global_version_at_issuance < new_version,
                ~RefreshToken.is_revoked,
            )
            .values(
                is_revoked=True,
                revoked_at=revocation_time,  # Delayed revocation
            )
        )

        await self.session.commit()

        # Log critical security event
        logger.critical(
            f"GLOBAL TOKEN ROTATION: version {old_version} → {new_version}. "
            f"Reason: {reason}. Initiated by: {initiated_by}. "
            f"Affected: {affected_users} users, {affected_tokens} tokens. "
            f"Grace period: {grace_period_minutes} minutes."
        )

        return TokenRotationResult(
            rotation_type="GLOBAL",
            old_version=old_version,
            new_version=new_version,
            tokens_revoked=affected_tokens,
            users_affected=affected_users,
            reason=reason,
            initiated_by=initiated_by,
            grace_period_minutes=grace_period_minutes,
        )
