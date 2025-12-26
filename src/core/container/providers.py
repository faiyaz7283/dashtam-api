"""Provider dependency factory.

Factory for creating financial provider adapters based on slug.
Single factory (get_provider) with capability checking (is_oauth_provider).

Usage:
    - get_provider(): Returns any provider by slug (auth-agnostic)
    - is_oauth_provider(): TypeGuard for OAuth capability checking

Pattern:
    # For sync handlers (all providers)
    provider = get_provider("schwab")
    result = await provider.fetch_accounts(credentials)

    # For OAuth callbacks (OAuth providers only)
    provider = get_provider("schwab")
    if is_oauth_provider(provider):
        tokens = await provider.exchange_code_for_tokens(code)

Reference:
    See docs/architecture/provider-integration-architecture.md for complete
    provider patterns and integration details.
"""

from typing import TYPE_CHECKING, TypeGuard

from src.core.config import settings

if TYPE_CHECKING:
    from src.domain.protocols.provider_protocol import (
        OAuthProviderProtocol,
        ProviderProtocol,
    )


# OAuth providers - these support exchange_code_for_tokens and refresh_access_token
OAUTH_PROVIDERS = {"schwab"}


# ============================================================================
# Provider Factory (Application-Scoped)
# ============================================================================


def get_provider(slug: str) -> "ProviderProtocol":
    """Get financial provider adapter by slug.

    Factory function that returns the correct provider implementation
    based on the provider slug. Follows Composition Root pattern.

    This returns providers typed as ProviderProtocol (auth-agnostic).
    For OAuth-specific operations, use get_oauth_provider() instead.

    Currently supported providers:
        - 'schwab': Charles Schwab (OAuth, Trader API)

    Future providers (not yet implemented):
        - 'alpaca': Alpaca (API Key, Trading API)
        - 'chase': Chase Bank (OAuth)

    Args:
        slug: Provider identifier (e.g., 'schwab', 'alpaca').

    Returns:
        Provider adapter implementing ProviderProtocol.

    Raises:
        ValueError: If provider slug is unknown or provider not configured.

    Usage:
        # Application Layer (sync handlers - auth-agnostic)
        from src.core.container import get_provider
        provider = get_provider("schwab")
        result = await provider.fetch_accounts(credentials)

    Reference:
        - docs/architecture/provider-integration-architecture.md
    """
    match slug:
        case "schwab":
            from src.infrastructure.providers.schwab import SchwabProvider

            # Validate required settings
            if not settings.schwab_api_key or not settings.schwab_api_secret:
                raise ValueError(
                    f"Provider '{slug}' not configured. "
                    "Set SCHWAB_API_KEY and SCHWAB_API_SECRET in environment."
                )

            return SchwabProvider(settings=settings)

        # Future providers:
        # case "alpaca":
        #     from src.infrastructure.providers.alpaca import AlpacaProvider
        #     return AlpacaProvider(settings=settings)

        case _:
            raise ValueError(f"Unknown provider: {slug}. Supported: 'schwab'")


def is_oauth_provider(
    provider: "ProviderProtocol",
) -> TypeGuard["OAuthProviderProtocol"]:
    """Check if provider supports OAuth authentication.

    TypeGuard function that performs runtime check and narrows type.
    After this returns True, the provider is typed as OAuthProviderProtocol.

    Use this to check provider capabilities before calling OAuth methods:
        - exchange_code_for_tokens()
        - refresh_access_token()

    Args:
        provider: Any provider instance.

    Returns:
        True if provider supports OAuth (has exchange_code_for_tokens method).
        Type is narrowed to OAuthProviderProtocol when True.

    Usage:
        # In OAuth callback handler:
        provider = get_provider(slug)
        if is_oauth_provider(provider):
            # Type is now OAuthProviderProtocol
            tokens = await provider.exchange_code_for_tokens(code)
        else:
            raise ValueError(f"Provider {slug} doesn't support OAuth")

        # In token refresh handler:
        provider = get_provider(connection.provider_slug)
        if is_oauth_provider(provider):
            result = await provider.refresh_access_token(refresh_token)
        else:
            # API Key providers don't need token refresh
            return Success("No refresh needed")

    Reference:
        - docs/architecture/provider-integration-architecture.md
    """
    return provider.slug in OAUTH_PROVIDERS
