"""Portfolio event handler for net worth calculation.

Reacts to balance and holdings changes, recalculates net worth,
and emits PortfolioNetWorthRecalculated events.

Architecture:
    - Application layer (coordination/aggregation logic)
    - App-scoped singleton (created once at startup)
    - Subscribes to AccountBalanceUpdated and AccountHoldingsUpdated
    - Emits PortfolioNetWorthRecalculated when net worth changes

Pattern:
    This is a REACTIVE AGGREGATION handler:
    1. Listens to AccountBalanceUpdated and AccountHoldingsUpdated
    2. Queries repository to calculate current net worth
    3. Compares with cached previous value
    4. Emits PortfolioNetWorthRecalculated if changed

Reference:
    - docs/architecture/domain-events-architecture.md
    - Implementation Plan: Issue #257, Phase 6
"""

from decimal import Decimal
from uuid import UUID

from uuid_extensions import uuid7

from src.core.result import Failure
from src.domain.events.portfolio_events import (
    AccountBalanceUpdated,
    AccountHoldingsUpdated,
    PortfolioNetWorthRecalculated,
)
from src.domain.protocols.cache_protocol import CacheProtocol
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.logger_protocol import LoggerProtocol
from src.infrastructure.persistence.database import Database


class PortfolioEventHandler:
    """Event handler for portfolio net worth calculation.

    Reacts to balance/holdings changes and emits net worth events.
    Follows same pattern as LoggingEventHandler, AuditEventHandler.

    App-scoped singleton, subscribed at container startup.

    Creates database sessions on-demand (same pattern as AuditEventHandler).
    Gets session from event_bus context when handling events.

    Attributes:
        _database: Database instance for creating sessions.
        _cache: For storing previous net worth values.
        _event_bus: For publishing PortfolioNetWorthRecalculated and getting sessions.
        _logger: For structured logging.

    Example:
        >>> # Container creates and subscribes at startup
        >>> handler = PortfolioEventHandler(
        ...     database=get_database(),
        ...     cache=get_cache(),
        ...     event_bus=get_event_bus(),
        ...     logger=get_logger(),
        ... )
        >>> event_bus.subscribe(AccountBalanceUpdated, handler.handle_balance_updated)
        >>> event_bus.subscribe(AccountHoldingsUpdated, handler.handle_holdings_updated)
    """

    def __init__(
        self,
        database: Database,
        cache: CacheProtocol,
        event_bus: EventBusProtocol,
        logger: LoggerProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            database: Database instance for creating sessions on-demand.
            cache: Cache for storing previous net worth values.
            event_bus: Event bus for publishing derived events and getting session context.
            logger: Logger protocol implementation from container.
        """
        self._database = database
        self._cache = cache
        self._event_bus = event_bus
        self._logger = logger

    async def handle_balance_updated(self, event: AccountBalanceUpdated) -> None:
        """React to balance change, recalculate net worth.

        Args:
            event: AccountBalanceUpdated event with user_id.
        """
        self._logger.debug(
            "balance_updated_recalculating_networth",
            user_id=str(event.user_id),
            account_id=str(event.account_id),
            delta=str(event.delta),
        )
        await self._recalculate_networth(event.user_id)

    async def handle_holdings_updated(self, event: AccountHoldingsUpdated) -> None:
        """React to holdings change, recalculate net worth.

        Args:
            event: AccountHoldingsUpdated event with user_id.
        """
        self._logger.debug(
            "holdings_updated_recalculating_networth",
            user_id=str(event.user_id),
            account_id=str(event.account_id),
            holdings_count=event.holdings_count,
        )
        await self._recalculate_networth(event.user_id)

    async def _recalculate_networth(self, user_id: UUID) -> None:
        """Calculate current net worth and emit event if changed.

        Creates a database session, queries repository for current total,
        compares with cached previous value, and emits PortfolioNetWorthRecalculated
        if the value changed.

        Args:
            user_id: User whose net worth to recalculate.
        """
        try:
            # Create session and repository for this query
            async with self._database.get_session() as session:
                from src.infrastructure.persistence.repositories import (
                    AccountRepository,
                )

                account_repo = AccountRepository(session=session)

                # Query current total from repository
                current = await account_repo.sum_balances_for_user(user_id)
                account_count = await account_repo.count_for_user(user_id)

            # Get previous from cache (fail-open if cache unavailable)
            cache_key = f"portfolio:networth:{user_id}"
            cached_result = await self._cache.get(cache_key)

            previous = Decimal("0")
            if isinstance(cached_result, Failure):
                # Cache error - fail open, assume previous was 0
                self._logger.warning(
                    "cache_unavailable_for_networth",
                    user_id=str(user_id),
                    fallback="previous=0",
                )
            elif cached_result.value is not None:
                previous = Decimal(cached_result.value)

            # Update cache with current value (fail-open if cache unavailable)
            set_result = await self._cache.set(cache_key, str(current))
            if isinstance(set_result, Failure):
                self._logger.warning(
                    "cache_set_failed_for_networth",
                    user_id=str(user_id),
                )

            # Emit event only if net worth changed
            if current != previous:
                await self._event_bus.publish(
                    PortfolioNetWorthRecalculated(
                        event_id=uuid7(),
                        user_id=user_id,
                        previous_net_worth=previous,
                        new_net_worth=current,
                        delta=current - previous,
                        currency="USD",  # TODO: Get user's base currency from settings
                        account_count=account_count,
                    )
                )
                self._logger.info(
                    "portfolio_networth_recalculated",
                    user_id=str(user_id),
                    previous=str(previous),
                    current=str(current),
                    delta=str(current - previous),
                    account_count=account_count,
                )
            else:
                self._logger.debug(
                    "portfolio_networth_unchanged",
                    user_id=str(user_id),
                    net_worth=str(current),
                )

        except Exception as e:
            # Log error but don't propagate - portfolio calculation is not critical
            # to the sync operation's success
            self._logger.error(
                "portfolio_networth_recalculation_failed",
                error=e,
                user_id=str(user_id),
            )
