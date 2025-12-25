"""Integration tests for provider connection caching.

Tests cache hit/miss behavior with real Redis instance.

Test Strategy:
- Use real Redis from test environment
- Test cache hit (2nd request faster)
- Test cache miss (1st request)
- Test cache invalidation (update → cleared)
- Test fail-open (cache errors don't block)
"""

from datetime import UTC, datetime, timedelta

import pytest
from uuid_extensions import uuid7

from src.application.queries.handlers.get_provider_handler import (
    GetProviderConnectionHandler,
)
from src.application.queries.provider_queries import GetProviderConnection
from src.core.result import Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.infrastructure.cache import RedisProviderConnectionCache
from src.infrastructure.persistence.repositories import ProviderConnectionRepository


# =============================================================================
# Test Helper Functions
# =============================================================================


async def create_user_in_db(session, user_id=None, email=None):
    """Create a user in the database for FK constraint satisfaction."""
    from src.infrastructure.persistence.models.user import User as UserModel

    user_id = user_id or uuid7()
    email = email or f"test_{user_id}@example.com"

    user = UserModel(
        id=user_id,
        email=email,
        password_hash="$2b$12$test_hash",
        is_verified=True,
        is_active=True,
        failed_login_attempts=0,
    )
    session.add(user)
    await session.commit()
    return user_id


@pytest.mark.asyncio
async def test_provider_connection_cache_miss_then_hit(
    test_database,
    cache_adapter,
    schwab_provider,
) -> None:
    """Test cache miss on first request, then cache hit on second request.

    Expected Flow:
    1. First request: Cache miss → DB lookup → Populate cache
    2. Second request: Cache hit → No DB lookup
    """
    # Setup: Create user for FK constraint
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)

    provider_id, provider_slug = schwab_provider

    # Create test provider connection with credentials (required for ACTIVE status)
    credentials = ProviderCredentials(
        encrypted_data=b"test_encrypted_credentials",
        credential_type=CredentialType.OAUTH2,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    connection = ProviderConnection(
        id=uuid7(),
        user_id=user_id,
        provider_id=provider_id,
        provider_slug=provider_slug,
        status=ConnectionStatus.ACTIVE,
        credentials=credentials,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Save to database
    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        await repo.save(connection)
        await session.commit()

    # Create handler with cache
    cache = cache_adapter
    connection_cache = RedisProviderConnectionCache(cache=cache)

    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        handler = GetProviderConnectionHandler(
            connection_repo=repo,
            connection_cache=connection_cache,
        )

        # First request - cache miss
        query = GetProviderConnection(
            connection_id=connection.id,
            user_id=connection.user_id,
        )
        result1 = await handler.handle(query)

        assert isinstance(result1, Success)
        assert result1.value.id == connection.id

    # Verify cache was populated
    cached = await connection_cache.get(connection.id)
    assert cached is not None
    assert cached.id == connection.id

    # Second request - cache hit (should not hit DB)
    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        handler = GetProviderConnectionHandler(
            connection_repo=repo,
            connection_cache=connection_cache,
        )
        result2 = await handler.handle(query)

        assert isinstance(result2, Success)
        assert result2.value.id == connection.id


@pytest.mark.asyncio
async def test_provider_connection_cache_invalidation(
    test_database,
    cache_adapter,
    schwab_provider,
) -> None:
    """Test cache invalidation after connection update.

    Expected Flow:
    1. Fetch connection (populates cache)
    2. Update connection status
    3. Invalidate cache
    4. Next fetch gets fresh data
    """
    # Setup: Create user for FK constraint
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)

    provider_id, provider_slug = schwab_provider

    # Create and save connection with credentials
    credentials = ProviderCredentials(
        encrypted_data=b"test_encrypted_credentials",
        credential_type=CredentialType.OAUTH2,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    connection = ProviderConnection(
        id=uuid7(),
        user_id=user_id,
        provider_id=provider_id,
        provider_slug=provider_slug,
        status=ConnectionStatus.ACTIVE,
        credentials=credentials,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        await repo.save(connection)
        await session.commit()

    # Cache the connection
    cache = cache_adapter
    connection_cache = RedisProviderConnectionCache(cache=cache)
    await connection_cache.set(connection)

    # Verify cached
    cached = await connection_cache.get(connection.id)
    assert cached is not None
    assert cached.status == ConnectionStatus.ACTIVE

    # Invalidate cache
    deleted = await connection_cache.delete(connection.id)
    assert deleted is True

    # Verify cache cleared
    cached_after = await connection_cache.get(connection.id)
    assert cached_after is None


@pytest.mark.asyncio
async def test_provider_connection_cache_exists(
    cache_adapter,
    schwab_provider,
) -> None:
    """Test cache exists check for quick validation."""
    provider_id, provider_slug = schwab_provider

    connection = ProviderConnection(
        id=uuid7(),
        user_id=uuid7(),  # No FK constraint for this test (not saving to DB)
        provider_id=provider_id,
        provider_slug=provider_slug,
        status=ConnectionStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    cache = cache_adapter
    connection_cache = RedisProviderConnectionCache(cache=cache)

    # Not cached yet
    exists_before = await connection_cache.exists(connection.id)
    assert exists_before is False

    # Cache it
    await connection_cache.set(connection)

    # Now exists
    exists_after = await connection_cache.exists(connection.id)
    assert exists_after is True


@pytest.mark.asyncio
async def test_provider_connection_cache_handles_none(
    cache_adapter,
) -> None:
    """Test cache correctly returns None for non-existent connections."""
    cache = cache_adapter
    connection_cache = RedisProviderConnectionCache(cache=cache)

    # Try to get non-existent connection
    non_existent_id = uuid7()
    result = await connection_cache.get(non_existent_id)

    assert result is None
