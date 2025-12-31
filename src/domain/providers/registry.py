"""Provider Registry - Single source of truth for all provider metadata.

This module defines the Provider Registry Pattern for managing financial provider
adapters. It provides a centralized catalog of all providers with their metadata,
capabilities, and configuration requirements.

Pattern Benefits:
    - Zero Drift: Can't forget to add provider to OAuth list
    - Self-Documenting: Registry shows all providers at a glance
    - Centralized Validation: Settings validation in one place
    - Type Safety: Compile-time verification via helper functions
    - Code Reduction: ~30% less container code

Registry Structure:
    - ProviderMetadata: Dataclass with provider configuration
    - PROVIDER_REGISTRY: List of all provider metadata entries
    - Helper Functions: Query and statistics utilities

Usage:
    # Get provider metadata
    from src.domain.providers.registry import get_provider_metadata

    metadata = get_provider_metadata("schwab")
    if metadata.auth_type == ProviderAuthType.OAUTH:
        # Handle OAuth flow
        ...

    # Get all OAuth providers
    oauth_providers = get_oauth_providers()

    # Get statistics
    stats = get_statistics()
    print(f"Total providers: {stats['total_providers']}")

Reference:
    - docs/architecture/provider-registry-architecture.md
    - docs/architecture/registry-pattern-architecture.md (F7.7)

Created: 2025-12-31 (F8.1: Provider Integration Registry)
"""

from dataclasses import dataclass
from enum import Enum

from src.domain.enums import CredentialType


class ProviderCategory(str, Enum):
    """Provider categories by financial institution type.

    Used for filtering and organizing providers in the registry.
    String enum for easy serialization and database storage.
    """

    BROKERAGE = "brokerage"
    """Brokerage accounts (stocks, bonds, ETFs, mutual funds).
    
    Examples: Charles Schwab, Fidelity, TD Ameritrade, Alpaca.
    """

    BANK = "bank"
    """Banking accounts (checking, savings, credit cards).
    
    Examples: Chase, Bank of America, Wells Fargo.
    """

    CRYPTO = "crypto"
    """Cryptocurrency exchanges and wallets.
    
    Examples: Coinbase, Binance, Kraken.
    """

    RETIREMENT = "retirement"
    """Retirement accounts (401k, IRA, pension).
    
    May overlap with BROKERAGE for provider classification.
    Examples: Vanguard (retirement-focused), Fidelity 401k.
    """

    INVESTMENT = "investment"
    """Investment platforms and robo-advisors.
    
    Examples: Betterment, Wealthfront, Acorns.
    """

    OTHER = "other"
    """Other financial institutions not fitting above categories.
    
    Used for specialty providers or future expansion.
    """


class ProviderAuthType(str, Enum):
    """Provider authentication mechanism types.

    Determines how the provider authenticates and what OAuth/API
    patterns are used. Maps to CredentialType but focuses on
    authentication flow rather than storage format.

    String enum for easy serialization and database storage.
    """

    OAUTH = "oauth"
    """OAuth 2.0 authentication flow.
    
    Requires redirect URLs, authorization codes, token exchange.
    Used by most modern brokerages for security and user consent.
    
    Providers: Schwab, Fidelity, TD Ameritrade, Robinhood.
    """

    API_KEY = "api_key"
    """Simple API key authentication.
    
    Static credentials (key + optional secret) passed in headers.
    No user interaction required. Used by data providers and some
    brokerages for programmatic access.
    
    Providers: Alpaca, Alpha Vantage, Polygon.io.
    """

    FILE_IMPORT = "file_import"
    """File-based data import (no live authentication).
    
    User downloads files (QFX, OFX, CSV) from provider website
    and uploads to Dashtam for parsing. No API credentials needed.
    
    Providers: Chase (file import), any institution with downloadable statements.
    """

    LINK_TOKEN = "link_token"
    """Aggregator-style link tokens.
    
    Used by third-party aggregation services (Plaid, Yodlee).
    Similar to OAuth but with aggregator-specific token format.
    
    Providers: Plaid-connected institutions.
    """

    CERTIFICATE = "certificate"
    """mTLS certificate-based authentication.
    
    Mutual TLS with client certificates. Used by enterprise-grade
    providers requiring hardware security modules.
    
    Providers: Some institutional providers (rare).
    """


@dataclass(frozen=True, kw_only=True)
class ProviderMetadata:
    """Metadata for a single financial provider adapter.

    Single source of truth for all provider configuration, capabilities,
    and requirements. Used by container for provider instantiation and
    validation, and by tests for compliance verification.

    Attributes:
        slug: Unique provider identifier (lowercase, snake_case).
            Used in URLs, database, and code references.
        display_name: User-facing provider name.
            Displayed in UI, logs, and documentation.
        category: Financial institution type (brokerage, bank, etc.).
            Used for filtering and organization.
        auth_type: Authentication mechanism (OAuth, API key, etc.).
            Determines authentication flow.
        credential_type: Credential storage format.
            Maps to CredentialType enum for persistence layer.
        supports_accounts: Whether provider supports account syncing.
            Most providers support this (default: True).
        supports_transactions: Whether provider supports transaction syncing.
            Most providers support this (default: True).
        supports_holdings: Whether provider supports holdings/positions.
            Brokerages support this, banks typically don't (default: True).
        supports_balance_history: Whether provider supports historical balances.
            Advanced feature, not all providers support (default: False).
        required_settings: List of settings.Config attribute names required.
            e.g., ["schwab_api_key", "schwab_api_secret"]
            Empty list if no settings required (e.g., file import).
        documentation_url: Official provider API documentation URL.
            Helpful for developers adding new provider support.
        is_production_ready: Whether provider is ready for production use.
            False for experimental/in-development providers (default: True).

    Example:
        >>> metadata = ProviderMetadata(
        ...     slug="schwab",
        ...     display_name="Charles Schwab",
        ...     category=ProviderCategory.BROKERAGE,
        ...     auth_type=ProviderAuthType.OAUTH,
        ...     credential_type=CredentialType.OAUTH2,
        ...     required_settings=["schwab_api_key", "schwab_api_secret"],
        ...     documentation_url="https://developer.schwab.com",
        ... )
    """

    # Identity
    slug: str
    display_name: str
    category: ProviderCategory

    # Authentication
    auth_type: ProviderAuthType
    credential_type: CredentialType

    # Capabilities (what data can this provider sync?)
    supports_accounts: bool = True
    supports_transactions: bool = True
    supports_holdings: bool = True
    supports_balance_history: bool = False

    # Settings validation (required config attributes)
    required_settings: list[str] | None = None

    # Metadata
    documentation_url: str | None = None
    is_production_ready: bool = True


# =============================================================================
# Provider Registry (Single Source of Truth)
# =============================================================================

PROVIDER_REGISTRY: list[ProviderMetadata] = [
    ProviderMetadata(
        slug="schwab",
        display_name="Charles Schwab",
        category=ProviderCategory.BROKERAGE,
        auth_type=ProviderAuthType.OAUTH,
        credential_type=CredentialType.OAUTH2,
        supports_accounts=True,
        supports_transactions=True,
        supports_holdings=True,
        supports_balance_history=False,
        required_settings=["schwab_api_key", "schwab_api_secret"],
        documentation_url="https://developer.schwab.com",
        is_production_ready=True,
    ),
    ProviderMetadata(
        slug="alpaca",
        display_name="Alpaca Markets",
        category=ProviderCategory.BROKERAGE,
        auth_type=ProviderAuthType.API_KEY,
        credential_type=CredentialType.API_KEY,
        supports_accounts=True,
        supports_transactions=True,
        supports_holdings=True,
        supports_balance_history=False,
        required_settings=[],  # API key passed per-request, not in settings
        documentation_url="https://alpaca.markets/docs",
        is_production_ready=True,
    ),
    ProviderMetadata(
        slug="chase_file",
        display_name="Chase Bank (File Import)",
        category=ProviderCategory.BANK,
        auth_type=ProviderAuthType.FILE_IMPORT,
        credential_type=CredentialType.FILE_IMPORT,
        supports_accounts=True,
        supports_transactions=True,
        supports_holdings=False,  # Banks don't have holdings/positions
        supports_balance_history=False,
        required_settings=[],  # File content passed per-request
        documentation_url=None,  # No API docs for file import
        is_production_ready=True,
    ),
]
"""Provider registry containing all financial provider metadata.

This is the single source of truth for all providers in Dashtam.
When adding a new provider:
1. Add ProviderMetadata entry here
2. Implement provider class in src/infrastructure/providers/{slug}/
3. Add factory case in src/core/container/providers.py
4. Tests will enforce completeness (see test_provider_registry_compliance.py)

Current Providers:
    - schwab: Charles Schwab (OAuth, brokerage)
    - alpaca: Alpaca Markets (API Key, brokerage)
    - chase_file: Chase Bank (File Import, bank)

Adding New Provider:
    See docs/guides/adding-new-providers.md for step-by-step guide.
"""


# =============================================================================
# Helper Functions
# =============================================================================


def get_provider_metadata(slug: str) -> ProviderMetadata | None:
    """Get provider metadata by slug.

    Args:
        slug: Provider identifier (e.g., "schwab", "alpaca").

    Returns:
        ProviderMetadata if found, None otherwise.

    Example:
        >>> metadata = get_provider_metadata("schwab")
        >>> if metadata:
        ...     print(metadata.display_name)  # "Charles Schwab"
        ...     print(metadata.auth_type)     # ProviderAuthType.OAUTH
    """
    return next((p for p in PROVIDER_REGISTRY if p.slug == slug), None)


def get_all_provider_slugs() -> list[str]:
    """Get all registered provider slugs.

    Returns:
        List of provider slugs (e.g., ["schwab", "alpaca", "chase_file"]).

    Example:
        >>> slugs = get_all_provider_slugs()
        >>> print(", ".join(slugs))  # "schwab, alpaca, chase_file"
    """
    return [p.slug for p in PROVIDER_REGISTRY]


def get_oauth_providers() -> list[str]:
    """Get slugs of all OAuth providers.

    Useful for determining which providers require OAuth redirect URLs
    and authorization code exchange flows.

    Returns:
        List of OAuth provider slugs (e.g., ["schwab"]).

    Example:
        >>> oauth_slugs = get_oauth_providers()
        >>> is_oauth = provider_slug in oauth_slugs
    """
    return [p.slug for p in PROVIDER_REGISTRY if p.auth_type == ProviderAuthType.OAUTH]


def get_providers_by_category(category: ProviderCategory) -> list[ProviderMetadata]:
    """Get all providers in a specific category.

    Args:
        category: Provider category to filter by.

    Returns:
        List of provider metadata for matching category.

    Example:
        >>> brokerages = get_providers_by_category(ProviderCategory.BROKERAGE)
        >>> print([p.display_name for p in brokerages])
        ['Charles Schwab', 'Alpaca Markets']
    """
    return [p for p in PROVIDER_REGISTRY if p.category == category]


def get_statistics() -> dict[str, int]:
    """Get provider registry statistics.

    Returns:
        Dictionary with provider counts by various dimensions:
            - total_providers: Total number of registered providers
            - oauth_providers: Number of OAuth providers
            - brokerages: Number of brokerage providers
            - banks: Number of bank providers
            - production_ready: Number of production-ready providers

    Example:
        >>> stats = get_statistics()
        >>> print(f"Total: {stats['total_providers']}")
        Total: 3
        >>> print(f"OAuth: {stats['oauth_providers']}")
        OAuth: 1
    """
    return {
        "total_providers": len(PROVIDER_REGISTRY),
        "oauth_providers": len(get_oauth_providers()),
        "brokerages": len(get_providers_by_category(ProviderCategory.BROKERAGE)),
        "banks": len(get_providers_by_category(ProviderCategory.BANK)),
        "crypto": len(get_providers_by_category(ProviderCategory.CRYPTO)),
        "production_ready": len(
            [p for p in PROVIDER_REGISTRY if p.is_production_ready]
        ),
    }
