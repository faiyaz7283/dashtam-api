"""SecurityConfigRepository - SQLAlchemy implementation.

Adapter for hexagonal architecture.
Maps between domain SecurityConfig entity and database SecurityConfig model.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.security_config import SecurityConfig
from src.infrastructure.persistence.models.security_config import (
    SecurityConfig as SecurityConfigModel,
)


class SecurityConfigRepository:
    """SQLAlchemy implementation of SecurityConfigRepository protocol.

    This is an adapter that implements the SecurityConfigRepository port.
    It handles the mapping between domain SecurityConfig entity and database model.

    Note:
        SecurityConfig is a singleton table (only one row with id=1).
        Use get_or_create_default() to ensure the config exists.

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = SecurityConfigRepository(session)
        ...     config = await repo.get_or_create_default()
        ...     print(config.global_min_token_version)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def get(self) -> SecurityConfig | None:
        """Get the security configuration.

        Returns the singleton security config row.

        Returns:
            SecurityConfig if exists, None if not initialized.
        """
        stmt = select(SecurityConfigModel).where(SecurityConfigModel.id == 1)
        result = await self.session.execute(stmt)
        config_model = result.scalar_one_or_none()

        if config_model is None:
            return None

        return self._to_domain(config_model)

    async def get_or_create_default(self) -> SecurityConfig:
        """Get security config or create with defaults.

        Ensures the singleton config row exists.
        Creates with default values if missing.

        Returns:
            SecurityConfig: The singleton configuration.

        Default values:
            - global_min_token_version: 1
            - grace_period_seconds: 300 (5 minutes)
        """
        config = await self.get()
        if config is not None:
            return config

        # Create default config
        config_model = SecurityConfigModel(
            id=1,
            global_min_token_version=1,
            grace_period_seconds=300,
            last_rotation_at=None,
            last_rotation_reason=None,
        )
        self.session.add(config_model)
        await self.session.commit()
        await self.session.refresh(config_model)

        return self._to_domain(config_model)

    async def update_global_version(
        self,
        new_version: int,
        reason: str,
        rotation_time: datetime,
    ) -> SecurityConfig:
        """Update global minimum token version.

        Used to trigger global token rotation (invalidate all tokens
        with version below new_version).

        Args:
            new_version: New global minimum token version.
            reason: Reason for rotation (for audit trail).
            rotation_time: When rotation was triggered.

        Returns:
            Updated SecurityConfig.

        Raises:
            ValueError: If new_version <= current version.
        """
        stmt = select(SecurityConfigModel).where(SecurityConfigModel.id == 1)
        result = await self.session.execute(stmt)
        config_model = result.scalar_one_or_none()

        if config_model is None:
            # Create default first, then update
            config_model = SecurityConfigModel(
                id=1,
                global_min_token_version=1,
                grace_period_seconds=300,
            )
            self.session.add(config_model)
            await self.session.flush()

        if new_version <= config_model.global_min_token_version:
            raise ValueError(
                f"New version ({new_version}) must be greater than "
                f"current version ({config_model.global_min_token_version})"
            )

        config_model.global_min_token_version = new_version
        config_model.last_rotation_at = rotation_time
        config_model.last_rotation_reason = reason

        await self.session.commit()
        await self.session.refresh(config_model)

        return self._to_domain(config_model)

    async def update_grace_period(
        self,
        grace_period_seconds: int,
    ) -> SecurityConfig:
        """Update grace period for token rotation.

        Args:
            grace_period_seconds: New grace period in seconds.

        Returns:
            Updated SecurityConfig.

        Raises:
            ValueError: If grace_period_seconds < 0.
        """
        if grace_period_seconds < 0:
            raise ValueError("Grace period cannot be negative")

        stmt = select(SecurityConfigModel).where(SecurityConfigModel.id == 1)
        result = await self.session.execute(stmt)
        config_model = result.scalar_one_or_none()

        if config_model is None:
            # Create default first, then update
            config_model = SecurityConfigModel(
                id=1,
                global_min_token_version=1,
                grace_period_seconds=grace_period_seconds,
            )
            self.session.add(config_model)
        else:
            config_model.grace_period_seconds = grace_period_seconds

        await self.session.commit()
        await self.session.refresh(config_model)

        return self._to_domain(config_model)

    def _to_domain(self, config_model: SecurityConfigModel) -> SecurityConfig:
        """Convert database model to domain entity.

        Args:
            config_model: SQLAlchemy SecurityConfigModel instance.

        Returns:
            Domain SecurityConfig entity.
        """
        return SecurityConfig(
            id=config_model.id,
            global_min_token_version=config_model.global_min_token_version,
            grace_period_seconds=config_model.grace_period_seconds,
            last_rotation_at=config_model.last_rotation_at,
            last_rotation_reason=config_model.last_rotation_reason,
            created_at=config_model.created_at,
            updated_at=config_model.updated_at,
        )
