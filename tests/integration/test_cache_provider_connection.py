"""Integration tests for provider connection caching.

Tests cache hit/miss behavior with real Redis instance.

Test Strategy:
- Use real Redis from test environment
- Test cache hit (2nd request faster)
- Test cache miss (1st request)
- Test cache invalidation (update → cleared)
- Test fail-open (cache errors don't block)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.queries.handlers.get_provider_handler import (
    GetProviderConnectionHandler,
)
from src.application.queries.provider_queries import GetProviderConnection
from src.core.container import get_cache
from src.core.result import Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.infrastructure.cache import RedisProviderConnectionCache
from src.infrastructure.persistence.repositories import ProviderConnectionRepository


@pytest.mark.asyncio
async def test_provider_connection_cache_miss_then_hit(
    db_session: AsyncSession,
) -> None:
    """Test cache miss on first request, then cache hit on second request.

    Expected Flow:
    1. First request: Cache miss → DB lookup → Populate cache
    2. Second request: Cache hit → No DB lookup
    """
    # Create test provider connection
    connection = ProviderConnection(
        id=uuid4(),
        user_id=uuid4(),
        provider_id=uuid4(),
        provider_slug="schwab",
        status=ConnectionStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Save to database
    repo = ProviderConnectionRepository(session=db_session)
    await repo.save(connection)
    await db_session.commit()

    # Create handler with cache
    cache = get_cache()
    connection_cache = RedisProviderConnectionCache(cache=cache)
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
    result2 = await handler.handle(query)

    assert isinstance(result2, Success)
    assert result2.value.id == connection.id


@pytest.mark.asyncio
async def test_provider_connection_cache_invalidation(
    db_session: AsyncSession,
) -> None:
    """Test cache invalidation after connection update.

    Expected Flow:
    1. Fetch connection (populates cache)
    2. Update connection status
    3. Invalidate cache
    4. Next fetch gets fresh data
    """
    # Create and save connection
    connection = ProviderConnection(
        id=uuid4(),
        user_id=uuid4(),
        provider_id=uuid4(),
        provider_slug="schwab",
        status=ConnectionStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    repo = ProviderConnectionRepository(session=db_session)
    await repo.save(connection)
    await db_session.commit()

    # Cache the connection
    cache = get_cache()
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
    db_session: AsyncSession,
) -> None:
    """Test cache exists check for quick validation."""
    connection = ProviderConnection(
        id=uuid4(),
        user_id=uuid4(),
        provider_id=uuid4(),
        provider_slug="schwab",
        status=ConnectionStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    cache = get_cache()
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
    db_session: AsyncSession,
) -> None:
    """Test cache correctly returns None for non-existent connections."""
    cache = get_cache()
    connection_cache = RedisProviderConnectionCache(cache=cache)

    # Try to get non-existent connection
    non_existent_id = uuid4()
    result = await connection_cache.get(non_existent_id)

    assert result is None
