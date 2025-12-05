"""Provider handler dependency factories.

Request-scoped handler instances for provider operations:
- Provider connection (connect, disconnect)
- Provider token refresh
- Provider queries (get, list)

Reference:
    See docs/architecture/cqrs-pattern.md for handler patterns.
"""

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.container.events import get_event_bus
from src.core.container.infrastructure import get_db_session

if TYPE_CHECKING:
    from src.application.commands.handlers.connect_provider_handler import (
        ConnectProviderHandler,
    )
    from src.application.commands.handlers.disconnect_provider_handler import (
        DisconnectProviderHandler,
    )
    from src.application.commands.handlers.refresh_provider_tokens_handler import (
        RefreshProviderTokensHandler,
    )
    from src.application.queries.handlers.get_provider_handler import (
        GetProviderConnectionHandler,
    )
    from src.application.queries.handlers.list_providers_handler import (
        ListProviderConnectionsHandler,
    )


# ============================================================================
# Provider Handler Factories
# ============================================================================


async def get_connect_provider_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ConnectProviderHandler":
    """Get ConnectProvider command handler (request-scoped).

    Creates handler with:
    - ProviderConnectionRepository (request-scoped)
    - EventBus (app-scoped singleton)

    Returns:
        ConnectProviderHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.commands.handlers.connect_provider_handler import (
        ConnectProviderHandler,
    )
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )

    connection_repo = ProviderConnectionRepository(session=session)
    event_bus = get_event_bus()

    return ConnectProviderHandler(
        connection_repo=connection_repo,
        event_bus=event_bus,
    )


async def get_disconnect_provider_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "DisconnectProviderHandler":
    """Get DisconnectProvider command handler (request-scoped).

    Creates handler with:
    - ProviderConnectionRepository (request-scoped)
    - EventBus (app-scoped singleton)

    Returns:
        DisconnectProviderHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.commands.handlers.disconnect_provider_handler import (
        DisconnectProviderHandler,
    )
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )

    connection_repo = ProviderConnectionRepository(session=session)
    event_bus = get_event_bus()

    return DisconnectProviderHandler(
        connection_repo=connection_repo,
        event_bus=event_bus,
    )


async def get_refresh_provider_tokens_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RefreshProviderTokensHandler":
    """Get RefreshProviderTokens command handler (request-scoped).

    Creates handler with:
    - ProviderConnectionRepository (request-scoped)
    - EventBus (app-scoped singleton)

    Returns:
        RefreshProviderTokensHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.commands.handlers.refresh_provider_tokens_handler import (
        RefreshProviderTokensHandler,
    )
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )

    connection_repo = ProviderConnectionRepository(session=session)
    event_bus = get_event_bus()

    return RefreshProviderTokensHandler(
        connection_repo=connection_repo,
        event_bus=event_bus,
    )


async def get_get_provider_connection_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "GetProviderConnectionHandler":
    """Get GetProviderConnection query handler (request-scoped).

    Creates handler with:
    - ProviderConnectionRepository (request-scoped)

    Returns:
        GetProviderConnectionHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.get_provider_handler import (
        GetProviderConnectionHandler,
    )
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )

    connection_repo = ProviderConnectionRepository(session=session)

    return GetProviderConnectionHandler(
        connection_repo=connection_repo,
    )


async def get_list_provider_connections_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListProviderConnectionsHandler":
    """Get ListProviderConnections query handler (request-scoped).

    Creates handler with:
    - ProviderConnectionRepository (request-scoped)

    Returns:
        ListProviderConnectionsHandler instance.

    Reference:
        - docs/architecture/cqrs-pattern.md
    """
    from src.application.queries.handlers.list_providers_handler import (
        ListProviderConnectionsHandler,
    )
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )

    connection_repo = ProviderConnectionRepository(session=session)

    return ListProviderConnectionsHandler(
        connection_repo=connection_repo,
    )
