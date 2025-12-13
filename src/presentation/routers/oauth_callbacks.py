"""OAuth callback router for provider authentication.

Handles OAuth 2.0 Authorization Code callbacks from providers.
These endpoints are external-facing (dictated by provider redirect URI requirements)
and not part of the versioned API.

Flow:
    1. User initiates OAuth via frontend → Backend generates auth URL with state
    2. User authorizes at provider → Provider redirects to callback with code
    3. This router exchanges code for tokens → Creates provider connection

Security:
    - CSRF protection via state parameter (stored in Redis)
    - State contains user_id + provider_slug + timestamp
    - State expires after 10 minutes (prevent replay attacks)

Registered Callback URLs (Schwab Developer Portal):
    - https://127.0.0.1:8182/oauth/schwab/callback (local standalone)
    - https://dashtam.local/oauth/schwab/callback (local via Traefik)

Reference:
    - docs/architecture/provider-oauth-architecture.md
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse

from src.application.commands.handlers.connect_provider_handler import (
    ConnectProviderHandler,
)
from src.application.commands.provider_commands import ConnectProvider
from src.core.container import (
    get_cache,
    get_connect_provider_handler,
    get_encryption_service,
    get_provider,
    get_provider_repository,
)
from src.core.result import Failure, Success
from src.domain.enums.credential_type import CredentialType
from src.domain.protocols.cache_protocol import CacheProtocol
from src.domain.protocols.provider_repository import ProviderRepository
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.infrastructure.providers.encryption_service import EncryptionService

# OAuth state cache key prefix
OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_STATE_TTL = 600  # 10 minutes

oauth_router = APIRouter(tags=["OAuth Callbacks"])


async def _get_oauth_state_data(
    cache: CacheProtocol,
    state: str,
) -> dict[str, Any] | None:
    """Retrieve and validate OAuth state from cache.

    Args:
        cache: Cache protocol instance.
        state: State parameter from OAuth callback.

    Returns:
        State data dict if valid, None if not found or expired.
    """
    key = f"{OAUTH_STATE_PREFIX}{state}"
    result = await cache.get_json(key)

    match result:
        case Success(value=data) if data:
            # Delete state after retrieval (one-time use)
            await cache.delete(key)
            return data
        case _:
            return None


def _create_success_html(provider_slug: str) -> str:
    """Create success HTML response for OAuth callback.

    Args:
        provider_slug: Provider identifier.

    Returns:
        HTML string with success message.
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connection Successful</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .card {{
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
            }}
            .success-icon {{
                font-size: 48px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
            }}
            p {{
                color: #666;
                margin-bottom: 20px;
            }}
            .provider {{
                color: #667eea;
                font-weight: 600;
                text-transform: capitalize;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="success-icon">✓</div>
            <h1>Connection Successful!</h1>
            <p>Your <span class="provider">{provider_slug}</span> account has been connected.</p>
            <p>You can close this window and return to the application.</p>
        </div>
    </body>
    </html>
    """


def _create_error_html(error_title: str, error_message: str) -> str:
    """Create error HTML response for OAuth callback.

    Args:
        error_title: Error title.
        error_message: Error description.

    Returns:
        HTML string with error message.
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connection Failed</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
            }}
            .card {{
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
            }}
            .error-icon {{
                font-size: 48px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
            }}
            p {{
                color: #666;
                margin-bottom: 20px;
            }}
            .error-detail {{
                background: #f8f8f8;
                padding: 15px;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                color: #e74c3c;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="error-icon">✗</div>
            <h1>{error_title}</h1>
            <p>Unable to connect your account.</p>
            <div class="error-detail">{error_message}</div>
            <p style="margin-top: 20px;">Please close this window and try again.</p>
        </div>
    </body>
    </html>
    """


@oauth_router.get(
    "/oauth/schwab/callback",
    response_class=HTMLResponse,
    summary="Schwab OAuth callback",
    description="Handle OAuth 2.0 Authorization Code callback from Schwab.",
    responses={
        200: {"description": "Connection successful"},
        400: {"description": "OAuth error or invalid state"},
        500: {"description": "Internal error during token exchange"},
    },
)
async def schwab_oauth_callback(
    request: Request,
    code: Annotated[str | None, Query(description="Authorization code")] = None,
    state: Annotated[str | None, Query(description="CSRF state token")] = None,
    error: Annotated[str | None, Query(description="OAuth error code")] = None,
    error_description: Annotated[
        str | None, Query(description="OAuth error description")
    ] = None,
    cache: CacheProtocol = Depends(get_cache),
    handler: ConnectProviderHandler = Depends(get_connect_provider_handler),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    provider_repo: ProviderRepository = Depends(get_provider_repository),
) -> HTMLResponse:
    """Handle Schwab OAuth 2.0 callback.

    This endpoint is called by Schwab after user authorizes the application.
    It exchanges the authorization code for tokens and creates the connection.

    Query Parameters:
        code: Authorization code from Schwab (on success).
        state: CSRF token (must match stored session state).
        error: OAuth error code (on user denial or error).
        error_description: Human-readable error description.

    Returns:
        HTMLResponse: Success or error page for user.

    Flow:
        1. Validate state parameter (CSRF protection)
        2. Handle OAuth errors from provider
        3. Exchange authorization code for tokens
        4. Encrypt tokens for storage
        5. Create provider connection via command handler
        6. Return success/error HTML to user
    """
    provider_slug = "schwab"

    # Step 1: Handle OAuth errors from provider
    if error:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Authorization Denied",
                error_message=error_description or error,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Step 2: Validate required parameters
    if not code:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Missing Authorization Code",
                error_message="No authorization code received from provider.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not state:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Missing State Parameter",
                error_message="State parameter is required for security.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Step 3: Validate state (CSRF protection)
    state_data = await _get_oauth_state_data(cache, state)
    if state_data is None:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Invalid or Expired State",
                error_message="Session expired. Please start the connection process again.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Extract user info from state
    user_id = UUID(state_data["user_id"])
    stored_provider = state_data.get("provider_slug")

    # Verify provider matches
    if stored_provider != provider_slug:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Provider Mismatch",
                error_message="State does not match expected provider.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Step 4: Get provider and exchange code for tokens
    provider = get_provider(provider_slug)
    if provider is None:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Provider Not Found",
                error_message=f"Provider '{provider_slug}' is not configured.",
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Exchange authorization code for tokens
    token_result = await provider.exchange_code_for_tokens(code)

    match token_result:
        case Failure(error=provider_error):
            return HTMLResponse(
                content=_create_error_html(
                    error_title="Token Exchange Failed",
                    error_message=provider_error.message,
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        case Success(value=tokens):
            pass  # Continue with tokens

    # Step 5: Encrypt tokens for storage
    token_data = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "scope": tokens.scope,
    }
    encryption_result = encryption_service.encrypt(token_data)

    match encryption_result:
        case Failure():
            return HTMLResponse(
                content=_create_error_html(
                    error_title="Encryption Failed",
                    error_message="Unable to secure credentials.",
                ),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        case Success(value=encrypted_data):
            pass  # Continue with encrypted data

    # Step 6: Calculate token expiration
    expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in)

    # Step 7: Look up provider from database
    provider_entity = await provider_repo.find_by_slug(provider_slug)
    if provider_entity is None:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Provider Not Configured",
                error_message=f"Provider '{provider_slug}' is not registered in the system.",
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Step 8: Create provider connection via command
    credentials = ProviderCredentials(
        encrypted_data=encrypted_data,
        credential_type=CredentialType.OAUTH2,
        expires_at=expires_at,
    )

    connect_command = ConnectProvider(
        user_id=user_id,
        provider_id=provider_entity.id,
        provider_slug=provider_slug,
        credentials=credentials,
        alias=state_data.get("alias"),  # Optional alias from state
    )

    connect_result = await handler.handle(connect_command)

    match connect_result:
        case Failure(error=connect_error):
            return HTMLResponse(
                content=_create_error_html(
                    error_title="Connection Failed",
                    error_message=connect_error,
                ),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        case Success():
            return HTMLResponse(
                content=_create_success_html(provider_slug),
                status_code=status.HTTP_200_OK,
            )


@oauth_router.get(
    "/oauth/{provider_slug}/callback",
    response_class=HTMLResponse,
    summary="OAuth callback (dynamic)",
    description="Handle OAuth 2.0 Authorization Code callback for any configured provider.",
    responses={
        200: {"description": "Connection successful"},
        400: {"description": "OAuth error or invalid state"},
        500: {"description": "Internal error during token exchange"},
    },
)
async def oauth_callback_dynamic(
    provider_slug: str,
    request: Request,
    code: Annotated[str | None, Query(description="Authorization code")] = None,
    state: Annotated[str | None, Query(description="CSRF state token")] = None,
    error: Annotated[str | None, Query(description="OAuth error code")] = None,
    error_description: Annotated[
        str | None, Query(description="OAuth error description")
    ] = None,
    cache: CacheProtocol = Depends(get_cache),
    handler: ConnectProviderHandler = Depends(get_connect_provider_handler),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    provider_repo: ProviderRepository = Depends(get_provider_repository),
) -> HTMLResponse:
    """Handle OAuth 2.0 callback for any provider slug.

    Mirrors logic of the Schwab-specific route, but uses the dynamic
    provider_slug path parameter to resolve provider and validate state.
    """
    # Step 1: Handle OAuth errors from provider
    if error:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Authorization Denied",
                error_message=error_description or error,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Step 2: Validate required parameters
    if not code:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Missing Authorization Code",
                error_message="No authorization code received from provider.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not state:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Missing State Parameter",
                error_message="State parameter is required for security.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Step 3: Validate state (CSRF protection)
    state_data = await _get_oauth_state_data(cache, state)
    if state_data is None:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Invalid or Expired State",
                error_message="Session expired. Please start the connection process again.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Extract user info from state
    user_id = UUID(state_data["user_id"])
    stored_provider = state_data.get("provider_slug")

    # Verify provider matches
    if stored_provider != provider_slug:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Provider Mismatch",
                error_message="State does not match expected provider.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Step 4: Get provider and exchange code for tokens
    provider = get_provider(provider_slug)
    if provider is None:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Provider Not Found",
                error_message=f"Provider '{provider_slug}' is not configured.",
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Exchange authorization code for tokens
    token_result = await provider.exchange_code_for_tokens(code)

    match token_result:
        case Failure(error=provider_error):
            return HTMLResponse(
                content=_create_error_html(
                    error_title="Token Exchange Failed",
                    error_message=provider_error.message,
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        case Success(value=tokens):
            pass  # Continue with tokens

    # Step 5: Encrypt tokens for storage
    token_data = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "scope": tokens.scope,
    }
    encryption_result = encryption_service.encrypt(token_data)

    match encryption_result:
        case Failure():
            return HTMLResponse(
                content=_create_error_html(
                    error_title="Encryption Failed",
                    error_message="Unable to secure credentials.",
                ),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        case Success(value=encrypted_data):
            pass  # Continue with encrypted data

    # Step 6: Calculate token expiration
    expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in)

    # Step 7: Look up provider from database
    provider_entity = await provider_repo.find_by_slug(provider_slug)
    if provider_entity is None:
        return HTMLResponse(
            content=_create_error_html(
                error_title="Provider Not Configured",
                error_message=f"Provider '{provider_slug}' is not registered in the system.",
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Step 8: Create provider connection via command
    credentials = ProviderCredentials(
        encrypted_data=encrypted_data,
        credential_type=CredentialType.OAUTH2,
        expires_at=expires_at,
    )

    connect_command = ConnectProvider(
        user_id=user_id,
        provider_id=provider_entity.id,
        provider_slug=provider_slug,
        credentials=credentials,
        alias=state_data.get("alias"),  # Optional alias from state
    )

    connect_result = await handler.handle(connect_command)

    match connect_result:
        case Failure(error=connect_error):
            return HTMLResponse(
                content=_create_error_html(
                    error_title="Connection Failed",
                    error_message=str(connect_error),
                ),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        case Success():
            return HTMLResponse(
                content=_create_success_html(provider_slug),
                status_code=status.HTTP_200_OK,
            )
