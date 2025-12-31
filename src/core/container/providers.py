"""Provider dependency factory (Registry-driven).

Factory for creating financial provider adapters based on slug.
Single factory (get_provider) with capability checking (is_oauth_provider).

Registry-Driven Pattern (F8.1):
    - Provider metadata stored in domain/providers/registry.py
    - Container uses registry for lookup and validation
    - Zero drift: Can't forget to add provider to OAuth list
    - Self-enforcing: Tests fail if registry/factory mismatch

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
    See docs/architecture/provider-registry-architecture.md for registry pattern.
    See docs/architecture/provider-integration-architecture.md for integration.
"""

from typing import TYPE_CHECKING, TypeGuard

from src.core.config import settings
from src.domain.providers.registry import (
    PROVIDER_REGISTRY,
    get_oauth_providers,
    get_provider_metadata,
)

if TYPE_CHECKING:
    from src.domain.protocols.provider_protocol import (
        OAuthProviderProtocol,
        ProviderProtocol,
    )


# ============================================================================
# Provider Factory (Application-Scoped)
# ============================================================================


def get_provider(slug: str) -> "ProviderProtocol":
    """Get financial provider adapter by slug (registry-driven).

    Factory function that returns the correct provider implementation
    based on the provider slug from registry. Follows Composition Root pattern.

    Registry-Driven (F8.1):
        - Looks up provider metadata from PROVIDER_REGISTRY
        - Validates required settings via metadata.required_settings
        - Ensures zero drift between registry and factory

    This returns providers typed as ProviderProtocol (auth-agnostic).
    For OAuth-specific operations, use is_oauth_provider() to check capability.

    Currently supported providers (from registry):
        - 'schwab': Charles Schwab (OAuth, brokerage)
        - 'alpaca': Alpaca Markets (API Key, brokerage)
        - 'chase_file': Chase Bank (File Import, bank)

    Args:
        slug: Provider identifier (e.g., 'schwab', 'alpaca').

    Returns:
        Provider adapter implementing ProviderProtocol.

    Raises:
        ValueError: If provider slug is unknown or provider not configured.

    Usage:
        # Sync handlers (auth-agnostic - works for all providers)
        from src.core.container import get_provider
        provider = get_provider("schwab")
        result = await provider.fetch_accounts(credentials)

        # OAuth callbacks (check capability first)
        provider = get_provider("schwab")
        if is_oauth_provider(provider):
            tokens = await provider.exchange_code_for_tokens(code)

    Reference:
        - docs/architecture/provider-registry-architecture.md
        - docs/architecture/provider-integration-architecture.md
    """
    # Step 1: Lookup metadata from registry
    metadata = get_provider_metadata(slug)
    if not metadata:
        supported = ", ".join([p.slug for p in PROVIDER_REGISTRY])
        raise ValueError(f"Unknown provider: {slug}. Supported: {supported}")

    # Step 2: Validate required settings (registry-driven)
    if metadata.required_settings:
        for setting_name in metadata.required_settings:
            if not getattr(settings, setting_name, None):
                required = ", ".join(metadata.required_settings)
                raise ValueError(
                    f"Provider '{slug}' not configured. Required settings: {required}"
                )

    # Step 3: Lazy import and instantiate (avoid circular imports)
    match slug:
        case "schwab":
            from src.infrastructure.providers.schwab import SchwabProvider

            return SchwabProvider(settings=settings)

        case "alpaca":
            from src.infrastructure.providers.alpaca import AlpacaProvider

            return AlpacaProvider(settings=settings)

        case "chase_file":
            from src.infrastructure.providers.chase import ChaseFileProvider

            return ChaseFileProvider()

        case _:
            # This should never happen (registry validation in Step 1)
            raise ValueError(
                f"Provider '{slug}' in registry but no factory defined. "
                "This is a bug - please report to maintainers."
            )


def is_oauth_provider(
    provider: "ProviderProtocol",
) -> TypeGuard["OAuthProviderProtocol"]:
    """Check if provider supports OAuth authentication (registry-driven).

    TypeGuard function that performs runtime check and narrows type.
    After this returns True, the provider is typed as OAuthProviderProtocol.

    Registry-Driven (F8.1):
        - Uses get_oauth_providers() from registry
        - Zero drift: OAuth list always in sync with registry
        - Self-enforcing: Tests verify OAuth providers match reality

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
        - docs/architecture/provider-registry-architecture.md
        - docs/architecture/provider-integration-architecture.md
    """
    return provider.slug in get_oauth_providers()
