"""Balance snapshots resource router.

RESTful endpoints for balance snapshot/history management.

Endpoints:
    GET    /api/v1/balance-snapshots              - Get latest snapshots for user
    GET    /api/v1/accounts/{id}/balance-history  - Get balance history for account

Reference:
    - docs/architecture/api-design-patterns.md
    - docs/architecture/error-handling-architecture.md
"""

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.errors import ApplicationError, ApplicationErrorCode
from src.application.queries.balance_snapshot_queries import (
    GetBalanceHistory,
    GetLatestBalanceSnapshots,
    ListBalanceSnapshotsByAccount,
)
from src.application.queries.handlers.balance_snapshot_handlers import (
    GetBalanceHistoryHandler,
    GetLatestBalanceSnapshotsHandler,
    ListBalanceSnapshotsByAccountHandler,
)
from src.core.result import Failure
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.balance_snapshot_repository import BalanceSnapshotRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.infrastructure.persistence.repositories import (
    AccountRepository as AccountRepositoryImpl,
    BalanceSnapshotRepository as BalanceSnapshotRepositoryImpl,
    ProviderConnectionRepository as ProviderConnectionRepositoryImpl,
)
from src.presentation.routers.api.middleware.auth_dependencies import AuthenticatedUser
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.core.container import get_database
from src.schemas.balance_snapshot_schemas import (
    BalanceHistoryResponse,
    LatestSnapshotsResponse,
)


# Main router for /balance-snapshots endpoints
router = APIRouter(prefix="/balance-snapshots", tags=["Balance Snapshots"])

# Nested router for /accounts/{id}/balance-history endpoints
account_balance_router = APIRouter(prefix="/accounts", tags=["Accounts"])


# =============================================================================
# Dependency Injection Factories
# =============================================================================


async def get_balance_snapshot_repo(
    session: AsyncSession = Depends(lambda: get_database().get_session()),
) -> AsyncGenerator[BalanceSnapshotRepository, None]:
    """Get BalanceSnapshotRepository instance."""
    async with get_database().get_session() as session:
        yield BalanceSnapshotRepositoryImpl(session)


async def get_account_repo(
    session: AsyncSession = Depends(lambda: get_database().get_session()),
) -> AsyncGenerator[AccountRepository, None]:
    """Get AccountRepository instance."""
    async with get_database().get_session() as session:
        yield AccountRepositoryImpl(session)


async def get_connection_repo(
    session: AsyncSession = Depends(lambda: get_database().get_session()),
) -> AsyncGenerator[ProviderConnectionRepository, None]:
    """Get ProviderConnectionRepository instance."""
    async with get_database().get_session() as session:
        yield ProviderConnectionRepositoryImpl(session)


async def get_balance_history_handler(
    snapshot_repo: BalanceSnapshotRepository = Depends(get_balance_snapshot_repo),
    account_repo: AccountRepository = Depends(get_account_repo),
    connection_repo: ProviderConnectionRepository = Depends(get_connection_repo),
) -> GetBalanceHistoryHandler:
    """Get GetBalanceHistoryHandler instance."""
    return GetBalanceHistoryHandler(
        snapshot_repo=snapshot_repo,
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_list_snapshots_handler(
    snapshot_repo: BalanceSnapshotRepository = Depends(get_balance_snapshot_repo),
    account_repo: AccountRepository = Depends(get_account_repo),
    connection_repo: ProviderConnectionRepository = Depends(get_connection_repo),
) -> ListBalanceSnapshotsByAccountHandler:
    """Get ListBalanceSnapshotsByAccountHandler instance."""
    return ListBalanceSnapshotsByAccountHandler(
        snapshot_repo=snapshot_repo,
        account_repo=account_repo,
        connection_repo=connection_repo,
    )


async def get_latest_snapshots_handler(
    snapshot_repo: BalanceSnapshotRepository = Depends(get_balance_snapshot_repo),
) -> GetLatestBalanceSnapshotsHandler:
    """Get GetLatestBalanceSnapshotsHandler instance."""
    return GetLatestBalanceSnapshotsHandler(snapshot_repo=snapshot_repo)


# =============================================================================
# Error Mapping
# =============================================================================


def _map_snapshot_error(error: str) -> ApplicationError:
    """Map handler string error to ApplicationError.

    Args:
        error: Error string from handler.

    Returns:
        ApplicationError with appropriate code and message.
    """
    error_lower = error.lower()

    if "not found" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.NOT_FOUND,
            message=error,
        )
    if "not owned" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.FORBIDDEN,
            message=error,
        )
    if "invalid date range" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.QUERY_VALIDATION_FAILED,
            message=error,
        )
    if "invalid source" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.QUERY_VALIDATION_FAILED,
            message=error,
        )

    return ApplicationError(
        code=ApplicationErrorCode.QUERY_EXECUTION_FAILED,
        message=error,
    )


# =============================================================================
# Main Router Endpoints (/balance-snapshots)
# =============================================================================


@router.get(
    "",
    response_model=LatestSnapshotsResponse,
    summary="Get latest balance snapshots",
    description="Get the most recent balance snapshot for each of user's accounts.",
)
async def get_latest_snapshots(
    request: Request,
    current_user: AuthenticatedUser,
    handler: GetLatestBalanceSnapshotsHandler = Depends(get_latest_snapshots_handler),
) -> LatestSnapshotsResponse | JSONResponse:
    """Get latest balance snapshot for each account.

    GET /api/v1/balance-snapshots → 200 OK

    Returns portfolio summary with one snapshot per account.
    """
    query = GetLatestBalanceSnapshots(user_id=current_user.user_id)
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_snapshot_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return LatestSnapshotsResponse.from_dto(result.value)


# =============================================================================
# Nested Router Endpoints (/accounts/{id}/balance-history)
# =============================================================================


@account_balance_router.get(
    "/{account_id}/balance-history",
    response_model=BalanceHistoryResponse,
    summary="Get balance history",
    description="Get balance history for an account within a date range.",
    responses={
        404: {"description": "Account not found"},
        403: {"description": "Not authorized to access this account"},
        400: {"description": "Invalid date range"},
    },
)
async def get_balance_history(
    request: Request,
    current_user: AuthenticatedUser,
    account_id: Annotated[UUID, Path(description="Account UUID")],
    start_date: Annotated[datetime, Query(description="Start of date range")],
    end_date: Annotated[datetime, Query(description="End of date range")],
    source: Annotated[
        str | None,
        Query(
            description="Filter by snapshot source (account_sync, manual_sync, etc.)"
        ),
    ] = None,
    handler: GetBalanceHistoryHandler = Depends(get_balance_history_handler),
) -> BalanceHistoryResponse | JSONResponse:
    """Get balance history for an account.

    GET /api/v1/accounts/{id}/balance-history → 200 OK

    Returns snapshots ordered chronologically for charting.
    """
    query = GetBalanceHistory(
        account_id=account_id,
        user_id=current_user.user_id,
        start_date=start_date,
        end_date=end_date,
        source=source,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_snapshot_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return BalanceHistoryResponse.from_dto(result.value)


@account_balance_router.get(
    "/{account_id}/balance-snapshots",
    response_model=BalanceHistoryResponse,
    summary="List balance snapshots",
    description="List recent balance snapshots for an account.",
    responses={
        404: {"description": "Account not found"},
        403: {"description": "Not authorized to access this account"},
    },
)
async def list_balance_snapshots(
    request: Request,
    current_user: AuthenticatedUser,
    account_id: Annotated[UUID, Path(description="Account UUID")],
    limit: Annotated[
        int | None,
        Query(description="Maximum number of snapshots to return", ge=1, le=100),
    ] = 30,
    source: Annotated[
        str | None,
        Query(description="Filter by snapshot source"),
    ] = None,
    handler: ListBalanceSnapshotsByAccountHandler = Depends(get_list_snapshots_handler),
) -> BalanceHistoryResponse | JSONResponse:
    """List recent balance snapshots for an account.

    GET /api/v1/accounts/{id}/balance-snapshots → 200 OK

    Returns snapshots ordered by captured_at descending (most recent first).
    """
    query = ListBalanceSnapshotsByAccount(
        account_id=account_id,
        user_id=current_user.user_id,
        limit=limit,
        source=source,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_snapshot_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return BalanceHistoryResponse.from_dto(result.value)
