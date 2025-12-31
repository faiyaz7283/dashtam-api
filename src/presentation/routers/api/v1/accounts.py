"""Accounts resource handlers.

Handler functions for account management endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    list_accounts              - List all accounts for user
    get_account                - Get account details
    sync_accounts              - Sync accounts from provider
    list_accounts_by_connection - List accounts for a connection

Reference:
    - docs/architecture/api-design-patterns.md
    - docs/architecture/error-handling-architecture.md
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path, Query, Request
from fastapi.responses import JSONResponse

from src.application.commands.handlers.sync_accounts_handler import (
    SyncAccountsHandler,
)
from src.application.commands.sync_commands import SyncAccounts
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.application.queries.account_queries import (
    GetAccount,
    ListAccountsByConnection,
    ListAccountsByUser,
)
from src.domain.enums.account_type import AccountType
from src.application.queries.handlers.get_account_handler import GetAccountHandler
from src.application.queries.handlers.list_accounts_handler import (
    ListAccountsByConnectionHandler,
    ListAccountsByUserHandler,
)
from src.core.container import (
    get_get_account_handler,
    get_list_accounts_by_connection_handler,
    get_list_accounts_by_user_handler,
    get_sync_accounts_handler,
)
from src.core.result import Failure
from src.presentation.routers.api.middleware.auth_dependencies import AuthenticatedUser
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.account_schemas import (
    AccountListResponse,
    AccountResponse,
    SyncAccountsRequest,
    SyncAccountsResponse,
)


# =============================================================================
# Error Mapping (String → ApplicationError)
# =============================================================================
# Note: Handlers currently return Result[T, str]. This mapping converts
# string errors to ApplicationError for RFC 7807 compliance.
# TODO (Phase 6): Refactor handlers to return Result[T, ApplicationError]
# =============================================================================


def _map_account_error(error: str) -> ApplicationError:
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
    if "too soon" in error_lower or "recently synced" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.RATE_LIMIT_EXCEEDED,
            message=error,
        )
    if "invalid" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message=error,
        )

    # Default to command execution failed
    return ApplicationError(
        code=ApplicationErrorCode.COMMAND_EXECUTION_FAILED,
        message=error,
    )


# =============================================================================
# Handlers
# =============================================================================


async def list_accounts(
    request: Request,
    current_user: AuthenticatedUser,
    active_only: Annotated[
        bool,
        Query(description="Only return active accounts"),
    ] = False,
    account_type: Annotated[
        str | None,
        Query(description="Filter by account type (e.g., brokerage, ira)"),
    ] = None,
    handler: ListAccountsByUserHandler = Depends(get_list_accounts_by_user_handler),
) -> AccountListResponse | JSONResponse:
    """List all accounts for the authenticated user.

    GET /api/v1/accounts → 200 OK

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        active_only: Filter to only active accounts.
        account_type: Filter by account type.
        handler: List accounts handler (injected).

    Returns:
        AccountListResponse with list of accounts.
        JSONResponse with RFC 7807 error on failure.
    """
    # Convert string to AccountType enum if provided
    account_type_enum: AccountType | None = None
    if account_type:
        try:
            account_type_enum = AccountType(account_type)
        except ValueError:
            # Invalid account type - will return empty list
            pass

    query = ListAccountsByUser(
        user_id=current_user.user_id,
        active_only=active_only,
        account_type=account_type_enum,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_account_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return AccountListResponse.from_dto(result.value)


async def get_account(
    request: Request,
    current_user: AuthenticatedUser,
    account_id: Annotated[UUID, Path(description="Account UUID")],
    handler: GetAccountHandler = Depends(get_get_account_handler),
) -> AccountResponse | JSONResponse:
    """Get a specific account.

    GET /api/v1/accounts/{id} → 200 OK

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        account_id: Account UUID.
        handler: Get account handler (injected).

    Returns:
        AccountResponse with account details.
        JSONResponse with RFC 7807 error on failure.
    """
    query = GetAccount(
        account_id=account_id,
        user_id=current_user.user_id,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_account_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return AccountResponse.from_dto(result.value)


async def sync_accounts(
    request: Request,
    current_user: AuthenticatedUser,
    data: SyncAccountsRequest,
    handler: SyncAccountsHandler = Depends(get_sync_accounts_handler),
) -> SyncAccountsResponse | JSONResponse:
    """Sync accounts from a provider connection.

    POST /api/v1/accounts/syncs → 201 Created

    Fetches accounts from the provider and upserts them to the database.
    Returns sync statistics (created/updated counts).

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        data: Sync request with connection_id and force flag.
        handler: Sync accounts handler (injected).

    Returns:
        SyncAccountsResponse with sync statistics.
        JSONResponse with RFC 7807 error on failure.
    """
    command = SyncAccounts(
        user_id=current_user.user_id,
        connection_id=data.connection_id,
        force=data.force,
    )
    result = await handler.handle(command)

    if isinstance(result, Failure):
        app_error = _map_account_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    # Convert handler result to response
    sync_result = result.value
    return SyncAccountsResponse(
        created=sync_result.created,
        updated=sync_result.updated,
        unchanged=sync_result.unchanged,
        errors=sync_result.errors,
        message=sync_result.message,
        accounts_created=sync_result.created,
        accounts_updated=sync_result.updated,
    )


# =============================================================================
# Provider-scoped Account Handler
# =============================================================================
# Note: This endpoint is under /providers/{id}/accounts but implemented here
# for account-related logic grouping.
# =============================================================================


async def list_accounts_by_connection(
    request: Request,
    current_user: AuthenticatedUser,
    connection_id: Annotated[UUID, Path(description="Provider connection UUID")],
    active_only: Annotated[
        bool,
        Query(description="Only return active accounts"),
    ] = False,
    handler: ListAccountsByConnectionHandler = Depends(
        get_list_accounts_by_connection_handler
    ),
) -> AccountListResponse | JSONResponse:
    """List accounts for a specific provider connection.

    GET /api/v1/providers/{id}/accounts → 200 OK

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        connection_id: Provider connection UUID.
        active_only: Filter to only active accounts.
        handler: List accounts by connection handler (injected).

    Returns:
        AccountListResponse with list of accounts.
        JSONResponse with RFC 7807 error on failure.
    """
    query = ListAccountsByConnection(
        connection_id=connection_id,
        user_id=current_user.user_id,
        active_only=active_only,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_account_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return AccountListResponse.from_dto(result.value)
