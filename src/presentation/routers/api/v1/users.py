"""Users resource handlers.

Handler functions for user management endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    create_user - Create new user (registration)
"""

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from src.application.commands.auth_commands import RegisterUser
from src.application.commands.handlers.register_user_handler import RegisterUserHandler
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.container import get_register_user_handler
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.auth_schemas import (
    UserCreateRequest,
    UserCreateResponse,
)


async def create_user(
    request: Request,
    data: UserCreateRequest,
    handler: RegisterUserHandler = Depends(get_register_user_handler),
) -> UserCreateResponse | JSONResponse:
    """Create a new user (registration).

    POST /api/v1/users → 201 Created

    Creates a new user account and sends a verification email.
    User must verify email before creating a session (login).

    Args:
        request: FastAPI request object.
        data: User creation request data (email, password).
        handler: Registration handler (injected).

    Returns:
        UserCreateResponse on success (201 Created).
        JSONResponse with error on failure (400/409).
    """
    # Create command from request data
    command = RegisterUser(
        email=data.email,
        password=data.password,
    )

    # Execute handler
    result = await handler.handle(command, request)

    # Handle result
    match result:
        case Success(value=user_id):
            return UserCreateResponse(
                id=user_id,
                email=data.email,
            )
        case Failure(error=error):
            # Map error to ApplicationErrorCode
            if "already registered" in error.lower():
                error_code = ApplicationErrorCode.CONFLICT
            else:
                error_code = ApplicationErrorCode.COMMAND_VALIDATION_FAILED

            app_error = ApplicationError(
                code=error_code,
                message=error,
            )
            return ErrorResponseBuilder.from_application_error(
                error=app_error,
                request=request,
                trace_id=get_trace_id() or "",
            )
