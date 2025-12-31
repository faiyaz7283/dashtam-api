"""Transactions resource handlers.

Handler functions for transaction management endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    get_transaction              - Get transaction details
    sync_transactions            - Sync transactions from provider
    list_transactions_by_account - List transactions for an account

Reference:
    - docs/architecture/api-design-patterns.md
    - docs/architecture/error-handling-architecture.md
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path, Query, Request
from fastapi.responses import JSONResponse

from src.application.commands.handlers.sync_transactions_handler import (
    SyncTransactionsHandler,
)
from src.application.commands.sync_commands import SyncTransactions
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.application.queries.handlers.get_transaction_handler import (
    GetTransactionHandler,
)
from src.application.queries.handlers.list_transactions_handler import (
    ListTransactionsByAccountHandler,
    ListTransactionsByDateRangeHandler,
)
from src.application.queries.transaction_queries import (
    GetTransaction,
    ListTransactionsByAccount,
    ListTransactionsByDateRange,
)
from src.core.container import (
    get_get_transaction_handler,
    get_list_transactions_by_account_handler,
    get_list_transactions_by_date_range_handler,
    get_sync_transactions_handler,
)
from src.core.result import Failure
from src.presentation.routers.api.middleware.auth_dependencies import AuthenticatedUser
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.transaction_schemas import (
    SyncTransactionsRequest,
    SyncTransactionsResponse,
    TransactionListResponse,
    TransactionResponse,
)


# =============================================================================
# Error Mapping (String → ApplicationError)
# =============================================================================
# Note: Handlers currently return Result[T, str]. This mapping converts
# string errors to ApplicationError for RFC 7807 compliance.
# TODO (Phase 6): Refactor handlers to return Result[T, ApplicationError]
# =============================================================================


def _map_transaction_error(error: str) -> ApplicationError:
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


async def get_transaction(
    request: Request,
    current_user: AuthenticatedUser,
    transaction_id: Annotated[UUID, Path(description="Transaction UUID")],
    handler: GetTransactionHandler = Depends(get_get_transaction_handler),
) -> TransactionResponse | JSONResponse:
    """Get a specific transaction.

    GET /api/v1/transactions/{id} → 200 OK

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        transaction_id: Transaction UUID.
        handler: Get transaction handler (injected).

    Returns:
        TransactionResponse with transaction details.
        JSONResponse with RFC 7807 error on failure.
    """
    query = GetTransaction(
        transaction_id=transaction_id,
        user_id=current_user.user_id,
    )
    result = await handler.handle(query)

    if isinstance(result, Failure):
        app_error = _map_transaction_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return TransactionResponse.from_dto(result.value)


async def sync_transactions(
    request: Request,
    current_user: AuthenticatedUser,
    data: SyncTransactionsRequest,
    handler: SyncTransactionsHandler = Depends(get_sync_transactions_handler),
) -> SyncTransactionsResponse | JSONResponse:
    """Sync transactions from a provider connection.

    POST /api/v1/transactions/syncs → 201 Created

    Fetches transactions from the provider and upserts them to the database.
    Returns sync statistics (created/updated counts).

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        data: Sync request with connection_id and optional filters.
        handler: Sync transactions handler (injected).

    Returns:
        SyncTransactionsResponse with sync statistics.
        JSONResponse with RFC 7807 error on failure.
    """
    command = SyncTransactions(
        user_id=current_user.user_id,
        connection_id=data.connection_id,
        account_id=data.account_id,
        start_date=data.start_date,
        end_date=data.end_date,
        force=data.force,
    )
    result = await handler.handle(command)

    if isinstance(result, Failure):
        app_error = _map_transaction_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    # Convert handler result to response
    sync_result = result.value
    return SyncTransactionsResponse(
        created=sync_result.created,
        updated=sync_result.updated,
        unchanged=sync_result.unchanged,
        errors=sync_result.errors,
        message=sync_result.message,
        transactions_created=sync_result.created,
        transactions_updated=sync_result.updated,
    )


# =============================================================================
# Account-scoped Transaction Handler
# =============================================================================
# Note: This endpoint is under /accounts/{id}/transactions but implemented here
# for transaction-related logic grouping.
# =============================================================================


async def list_transactions_by_account(
    request: Request,
    current_user: AuthenticatedUser,
    account_id: Annotated[UUID, Path(description="Account UUID")],
    limit: Annotated[
        int,
        Query(description="Maximum number of results", ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(description="Number of results to skip", ge=0),
    ] = 0,
    transaction_type: Annotated[
        str | None,
        Query(description="Filter by transaction type (e.g., trade, transfer)"),
    ] = None,
    start_date: Annotated[
        date | None,
        Query(description="Filter by start date (inclusive)"),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(description="Filter by end date (inclusive)"),
    ] = None,
    account_handler: ListTransactionsByAccountHandler = Depends(
        get_list_transactions_by_account_handler
    ),
    date_handler: ListTransactionsByDateRangeHandler = Depends(
        get_list_transactions_by_date_range_handler
    ),
) -> TransactionListResponse | JSONResponse:
    """List transactions for a specific account.

    GET /api/v1/accounts/{id}/transactions → 200 OK

    Supports pagination via limit/offset and filtering by:
    - transaction_type: Filter to specific type (e.g., "trade")
    - start_date/end_date: Date range filter

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        account_id: Account UUID.
        limit: Maximum results to return.
        offset: Number of results to skip.
        transaction_type: Optional type filter.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        account_handler: List by account handler (injected).
        date_handler: List by date range handler (injected).

    Returns:
        TransactionListResponse with list of transactions.
        JSONResponse with RFC 7807 error on failure.
    """
    # Use date range handler if dates provided, otherwise use account handler
    if start_date and end_date:
        date_query = ListTransactionsByDateRange(
            account_id=account_id,
            user_id=current_user.user_id,
            start_date=start_date,
            end_date=end_date,
        )
        result = await date_handler.handle(date_query)
    else:
        account_query = ListTransactionsByAccount(
            account_id=account_id,
            user_id=current_user.user_id,
            limit=limit,
            offset=offset,
            transaction_type=transaction_type,
        )
        result = await account_handler.handle(account_query)

    if isinstance(result, Failure):
        app_error = _map_transaction_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return TransactionListResponse.from_dto(result.value)
