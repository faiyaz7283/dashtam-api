"""Security configuration database model for token breach rotation.

This module defines the SecurityConfig model - a singleton table (single row)
storing global security settings for token version management.

Security:
    - global_min_token_version: Minimum acceptable token version (incremented on breach)
    - grace_period_seconds: Time to allow old tokens after rotation (gradual rollout)
    - Single row constraint: Only one config row allowed (id=1)

Reference:
    - docs/architecture/token-breach-rotation-architecture.md
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class SecurityConfig(BaseMutableModel):
    """Security configuration model for token version management.

    This is a singleton table - only one row with id=1 is allowed.
    Stores global security settings used during token validation.

    Note:
        This model uses Integer ID (not UUID like other models) because
        the singleton pattern requires a fixed ID of 1. The id column
        overrides the UUID from BaseMutableModel.

    Token Validation Rule:
        token_version >= max(global_min_token_version, user.min_token_version)

    Use Cases:
        - Database breach: Increment global_min_token_version to invalidate ALL tokens
        - Grace period: Allow old tokens for N seconds during rotation

    Fields:
        id: Always 1 (singleton constraint, Integer NOT UUID)
        created_at: When config was created (from BaseMutableModel)
        updated_at: When config was last modified (from BaseMutableModel)
        global_min_token_version: Minimum acceptable token version globally
        grace_period_seconds: Seconds to allow old tokens after rotation
        last_rotation_at: When global rotation was last triggered
        last_rotation_reason: Why global rotation was triggered

    Constraints:
        - single_row: CHECK (id = 1) ensures only one config row

    Example:
        # Get config (should always exist)
        result = await session.execute(
            select(SecurityConfig).where(SecurityConfig.id == 1)
        )
        config = result.scalar_one()

        # Trigger global rotation
        config.global_min_token_version += 1
        config.last_rotation_at = datetime.now(UTC)
        config.last_rotation_reason = "Database breach detected"
        await session.commit()
    """

    __tablename__ = "security_config"

    # Override id to use Integer (for singleton pattern, id=1)
    # This overrides the UUID from BaseMutableModel
    id: Mapped[int] = mapped_column(  # type: ignore[assignment]
        Integer,
        primary_key=True,
        default=1,
        nullable=False,
    )

    # Global minimum token version (increment to invalidate all tokens below)
    global_min_token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Minimum acceptable token version globally (increment on breach)",
    )

    # Grace period for gradual rotation (seconds)
    grace_period_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,  # 5 minutes default
        comment="Seconds to allow old tokens after rotation (gradual rollout)",
    )

    # Last global rotation tracking
    last_rotation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp when global rotation was last triggered",
    )

    last_rotation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Reason for last global rotation (breach, vulnerability, etc.)",
    )

    # Singleton constraint - only one row with id=1 allowed
    __table_args__ = (CheckConstraint("id = 1", name="single_row_constraint"),)

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of security config.
        """
        return (
            f"<SecurityConfig("
            f"global_min_token_version={self.global_min_token_version}, "
            f"grace_period_seconds={self.grace_period_seconds}, "
            f"last_rotation_at={self.last_rotation_at}"
            f")>"
        )
