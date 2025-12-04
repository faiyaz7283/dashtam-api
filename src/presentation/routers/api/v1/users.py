"""Users resource router.

RESTful endpoints for user management.

Endpoints:
    POST /api/v1/users - Create new user (registration)
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from src.application.commands.auth_commands import RegisterUser
from src.application.commands.handlers.register_user_handler import RegisterUserHandler
from src.core.container import get_register_user_handler
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.schemas.auth_schemas import (
    AuthErrorResponse,
    UserCreateRequest,
    UserCreateResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=UserCreateResponse,
    responses={
        201: {"description": "User created successfully", "model": UserCreateResponse},
        400: {"description": "Validation error", "model": AuthErrorResponse},
        409: {"description": "Email already registered", "model": AuthErrorResponse},
    },
    summary="Create user",
    description="Register a new user account. Sends verification email.",
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
    result = await handler.handle(command)

    # Handle result
    match result:
        case Success(value=user_id):
            return UserCreateResponse(
                id=user_id,
                email=data.email,
            )
        case Failure(error=error):
            # Determine status code based on error
            if "already registered" in error.lower():
                status_code = status.HTTP_409_CONFLICT
                title = "Email Already Registered"
            else:
                status_code = status.HTTP_400_BAD_REQUEST
                title = "Validation Error"

            trace_id = get_trace_id()
            return JSONResponse(
                status_code=status_code,
                content=AuthErrorResponse(
                    type=f"https://api.dashtam.com/errors/{title.lower().replace(' ', '-')}",
                    title=title,
                    status=status_code,
                    detail=error,
                    instance=str(request.url.path),
                ).model_dump(),
                headers={"X-Trace-ID": trace_id} if trace_id else None,
            )
