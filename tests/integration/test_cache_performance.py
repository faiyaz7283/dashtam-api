"""Performance verification tests for F6.11 cache optimization.

This module verifies that caching provides measurable performance improvements
and that fail-open behavior works correctly.

Test Strategy:
- Measure cache hit vs cache miss performance
- Verify fail-open behavior (cache errors don't block)
- Validate cache metrics accuracy
- Confirm cache invalidation triggers correctly

Note: These are verification tests, not benchmarks. They demonstrate that
caching works and provides improvement, not precise performance numbers.
"""

import time
from datetime import UTC, datetime

import pytest
from uuid_extensions import uuid7

from src.application.queries.handlers.get_provider_handler import (
    GetProviderConnectionHandler,
)
from src.application.queries.provider_queries import GetProviderConnection
from src.core.result import Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.infrastructure.cache import RedisProviderConnectionCache
from src.infrastructure.cache.cache_metrics import CacheMetrics
from src.infrastructure.persistence.repositories import ProviderConnectionRepository


# =============================================================================
# Helper Functions
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


# =============================================================================
# Performance Verification Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_improves_query_performance(
    test_database,
    cache_adapter,
    schwab_provider,
) -> None:
    """Verify that cache provides measurable performance improvement.

    This test demonstrates that:
    1. First request (cache miss) takes longer (DB lookup)
    2. Second request (cache hit) is faster (no DB lookup)
    3. The improvement is measurable and significant

    Note: This is not a precise benchmark, just verification that
    caching provides benefit.
    """
    # Setup: Create user and connection
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)

    provider_id, provider_slug = schwab_provider

    connection = ProviderConnection(
        id=uuid7(),
        user_id=user_id,
        provider_id=provider_id,
        provider_slug=provider_slug,
        status=ConnectionStatus.PENDING,
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

    query = GetProviderConnection(
        connection_id=connection.id,
        user_id=user_id,
    )

    # First request - cache miss (slower, includes DB lookup)
    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        handler = GetProviderConnectionHandler(
            connection_repo=repo,
            connection_cache=connection_cache,
        )

        start_miss = time.perf_counter()
        result1 = await handler.handle(query)
        time_miss = time.perf_counter() - start_miss

    assert isinstance(result1, Success)

    # Second request - cache hit (faster, no DB lookup)
    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        handler = GetProviderConnectionHandler(
            connection_repo=repo,
            connection_cache=connection_cache,
        )

        start_hit = time.perf_counter()
        result2 = await handler.handle(query)
        time_hit = time.perf_counter() - start_hit

    assert isinstance(result2, Success)

    # Verify performance improvement
    # Cache hit should be faster than cache miss
    # We don't assert specific numbers since timing varies by environment,
    # but we verify the relationship holds
    assert time_hit < time_miss, (
        f"Cache hit ({time_hit:.4f}s) should be faster than "
        f"cache miss ({time_miss:.4f}s)"
    )

    # Cache hit should be significantly faster (at least 20% faster)
    # This is a conservative threshold to account for test environment variance
    improvement = (time_miss - time_hit) / time_miss
    assert improvement > 0.20, (
        f"Cache should provide >20% improvement, got {improvement:.1%}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_metrics_track_operations_accurately() -> None:
    """Verify cache metrics accurately track hit/miss/error counts.

    This test ensures that:
    1. Cache metrics count operations correctly
    2. Hit rate calculation is accurate
    3. Multiple namespaces work independently
    """
    metrics = CacheMetrics()

    # Simulate cache operations for "test" namespace
    metrics.record_hit("test")
    metrics.record_hit("test")
    metrics.record_miss("test")
    metrics.record_error("test")

    # Verify test namespace stats
    stats = metrics.get_stats("test")
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["errors"] == 1
    assert stats["total_requests"] == 3  # hits + misses
    # Use pytest.approx for float comparison
    assert stats["hit_rate"] == pytest.approx(2 / 3, rel=1e-3)  # 2 hits out of 3

    # Simulate cache operations for "provider" namespace
    metrics.record_hit("provider")
    metrics.record_miss("provider")
    metrics.record_miss("provider")

    # Verify provider namespace stats
    provider_stats = metrics.get_stats("provider")
    assert provider_stats["hits"] == 1
    assert provider_stats["misses"] == 2
    # Use pytest.approx for float comparison
    assert provider_stats["hit_rate"] == pytest.approx(
        1 / 3, rel=1e-3
    )  # 1 hit out of 3

    # Verify namespaces are independent
    assert stats["hits"] == 2  # Test namespace unchanged

    # Verify get_all_stats works
    all_stats = metrics.get_all_stats()
    assert "test" in all_stats
    assert "provider" in all_stats
    assert len(all_stats) == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_invalidation_verified(
    test_database,
    cache_adapter,
    schwab_provider,
) -> None:
    """Verify cache invalidation works correctly.

    This test ensures that:
    1. Cache can be manually invalidated
    2. Invalidated cache forces fresh DB lookup
    3. Handler repopulates cache on miss
    """
    # Setup: Create user and connection
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)

    provider_id, provider_slug = schwab_provider

    connection = ProviderConnection(
        id=uuid7(),
        user_id=user_id,
        provider_id=provider_id,
        provider_slug=provider_slug,
        status=ConnectionStatus.PENDING,
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

    query = GetProviderConnection(
        connection_id=connection.id,
        user_id=user_id,
    )

    # First request - populates cache
    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        handler = GetProviderConnectionHandler(
            connection_repo=repo,
            connection_cache=connection_cache,
        )
        result1 = await handler.handle(query)

    assert isinstance(result1, Success)

    # Verify cache is populated
    cached = await connection_cache.get(connection.id)
    assert cached is not None

    # Invalidate cache
    deleted = await connection_cache.delete(connection.id)
    assert deleted is True

    # Verify cache is cleared
    cached_after_delete = await connection_cache.get(connection.id)
    assert cached_after_delete is None

    # Next request should repopulate cache
    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        handler = GetProviderConnectionHandler(
            connection_repo=repo,
            connection_cache=connection_cache,
        )
        result2 = await handler.handle(query)

    assert isinstance(result2, Success)

    # Verify cache was repopulated
    cached_after_repopulate = await connection_cache.get(connection.id)
    assert cached_after_repopulate is not None
    assert cached_after_repopulate.id == connection.id


# =============================================================================
# Fail-Open Behavior Verification
# =============================================================================

# Note: Fail-open behavior is verified at the cache layer level, not handler
# level. See test_cache_optimization.py::test_cache_fail_open_on_malformed_data
# for fail-open verification.
#
# Handlers require cache as a dependency (not optional). This is correct
# architecture - cache operations fail-open (Redis errors don't break), but
# handlers always use cache (no cache=None pattern).
#
# If fail-open needs handler-level testing, use a mock cache that raises
# exceptions and verify handler still succeeds via cache error handling.
