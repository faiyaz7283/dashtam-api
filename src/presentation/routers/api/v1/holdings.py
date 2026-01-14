"""Holdings resource handlers.

Handler functions for holdings (positions) management endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    list_holdings           - List all holdings for user
    list_holdings_by_account - List holdings for an account
    sync_holdings           - Sync holdings from provider

Reference:
    - docs/architecture/api-design-patterns.md
    - docs/architecture/error-handling-architecture.md
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path, Query, Request
from fastapi.responses import JSONResponse

from src.application.commands.handlers.sync_holdings_handler import (
    SyncHoldingsHandler,
)
from src.application.commands.sync_commands import SyncHoldings
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.application.queries.holding_queries import (
    ListHoldingsByAccount,
    ListHoldingsByUser,
)
from src.application.queries.handlers.list_holdings_handler import (
    ListHoldingsByAccountHandler,
    ListHoldingsByUserHandler,
)
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure
from src.presentation.routers.api.middleware.auth_dependencies import AuthenticatedUser
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.holding_schemas import (
    HoldingListResponse,
    SyncHoldingsRequest,
    SyncHoldingsResponse,
)


# =============================================================================
# Error Mapping (String → ApplicationError)
# =============================================================================


def _map_holding_error(error: str) -> ApplicationError:
    """Map handler string error to ApplicationError.

    Converts handler error strings to typed ApplicationError for
    RFC 7807 compliant error responses.

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
    if "not active" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message=error,
        )
    if "too soon" in error_lower or "recently synced" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.RATE_LIMIT_EXCEEDED,
            message=error,
        )
    if "invalid" in error_lower or "decryption" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message=error,
        )
    if "provider" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.EXTERNAL_SERVICE_ERROR,
            message=error,
        )

    # Default to command execution failed
    return ApplicationError(
        code=ApplicationErrorCode.COMMAND_EXECUTION_FAILED,
        message=error,
    )


# =============================================================================
# Holdings Collection Handlers
# =============================================================================


async def list_holdings(
    request: Request,
    current_user: AuthenticatedUser,
    active_only: Annotated[
        bool,
        Query(description="Only return active holdings"),
    ] = True,
    asset_type: Annotated[
        str | None,
        Query(description="Filter by asset type (e.g., equity, etf, option)"),
    ] = None,
    symbol: Annotated[
        str | None,
        Query(description="Filter by security symbol (e.g., AAPL)"),
    ] = None,
    handler: ListHoldingsByUserHandler = Depends(
        handler_factory(ListHoldingsByUserHandler)
    ),
) -> HoldingListResponse | JSONResponse:
    """List all holdings for the authenticated user.

    GET /api/v1/holdings → 200 OK

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        active_only: Filter to only active holdings.
        asset_type: Filter by asset type.
        symbol: Filter by security symbol.
        handler: List holdings handler (injected).

    Returns:
        HoldingListResponse with list of holdings.
        JSONResponse with RFC 7807 error on failure.
    """
    query = ListHoldingsByUser(
        user_id=current_user.user_id,
        active_only=active_only,
        asset_type=asset_type,
        symbol=symbol,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_holding_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return HoldingListResponse.from_dto(result.value)


# =============================================================================
# Account-scoped Holdings Handlers (nested resource)
# =============================================================================


async def list_holdings_by_account(
    request: Request,
    current_user: AuthenticatedUser,
    account_id: Annotated[UUID, Path(description="Account UUID")],
    active_only: Annotated[
        bool,
        Query(description="Only return active holdings"),
    ] = True,
    asset_type: Annotated[
        str | None,
        Query(description="Filter by asset type (e.g., equity, etf, option)"),
    ] = None,
    handler: ListHoldingsByAccountHandler = Depends(
        handler_factory(ListHoldingsByAccountHandler)
    ),
) -> HoldingListResponse | JSONResponse:
    """List holdings for a specific account.

    GET /api/v1/accounts/{id}/holdings → 200 OK

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        account_id: Account UUID.
        active_only: Filter to only active holdings.
        asset_type: Filter by asset type.
        handler: List holdings by account handler (injected).

    Returns:
        HoldingListResponse with list of holdings.
        JSONResponse with RFC 7807 error on failure.
    """
    query = ListHoldingsByAccount(
        account_id=account_id,
        user_id=current_user.user_id,
        active_only=active_only,
        asset_type=asset_type,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_holding_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return HoldingListResponse.from_dto(result.value)


async def sync_holdings(
    request: Request,
    current_user: AuthenticatedUser,
    account_id: Annotated[UUID, Path(description="Account UUID")],
    data: SyncHoldingsRequest,
    handler: SyncHoldingsHandler = Depends(handler_factory(SyncHoldingsHandler)),
) -> SyncHoldingsResponse | JSONResponse:
    """Sync holdings from provider for an account.

    POST /api/v1/accounts/{id}/holdings/syncs → 201 Created

    Fetches holdings from the provider and upserts them to the database.
    Returns sync statistics (created/updated/deactivated counts).

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        account_id: Account UUID.
        data: Sync request with force flag.
        handler: Sync holdings handler (injected).

    Returns:
        SyncHoldingsResponse with sync statistics.
        JSONResponse with RFC 7807 error on failure.
    """
    command = SyncHoldings(
        account_id=account_id,
        user_id=current_user.user_id,
        force=data.force,
    )
    result = await handler.handle(command)

    if isinstance(result, Failure):
        app_error = _map_holding_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    # Convert handler result to response
    sync_result = result.value
    return SyncHoldingsResponse(
        created=sync_result.created,
        updated=sync_result.updated,
        unchanged=sync_result.unchanged,
        errors=sync_result.errors,
        message=sync_result.message,
        holdings_created=sync_result.created,
        holdings_updated=sync_result.updated,
        holdings_deactivated=sync_result.deactivated,
    )
