"""Database seeding package.

Provides idempotent seeders that run automatically after Alembic migrations.
All seeders use ON CONFLICT DO NOTHING to be safe for repeated runs.

Reference:
    - docs/guides/database-seeding.md
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from seeds.provider_seeder import seed_providers
from seeds.rbac_seeder import seed_rbac_policies

logger = structlog.get_logger(__name__)


async def run_all_seeders(session: AsyncSession) -> None:
    """Run all database seeders. Called after Alembic migrations.

    All seeders are idempotent - safe to run on every migration.
    Uses ON CONFLICT DO NOTHING or existence checks for insert operations.

    Args:
        session: Async database session.
    """
    logger.info("seeding_started")

    # Run RBAC seeder (F1.1b - User Authorization)
    await seed_rbac_policies(session)

    # Run Provider seeder (F4.1 - Provider Integration)
    await seed_providers(session)

    # Add future seeders here:
    # await seed_security_config(session)  # F1.3b - Token Breach Rotation
    # await seed_feature_flags(session)

    logger.info("seeding_completed")


__all__ = ["run_all_seeders", "seed_providers", "seed_rbac_policies"]
