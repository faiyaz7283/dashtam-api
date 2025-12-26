"""Data handler dependency factories.

Request-scoped handler instances for account, holding, and transaction operations:
- Account queries (get, list by connection, list by user)
- Holding queries (list by account, list by user)
- Transaction queries (get, list by account, list by date range, list security)
- Sync commands (accounts, holdings, transactions)

Reference:
    See docs/architecture/cqrs-pattern.md for handler patterns.
"""

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.container.events import get_event_bus
from src.core.container.infrastructure import get_db_session, get_encryption_service
from src.core.container.providers import get_provider

if TYPE_CHECKING:
    from src.application.commands.handlers.sync_accounts_handler import (
        SyncAccountsHandler,
    )
    from src.application.commands.handlers.sync_holdings_handler import (
        SyncHoldingsHandler,
    )
    from src.application.commands.handlers.sync_transactions_handler import (
        SyncTransactionsHandler,
    )
    from src.application.queries.handlers.get_account_handler import GetAccountHandler
    from src.application.queries.handlers.get_transaction_handler import (
        GetTransactionHandler,
    )
    from src.application.queries.handlers.list_accounts_handler import (
        ListAccountsByConnectionHandler,
        ListAccountsByUserHandler,
    )
    from src.application.queries.handlers.list_holdings_handler import (
        ListHoldingsByAccountHandler,
        ListHoldingsByUserHandler,
    )
    from src.application.queries.handlers.list_transactions_handler import (
        ListSecurityTransactionsHandler,
        ListTransactionsByAccountHandler,
        ListTransactionsByDateRangeHandler,
    )


# ============================================================================
# Account Query Handler Factories (Request-Scoped)
# ============================================================================


async def get_get_account_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "GetAccountHandler":
    """Get GetAccount query handler (request-scoped).

    Creates handler with:
    - AccountRepository (request-scoped)
    - ProviderConnectionRepository (request-scoped for ownership verification)

    Returns:
        GetAccountHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.get_account_handler import (
        GetAccountHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
    )

    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)

    return GetAccountHandler(
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_list_accounts_by_connection_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListAccountsByConnectionHandler":
    """Get ListAccountsByConnection query handler (request-scoped).

    Creates handler with:
    - AccountRepository (request-scoped)
    - ProviderConnectionRepository (request-scoped for ownership verification)

    Returns:
        ListAccountsByConnectionHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_accounts_handler import (
        ListAccountsByConnectionHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
    )

    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)

    return ListAccountsByConnectionHandler(
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_list_accounts_by_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListAccountsByUserHandler":
    """Get ListAccountsByUser query handler (request-scoped).

    Creates handler with:
    - AccountRepository (request-scoped)

    Returns:
        ListAccountsByUserHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_accounts_handler import (
        ListAccountsByUserHandler,
    )
    from src.infrastructure.persistence.repositories import AccountRepository

    account_repo = AccountRepository(session=session)

    return ListAccountsByUserHandler(
        account_repo=account_repo,
    )


# ============================================================================
# Transaction Query Handler Factories (Request-Scoped)
# ============================================================================


async def get_get_transaction_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "GetTransactionHandler":
    """Get GetTransaction query handler (request-scoped).

    Creates handler with:
    - TransactionRepository (request-scoped)
    - AccountRepository (request-scoped for ownership chain)
    - ProviderConnectionRepository (request-scoped for ownership verification)

    Returns:
        GetTransactionHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.get_transaction_handler import (
        GetTransactionHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
        TransactionRepository,
    )

    transaction_repo = TransactionRepository(session=session)
    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)

    return GetTransactionHandler(
        transaction_repo=transaction_repo,
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_list_transactions_by_account_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListTransactionsByAccountHandler":
    """Get ListTransactionsByAccount query handler (request-scoped).

    Creates handler with:
    - TransactionRepository (request-scoped)
    - AccountRepository (request-scoped for ownership chain)
    - ProviderConnectionRepository (request-scoped for ownership verification)

    Returns:
        ListTransactionsByAccountHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_transactions_handler import (
        ListTransactionsByAccountHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
        TransactionRepository,
    )

    transaction_repo = TransactionRepository(session=session)
    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)

    return ListTransactionsByAccountHandler(
        transaction_repo=transaction_repo,
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_list_transactions_by_date_range_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListTransactionsByDateRangeHandler":
    """Get ListTransactionsByDateRange query handler (request-scoped).

    Creates handler with:
    - TransactionRepository (request-scoped)
    - AccountRepository (request-scoped for ownership chain)
    - ProviderConnectionRepository (request-scoped for ownership verification)

    Returns:
        ListTransactionsByDateRangeHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_transactions_handler import (
        ListTransactionsByDateRangeHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
        TransactionRepository,
    )

    transaction_repo = TransactionRepository(session=session)
    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)

    return ListTransactionsByDateRangeHandler(
        transaction_repo=transaction_repo,
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_list_security_transactions_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListSecurityTransactionsHandler":
    """Get ListSecurityTransactions query handler (request-scoped).

    Creates handler with:
    - TransactionRepository (request-scoped)
    - AccountRepository (request-scoped for ownership chain)
    - ProviderConnectionRepository (request-scoped for ownership verification)

    Returns:
        ListSecurityTransactionsHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_transactions_handler import (
        ListSecurityTransactionsHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
        TransactionRepository,
    )

    transaction_repo = TransactionRepository(session=session)
    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)

    return ListSecurityTransactionsHandler(
        transaction_repo=transaction_repo,
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


# ============================================================================
# Sync Handler Factories (Request-Scoped)
# ============================================================================


async def get_sync_accounts_handler(
    session: AsyncSession = Depends(get_db_session),
    provider_slug: str = "schwab",
) -> "SyncAccountsHandler":
    """Get SyncAccounts command handler (request-scoped).

    Creates handler with:
    - ProviderConnectionRepository (request-scoped)
    - AccountRepository (request-scoped)
    - EncryptionService (app-scoped)
    - Provider adapter (created from slug)
    - EventBus (app-scoped)

    Args:
        session: Database session.
        provider_slug: Provider to use for sync (default: schwab).

    Returns:
        SyncAccountsHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.commands.handlers.sync_accounts_handler import (
        SyncAccountsHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
    )

    connection_repo = ProviderConnectionRepository(session=session)
    account_repo = AccountRepository(session=session)
    encryption_service = get_encryption_service()
    provider = get_provider(provider_slug)
    event_bus = get_event_bus()

    return SyncAccountsHandler(
        connection_repo=connection_repo,
        account_repo=account_repo,
        encryption_service=encryption_service,
        provider=provider,
        event_bus=event_bus,
    )


async def get_sync_transactions_handler(
    session: AsyncSession = Depends(get_db_session),
    provider_slug: str = "schwab",
) -> "SyncTransactionsHandler":
    """Get SyncTransactions command handler (request-scoped).

    Creates handler with:
    - ProviderConnectionRepository (request-scoped)
    - AccountRepository (request-scoped)
    - TransactionRepository (request-scoped)
    - EncryptionService (app-scoped)
    - Provider adapter (created from slug)
    - EventBus (app-scoped)

    Args:
        session: Database session.
        provider_slug: Provider to use for sync (default: schwab).

    Returns:
        SyncTransactionsHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.commands.handlers.sync_transactions_handler import (
        SyncTransactionsHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
        TransactionRepository,
    )

    connection_repo = ProviderConnectionRepository(session=session)
    account_repo = AccountRepository(session=session)
    transaction_repo = TransactionRepository(session=session)
    encryption_service = get_encryption_service()
    provider = get_provider(provider_slug)
    event_bus = get_event_bus()

    return SyncTransactionsHandler(
        connection_repo=connection_repo,
        account_repo=account_repo,
        transaction_repo=transaction_repo,
        encryption_service=encryption_service,
        provider=provider,
        event_bus=event_bus,
    )


# ============================================================================
# Holding Query Handler Factories (Request-Scoped)
# ============================================================================


async def get_list_holdings_by_account_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListHoldingsByAccountHandler":
    """Get ListHoldingsByAccount query handler (request-scoped).

    Creates handler with:
    - HoldingRepository (request-scoped)
    - AccountRepository (request-scoped for ownership chain)
    - ProviderConnectionRepository (request-scoped for ownership verification)

    Returns:
        ListHoldingsByAccountHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_holdings_handler import (
        ListHoldingsByAccountHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        HoldingRepository,
        ProviderConnectionRepository,
    )

    holding_repo = HoldingRepository(session=session)
    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)

    return ListHoldingsByAccountHandler(
        holding_repo=holding_repo,
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_list_holdings_by_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListHoldingsByUserHandler":
    """Get ListHoldingsByUser query handler (request-scoped).

    Creates handler with:
    - HoldingRepository (request-scoped)

    Returns:
        ListHoldingsByUserHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_holdings_handler import (
        ListHoldingsByUserHandler,
    )
    from src.infrastructure.persistence.repositories import HoldingRepository

    holding_repo = HoldingRepository(session=session)

    return ListHoldingsByUserHandler(
        holding_repo=holding_repo,
    )


async def get_sync_holdings_handler(
    session: AsyncSession = Depends(get_db_session),
    provider_slug: str = "schwab",
) -> "SyncHoldingsHandler":
    """Get SyncHoldings command handler (request-scoped).

    Creates handler with:
    - AccountRepository (request-scoped)
    - ProviderConnectionRepository (request-scoped)
    - HoldingRepository (request-scoped)
    - EncryptionService (app-scoped)
    - Provider adapter (created from slug)
    - EventBus (app-scoped)

    Args:
        session: Database session.
        provider_slug: Provider to use for sync (default: schwab).

    Returns:
        SyncHoldingsHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.commands.handlers.sync_holdings_handler import (
        SyncHoldingsHandler,
    )
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        HoldingRepository,
        ProviderConnectionRepository,
    )

    account_repo = AccountRepository(session=session)
    connection_repo = ProviderConnectionRepository(session=session)
    holding_repo = HoldingRepository(session=session)
    encryption_service = get_encryption_service()
    provider = get_provider(provider_slug)
    event_bus = get_event_bus()

    return SyncHoldingsHandler(
        account_repo=account_repo,
        connection_repo=connection_repo,
        holding_repo=holding_repo,
        encryption_service=encryption_service,
        provider=provider,
        event_bus=event_bus,
    )
