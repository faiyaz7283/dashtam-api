"""Provider seeder for default providers.

Seeds default providers (Schwab, Alpaca) into the providers table.
Idempotent via slug uniqueness check - safe to run on every migration.

These are the built-in providers that ship with Dashtam. Future providers
(Chase, Fidelity, etc.) can be added here or via admin APIs.

Reference:
    - docs/architecture/provider-domain-model.md
    - docs/guides/database-seeding.md
"""

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_extensions import uuid7

logger = structlog.get_logger(__name__)

# Default providers to seed
# These are the built-in providers that ship with Dashtam
DEFAULT_PROVIDERS = [
    {
        "slug": "schwab",
        "name": "Charles Schwab",
        "category": "brokerage",
        "credential_type": "oauth2",
        "description": "Connect your Charles Schwab brokerage account to sync "
        "accounts, positions, and transactions.",
        "website_url": "https://www.schwab.com",
        "is_active": True,
    },
    {
        "slug": "alpaca",
        "name": "Alpaca",
        "category": "brokerage",
        "credential_type": "api_key",
        "description": "Connect your Alpaca brokerage account to sync "
        "accounts, positions, and transactions. Supports both paper and live trading.",
        "website_url": "https://alpaca.markets",
        "is_active": True,
    },
    # Future providers can be added here:
    # {
    #     "slug": "chase",
    #     "name": "Chase Bank",
    #     "credential_type": "oauth2",
    #     "description": "Connect your Chase Bank accounts.",
    #     "website_url": "https://www.chase.com",
    #     "is_active": False,  # Not yet implemented
    # },
]


async def seed_providers(session: AsyncSession) -> None:
    """Seed default providers. Idempotent via slug uniqueness check.

    Seeds built-in providers like Schwab that ship with Dashtam.
    Uses existence check to ensure idempotency.

    Args:
        session: Async database session.
    """
    seeded_count = 0
    skipped_count = 0

    for provider_data in DEFAULT_PROVIDERS:
        slug = provider_data["slug"]

        # Check if provider already exists by slug
        result = await session.execute(
            text("SELECT 1 FROM providers WHERE slug = :slug LIMIT 1"),
            {"slug": slug},
        )

        if result.fetchone() is not None:
            skipped_count += 1
            logger.debug("provider_exists", slug=slug)
            continue

        # Generate UUID for new provider
        provider_id = uuid7()

        # Insert provider
        await session.execute(
            text("""
                INSERT INTO providers (
                    id, slug, name, category, credential_type, description,
                    logo_url, website_url, is_active,
                    created_at, updated_at
                )
                VALUES (
                    :id, :slug, :name, :category, :credential_type, :description,
                    :logo_url, :website_url, :is_active,
                    NOW(), NOW()
                )
            """),
            {
                "id": provider_id,
                "slug": slug,
                "name": provider_data["name"],
                "category": provider_data.get("category", "other"),
                "credential_type": provider_data["credential_type"],
                "description": provider_data.get("description"),
                "logo_url": provider_data.get("logo_url"),
                "website_url": provider_data.get("website_url"),
                "is_active": provider_data["is_active"],
            },
        )
        seeded_count += 1
        logger.info("provider_seeded", slug=slug, id=str(provider_id))

    logger.info(
        "provider_seeding_complete",
        seeded=seeded_count,
        skipped=skipped_count,
        total=len(DEFAULT_PROVIDERS),
    )
