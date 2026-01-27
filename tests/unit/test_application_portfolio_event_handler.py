"""Unit tests for PortfolioEventHandler (Issue #257).

Tests cover:
- Handler initialization with dependencies
- Balance updated event triggers net worth recalculation
- Holdings updated event triggers net worth recalculation
- Event emission when net worth changes
- No event emission when net worth unchanged
- Cache handling (get/set, fail-open behavior)
- Error handling (non-critical, fail-open)
- Logging at appropriate levels

Test Strategy:
- Mock protocols (LoggerProtocol, CacheProtocol, EventBusProtocol)
- Mock Database and AccountRepository
- Test behavior, not implementation details
- Verify correct event emission based on net worth delta

Reference:
    - src/application/event_handlers/portfolio_event_handler.py
    - GitHub Issue #257
"""

from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.event_handlers.portfolio_event_handler import PortfolioEventHandler
from src.core.result import Failure, Success
from src.domain.events.portfolio_events import (
    AccountBalanceUpdated,
    AccountHoldingsUpdated,
    PortfolioNetWorthRecalculated,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create mock LoggerProtocol."""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


@pytest.fixture
def mock_cache():
    """Create mock CacheProtocol."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=Success(value=None))
    cache.set = AsyncMock(return_value=Success(value=None))
    return cache


@pytest.fixture
def mock_event_bus():
    """Create mock EventBusProtocol."""
    event_bus = MagicMock()
    event_bus.publish = AsyncMock(return_value=None)
    return event_bus


@pytest.fixture
def mock_database():
    """Create mock Database with session context manager."""
    database = MagicMock()
    # Mock session context manager
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    database.get_session = MagicMock(return_value=mock_session)
    return database


@pytest.fixture
def mock_account_repo():
    """Create mock AccountRepository."""
    repo = MagicMock()
    repo.sum_balances_for_user = AsyncMock(return_value=Decimal("10000.00"))
    repo.count_for_user = AsyncMock(return_value=3)
    return repo


@pytest.fixture
def user_id() -> UUID:
    """Provide a test user ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def account_id() -> UUID:
    """Provide a test account ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def handler(mock_database, mock_cache, mock_event_bus, mock_logger):
    """Create PortfolioEventHandler with mock dependencies."""
    return PortfolioEventHandler(
        database=mock_database,
        cache=mock_cache,
        event_bus=mock_event_bus,
        logger=mock_logger,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestPortfolioEventHandlerInitialization:
    """Test PortfolioEventHandler initialization."""

    def test_handler_stores_dependencies(
        self, mock_database, mock_cache, mock_event_bus, mock_logger
    ):
        """Test handler stores all dependencies."""
        handler = PortfolioEventHandler(
            database=mock_database,
            cache=mock_cache,
            event_bus=mock_event_bus,
            logger=mock_logger,
        )

        assert handler._database is mock_database
        assert handler._cache is mock_cache
        assert handler._event_bus is mock_event_bus
        assert handler._logger is mock_logger


# =============================================================================
# Balance Updated Event Tests
# =============================================================================


@pytest.mark.unit
class TestHandleBalanceUpdated:
    """Test handle_balance_updated method."""

    @pytest.mark.asyncio
    async def test_logs_debug_when_balance_updated(
        self, handler, mock_logger, user_id, account_id, mock_account_repo
    ):
        """Test handler logs debug message when balance update received."""
        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("1500.00"),
            delta=Decimal("500.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        mock_logger.debug.assert_any_call(
            "balance_updated_recalculating_networth",
            user_id=str(user_id),
            account_id=str(account_id),
            delta="500.00",
        )

    @pytest.mark.asyncio
    async def test_calls_recalculate_networth(
        self, handler, user_id, account_id, mock_account_repo
    ):
        """Test balance updated triggers net worth recalculation."""
        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("1500.00"),
            delta=Decimal("500.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Verify repository was queried
        mock_account_repo.sum_balances_for_user.assert_called_once_with(user_id)
        mock_account_repo.count_for_user.assert_called_once_with(user_id)


# =============================================================================
# Holdings Updated Event Tests
# =============================================================================


@pytest.mark.unit
class TestHandleHoldingsUpdated:
    """Test handle_holdings_updated method."""

    @pytest.mark.asyncio
    async def test_logs_debug_when_holdings_updated(
        self, handler, mock_logger, user_id, account_id, mock_account_repo
    ):
        """Test handler logs debug message when holdings update received."""
        event = AccountHoldingsUpdated(
            user_id=user_id,
            account_id=account_id,
            holdings_count=10,
            created_count=2,
            updated_count=5,
            deactivated_count=3,
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_holdings_updated(event)

        mock_logger.debug.assert_any_call(
            "holdings_updated_recalculating_networth",
            user_id=str(user_id),
            account_id=str(account_id),
            holdings_count=10,
        )

    @pytest.mark.asyncio
    async def test_calls_recalculate_networth(
        self, handler, user_id, account_id, mock_account_repo
    ):
        """Test holdings updated triggers net worth recalculation."""
        event = AccountHoldingsUpdated(
            user_id=user_id,
            account_id=account_id,
            holdings_count=10,
            created_count=2,
            updated_count=5,
            deactivated_count=3,
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_holdings_updated(event)

        # Verify repository was queried
        mock_account_repo.sum_balances_for_user.assert_called_once_with(user_id)


# =============================================================================
# Net Worth Recalculation Tests
# =============================================================================


@pytest.mark.unit
class TestRecalculateNetworth:
    """Test _recalculate_networth method behavior."""

    @pytest.mark.asyncio
    async def test_emits_event_when_networth_changed(
        self,
        handler,
        mock_event_bus,
        mock_cache,
        user_id,
        account_id,
        mock_account_repo,
    ):
        """Test event emitted when net worth changes from cached value."""
        # Setup: current net worth is 10000, cache returns previous as 8000
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("10000.00")
        )
        mock_account_repo.count_for_user = AsyncMock(return_value=3)
        mock_cache.get = AsyncMock(return_value=Success(value="8000.00"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("3000.00"),
            delta=Decimal("2000.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Verify event was published
        mock_event_bus.publish.assert_called_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert isinstance(published_event, PortfolioNetWorthRecalculated)
        assert published_event.user_id == user_id
        assert published_event.previous_net_worth == Decimal("8000.00")
        assert published_event.new_net_worth == Decimal("10000.00")
        assert published_event.delta == Decimal("2000.00")
        assert published_event.account_count == 3

    @pytest.mark.asyncio
    async def test_no_event_when_networth_unchanged(
        self,
        handler,
        mock_event_bus,
        mock_cache,
        user_id,
        account_id,
        mock_account_repo,
    ):
        """Test no event emitted when net worth is unchanged."""
        # Setup: current net worth equals cached value
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("10000.00")
        )
        mock_cache.get = AsyncMock(return_value=Success(value="10000.00"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("1000.00"),
            delta=Decimal("0"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Verify no event was published
        mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_emits_event_when_cache_empty(
        self,
        handler,
        mock_event_bus,
        mock_cache,
        user_id,
        account_id,
        mock_account_repo,
    ):
        """Test event emitted when cache has no previous value (first calculation)."""
        # Setup: cache returns None (no previous value)
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("10000.00")
        )
        mock_account_repo.count_for_user = AsyncMock(return_value=2)
        mock_cache.get = AsyncMock(return_value=Success(value=None))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("10000.00"),
            delta=Decimal("10000.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Event should be published (10000 != 0)
        mock_event_bus.publish.assert_called_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert published_event.previous_net_worth == Decimal("0")
        assert published_event.new_net_worth == Decimal("10000.00")

    @pytest.mark.asyncio
    async def test_logs_info_when_networth_changed(
        self, handler, mock_logger, mock_cache, user_id, account_id, mock_account_repo
    ):
        """Test INFO log when net worth changes."""
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("15000.00")
        )
        mock_account_repo.count_for_user = AsyncMock(return_value=4)
        mock_cache.get = AsyncMock(return_value=Success(value="12000.00"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("3000.00"),
            delta=Decimal("3000.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        mock_logger.info.assert_called_once_with(
            "portfolio_networth_recalculated",
            user_id=str(user_id),
            previous="12000.00",
            current="15000.00",
            delta="3000.00",
            account_count=4,
        )

    @pytest.mark.asyncio
    async def test_logs_debug_when_networth_unchanged(
        self, handler, mock_logger, mock_cache, user_id, account_id, mock_account_repo
    ):
        """Test DEBUG log when net worth is unchanged."""
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("10000.00")
        )
        mock_cache.get = AsyncMock(return_value=Success(value="10000.00"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("0"),
            delta=Decimal("0"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Should log debug for unchanged
        mock_logger.debug.assert_any_call(
            "portfolio_networth_unchanged",
            user_id=str(user_id),
            net_worth="10000.00",
        )


# =============================================================================
# Cache Handling Tests
# =============================================================================


@pytest.mark.unit
class TestCacheHandling:
    """Test cache get/set and fail-open behavior."""

    @pytest.mark.asyncio
    async def test_cache_key_format(
        self, handler, mock_cache, user_id, account_id, mock_account_repo
    ):
        """Test cache uses correct key format."""
        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        expected_key = f"portfolio:networth:{user_id}"
        mock_cache.get.assert_called_once_with(expected_key)
        mock_cache.set.assert_called_once()
        actual_key = mock_cache.set.call_args[0][0]
        assert actual_key == expected_key

    @pytest.mark.asyncio
    async def test_updates_cache_with_current_networth(
        self, handler, mock_cache, user_id, account_id, mock_account_repo
    ):
        """Test cache is updated with current net worth value."""
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("25000.50")
        )

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Verify cache.set called with stringified Decimal
        mock_cache.set.assert_called_once()
        _, value = mock_cache.set.call_args[0]
        assert value == "25000.50"

    @pytest.mark.asyncio
    async def test_fail_open_on_cache_get_failure(
        self,
        handler,
        mock_cache,
        mock_event_bus,
        mock_logger,
        user_id,
        account_id,
        mock_account_repo,
    ):
        """Test handler continues with previous=0 when cache get fails."""
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("5000.00")
        )
        mock_account_repo.count_for_user = AsyncMock(return_value=1)
        mock_cache.get = AsyncMock(return_value=Failure(error="Cache connection error"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("5000.00"),
            delta=Decimal("5000.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Should log warning
        mock_logger.warning.assert_any_call(
            "cache_unavailable_for_networth",
            user_id=str(user_id),
            fallback="previous=0",
        )
        # Event should still be published (5000 != 0)
        mock_event_bus.publish.assert_called_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert published_event.previous_net_worth == Decimal("0")

    @pytest.mark.asyncio
    async def test_fail_open_on_cache_set_failure(
        self, handler, mock_cache, mock_logger, user_id, account_id, mock_account_repo
    ):
        """Test handler continues when cache set fails."""
        mock_cache.get = AsyncMock(return_value=Success(value=None))
        mock_cache.set = AsyncMock(return_value=Failure(error="Cache write error"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        # Should log warning but not fail
        mock_logger.warning.assert_called_with(
            "cache_set_failed_for_networth",
            user_id=str(user_id),
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling and fail-open behavior."""

    @pytest.mark.asyncio
    async def test_logs_error_on_repository_failure(
        self, handler, mock_logger, user_id, account_id
    ):
        """Test error logged when repository query fails."""
        mock_failing_repo = MagicMock()
        mock_failing_repo.sum_balances_for_user = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_failing_repo,
        ):
            # Should not raise - fail open
            await handler.handle_balance_updated(event)

        # Should log error
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "portfolio_networth_recalculation_failed"
        assert call_args[1]["user_id"] == str(user_id)

    @pytest.mark.asyncio
    async def test_does_not_propagate_exception(
        self, handler, mock_event_bus, user_id, account_id
    ):
        """Test exceptions don't propagate to caller."""
        mock_failing_repo = MagicMock()
        mock_failing_repo.sum_balances_for_user = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_failing_repo,
        ):
            # This should complete without exception
            await handler.handle_balance_updated(event)

        # No event should be published on error
        mock_event_bus.publish.assert_not_called()


# =============================================================================
# Integration with Event Bus Tests
# =============================================================================


@pytest.mark.unit
class TestEventBusIntegration:
    """Test handler produces correct events for event bus."""

    @pytest.mark.asyncio
    async def test_published_event_has_correct_structure(
        self,
        handler,
        mock_event_bus,
        mock_cache,
        user_id,
        account_id,
        mock_account_repo,
    ):
        """Test PortfolioNetWorthRecalculated event has all required fields."""
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("50000.00")
        )
        mock_account_repo.count_for_user = AsyncMock(return_value=5)
        mock_cache.get = AsyncMock(return_value=Success(value="45000.00"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("5000.00"),
            delta=Decimal("5000.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        mock_event_bus.publish.assert_called_once()
        published = mock_event_bus.publish.call_args[0][0]

        # Verify all fields
        assert isinstance(published, PortfolioNetWorthRecalculated)
        assert published.event_id is not None  # uuid7
        assert published.user_id == user_id
        assert published.previous_net_worth == Decimal("45000.00")
        assert published.new_net_worth == Decimal("50000.00")
        assert published.delta == Decimal("5000.00")
        assert published.currency == "USD"
        assert published.account_count == 5

    @pytest.mark.asyncio
    async def test_negative_delta_handled_correctly(
        self,
        handler,
        mock_event_bus,
        mock_cache,
        user_id,
        account_id,
        mock_account_repo,
    ):
        """Test negative delta (net worth decrease) handled correctly."""
        mock_account_repo.sum_balances_for_user = AsyncMock(
            return_value=Decimal("8000.00")
        )
        mock_account_repo.count_for_user = AsyncMock(return_value=2)
        mock_cache.get = AsyncMock(return_value=Success(value="10000.00"))

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("5000.00"),
            new_balance=Decimal("3000.00"),
            delta=Decimal("-2000.00"),
            currency="USD",
        )

        with patch(
            "src.infrastructure.persistence.repositories.AccountRepository",
            return_value=mock_account_repo,
        ):
            await handler.handle_balance_updated(event)

        mock_event_bus.publish.assert_called_once()
        published = mock_event_bus.publish.call_args[0][0]
        assert published.delta == Decimal("-2000.00")
        assert published.previous_net_worth > published.new_net_worth
