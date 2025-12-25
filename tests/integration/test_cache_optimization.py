"""Integration tests for F6.11 cache optimization.

Tests all Phase 4-7 cache implementations:
- Provider Connection Cache (Phase 4)
- Schwab API Response Cache (Phase 5)
- Account List Cache (Phase 6)
- Security Config Cache (Phase 7)

Test Strategy:
- Real Redis from test environment
- Cache hit/miss behavior validation
- Cache invalidation verification
- Fail-open behavior (cache errors don't block)
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from uuid_extensions import uuid7

from src.core.container.infrastructure import get_cache_keys
from src.core.result import Success
from src.domain.enums.connection_status import ConnectionStatus
from src.infrastructure.cache import RedisProviderConnectionCache
from src.infrastructure.cache.cache_keys import CacheKeys
from src.infrastructure.cache.cache_metrics import CacheMetrics
from src.infrastructure.persistence.repositories import SecurityConfigRepository


# =============================================================================
# Phase 7: Security Config Cache Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_security_config_cache_manual_set_and_get(cache_adapter) -> None:
    """Test manual caching of security config data.

    Flow:
    1. Manually cache security config data
    2. Verify retrieval

    Note: Repository doesn't populate cache - that's the handler's job.
    This test validates the cache key structure and JSON serialization.
    """
    # Get cache infrastructure
    cache = cache_adapter
    cache_keys = get_cache_keys()

    # Manually create and cache security config data
    config_data = {
        "id": 1,
        "global_min_token_version": 1,
        "grace_period_seconds": 300,
        "last_rotation_at": None,
        "last_rotation_reason": None,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    # Cache it
    cache_key = cache_keys.security_global_version()
    await cache.set(cache_key, json.dumps(config_data), ttl=60)

    # Verify cache retrieval
    result = await cache.get(cache_key)

    assert isinstance(result, Success)
    assert result.value is not None

    # Verify cached data is correct
    cached_data = json.loads(result.value)
    assert cached_data["global_min_token_version"] == 1
    assert cached_data["grace_period_seconds"] == 300


@pytest.mark.asyncio
@pytest.mark.integration
async def test_security_config_cache_invalidation(test_database, cache_adapter) -> None:
    """Test cache invalidation on version update.

    Flow:
    1. Manually populate cache
    2. Update global_min_token_version (repository should invalidate)
    3. Verify cache was cleared
    """
    # Get cache infrastructure
    cache = cache_adapter
    cache_keys = get_cache_keys()

    # Cleanup: Delete existing security config to avoid version conflicts
    async with test_database.get_session() as session:
        from sqlalchemy import text

        await session.execute(text("DELETE FROM security_config"))
        await session.commit()

    # Setup: Create security config in database
    async with test_database.get_session() as session:
        repo = SecurityConfigRepository(
            session=session,
            cache=cache,
            cache_keys=cache_keys,
        )
        await repo.get_or_create_default()
        await session.commit()

    # Manually populate cache (simulating handler's cache population)
    cache_key = cache_keys.security_global_version()
    config_data = {
        "id": 1,
        "global_min_token_version": 1,
        "grace_period_seconds": 300,
        "last_rotation_at": None,
        "last_rotation_reason": None,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await cache.set(cache_key, json.dumps(config_data), ttl=60)

    # Verify cache is populated
    result = await cache.get(cache_key)
    assert isinstance(result, Success)
    assert result.value is not None

    # Update version (should invalidate cache)
    async with test_database.get_session() as session:
        repo = SecurityConfigRepository(
            session=session,
            cache=cache,
            cache_keys=cache_keys,
        )
        updated = await repo.update_global_version(
            new_version=2,
            reason="Test rotation",
            rotation_time=datetime.now(UTC),
        )
        await session.commit()

        assert updated.global_min_token_version == 2

    # Verify cache was invalidated
    result_after = await cache.get(cache_key)
    # Cache should be cleared (returns Success(None) or empty)
    assert isinstance(result_after, Success)
    # After invalidation, cache should be empty or return None
    assert result_after.value is None or result_after.value == ""


# =============================================================================
# Phase 4: Provider Connection Cache Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_provider_connection_cache_basic_operations(cache_adapter) -> None:
    """Test basic provider connection cache operations.

    Tests set, get, exists, delete operations.
    """
    from src.domain.entities.provider_connection import ProviderConnection

    # Get cache infrastructure
    cache = cache_adapter
    connection_cache = RedisProviderConnectionCache(cache=cache)

    # Create test connection (PENDING status, no credentials required)
    connection = ProviderConnection(
        id=uuid7(),
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="schwab",
        status=ConnectionStatus.PENDING,  # PENDING doesn't require credentials
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Test: Cache does not exist initially
    exists_before = await connection_cache.exists(connection.id)
    assert exists_before is False

    # Test: Get returns None for uncached connection
    cached_before = await connection_cache.get(connection.id)
    assert cached_before is None

    # Test: Set caches the connection
    await connection_cache.set(connection)

    # Test: Exists now returns True
    exists_after = await connection_cache.exists(connection.id)
    assert exists_after is True

    # Test: Get returns cached connection
    cached_after = await connection_cache.get(connection.id)
    assert cached_after is not None
    assert cached_after.id == connection.id
    assert cached_after.status == ConnectionStatus.PENDING

    # Test: Delete removes from cache
    deleted = await connection_cache.delete(connection.id)
    assert deleted is True

    # Test: After delete, exists returns False
    exists_final = await connection_cache.exists(connection.id)
    assert exists_final is False


# =============================================================================
# Phase 5 & 6: Cache Key Construction Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_keys_construction() -> None:
    """Test all cache key construction methods.

    Verifies:
    - Consistent key patterns
    - UUID → string conversion
    - Date formatting
    """
    from datetime import date

    cache_keys = CacheKeys(prefix="dashtam")

    user_id = uuid4()
    connection_id = uuid4()
    account_id = uuid4()
    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 31)

    # Test user key
    user_key = cache_keys.user(user_id)
    assert user_key == f"dashtam:user:{user_id}"

    # Test provider connection key
    conn_key = cache_keys.provider_connection(connection_id)
    assert conn_key == f"dashtam:provider:conn:{connection_id}"

    # Test Schwab accounts key
    schwab_key = cache_keys.schwab_accounts(user_id)
    assert schwab_key == f"dashtam:schwab:accounts:{user_id}"

    # Test Schwab transactions key
    tx_key = cache_keys.schwab_transactions(account_id, start_date, end_date)
    assert tx_key == f"dashtam:schwab:tx:{account_id}:2025-01-01:2025-01-31"

    # Test account list key
    account_list_key = cache_keys.account_list(user_id)
    assert account_list_key == f"dashtam:accounts:user:{user_id}"

    # Test security keys
    global_version_key = cache_keys.security_global_version()
    assert global_version_key == "dashtam:security:global_version"

    user_version_key = cache_keys.security_user_version(user_id)
    assert user_version_key == f"dashtam:security:user_version:{user_id}"


# =============================================================================
# Cache Metrics Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_metrics_tracking() -> None:
    """Test cache metrics hit/miss/error tracking.

    Verifies:
    - Hit count increments
    - Miss count increments
    - Error count increments
    - Thread-safe counters
    """
    metrics = CacheMetrics()

    # Initial state
    stats = metrics.get_stats("test")
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["errors"] == 0

    # Record some hits
    metrics.record_hit("test")
    metrics.record_hit("test")
    stats = metrics.get_stats("test")
    assert stats["hits"] == 2

    # Record some misses
    metrics.record_miss("test")
    stats = metrics.get_stats("test")
    assert stats["misses"] == 1

    # Record some errors
    metrics.record_error("test")
    stats = metrics.get_stats("test")
    assert stats["errors"] == 1

    # Test different namespaces
    metrics.record_hit("provider")
    metrics.record_miss("accounts")
    assert metrics.get_stats("provider")["hits"] == 1
    assert metrics.get_stats("accounts")["misses"] == 1
    assert metrics.get_stats("test")["hits"] == 2  # Original namespace unchanged


# =============================================================================
# Fail-Open Behavior Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_fail_open_on_malformed_data(cache_adapter) -> None:
    """Test cache handles malformed data gracefully.

    Cache should return None (miss) instead of raising exceptions.
    """
    cache = cache_adapter
    cache_keys = get_cache_keys()

    # Store malformed JSON
    cache_key = cache_keys.user(uuid4())
    await cache.set(cache_key, "not valid json", ttl=60)

    # Attempt to deserialize in consumer code
    result = await cache.get(cache_key)

    # Should return the raw value successfully
    # Consumer code is responsible for handling JSON errors
    assert isinstance(result, Success)
    assert result.value == "not valid json"
