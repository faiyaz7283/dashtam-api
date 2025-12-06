"""Repository dependency factories.

Request-scoped repository instances for domain entity persistence.
Each request gets fresh repository instances with shared session.

Reference:
    See docs/architecture/dependency-injection-architecture.md for complete
    patterns and usage examples.
"""

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.container.infrastructure import get_db_session

if TYPE_CHECKING:
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        ProviderConnectionRepository,
        TransactionRepository,
        UserRepository,
    )
    from src.infrastructure.persistence.repositories.provider_repository import (
        ProviderRepository,
    )


# ============================================================================
# Repository Factories (Request-Scoped)
# ============================================================================


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "UserRepository":
    """Get user repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for User domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        UserRepository instance.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_user_repository
        user_repo = await anext(get_user_repository())
        user = await user_repo.find_by_email("user@example.com")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.infrastructure.persistence.repositories import UserRepository

        @router.post("/users")
        async def create_user(
            user_repo: UserRepository = Depends(get_user_repository)
        ):
            await user_repo.save(user)

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 589-593)
    """
    from src.infrastructure.persistence.repositories import UserRepository

    return UserRepository(session=session)


async def get_provider_connection_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "ProviderConnectionRepository":
    """Get provider connection repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for ProviderConnection domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        ProviderConnectionRepository instance.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_provider_connection_repository
        conn_repo = await anext(get_provider_connection_repository())
        conn = await conn_repo.find_by_id(connection_id)

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.infrastructure.persistence.repositories import ProviderConnectionRepository

        @router.get("/providers/connections/{id}")
        async def get_connection(
            conn_repo: ProviderConnectionRepository = Depends(get_provider_connection_repository)
        ):
            return await conn_repo.find_by_id(id)

    Reference:
        - docs/architecture/repository-pattern.md
    """
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )

    return ProviderConnectionRepository(session=session)


async def get_provider_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "ProviderRepository":
    """Get provider repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for Provider domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        ProviderRepository instance.

    Usage:
        # Application Layer
        from src.core.container import get_provider_repository
        provider_repo = await anext(get_provider_repository())
        provider = await provider_repo.find_by_slug("schwab")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends

        @router.get("/providers/{slug}")
        async def get_provider(
            provider_repo: ProviderRepository = Depends(get_provider_repository)
        ):
            return await provider_repo.find_by_slug(slug)
    """
    from src.infrastructure.persistence.repositories.provider_repository import (
        ProviderRepository,
    )

    return ProviderRepository(session=session)


async def get_account_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "AccountRepository":
    """Get account repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for Account domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        AccountRepository instance.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_account_repository
        account_repo = await anext(get_account_repository())
        account = await repo.find_by_id(account_id)

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.infrastructure.persistence.repositories import AccountRepository

        @router.get("/accounts/{id}")
        async def get_account(
            account_repo: AccountRepository = Depends(get_account_repository)
        ):
            return await account_repo.find_by_id(id)

    Reference:
        - docs/architecture/repository-pattern.md
    """
    from src.infrastructure.persistence.repositories import AccountRepository

    return AccountRepository(session=session)


async def get_transaction_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "TransactionRepository":
    """Get transaction repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for Transaction domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        TransactionRepository instance.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_transaction_repository
        tx_repo = await anext(get_transaction_repository())
        transactions = await tx_repo.find_by_account_id(account_id)

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.infrastructure.persistence.repositories import TransactionRepository

        @router.get("/transactions")
        async def list_transactions(
            tx_repo: TransactionRepository = Depends(get_transaction_repository)
        ):
            return await tx_repo.find_by_account_id(account_id, limit=50)

    Reference:
        - docs/architecture/repository-pattern.md
    """
    from src.infrastructure.persistence.repositories import TransactionRepository

    return TransactionRepository(session=session)
