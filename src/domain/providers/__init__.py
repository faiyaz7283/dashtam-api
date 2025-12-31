"""Provider domain module.

Exports provider registry and related types for use throughout the application.
"""

from src.domain.providers.registry import (
    PROVIDER_REGISTRY,
    ProviderAuthType,
    ProviderCategory,
    ProviderMetadata,
    get_all_provider_slugs,
    get_oauth_providers,
    get_provider_metadata,
    get_providers_by_category,
    get_statistics,
)

__all__ = [
    # Registry
    "PROVIDER_REGISTRY",
    # Types
    "ProviderMetadata",
    "ProviderCategory",
    "ProviderAuthType",
    # Helper Functions
    "get_provider_metadata",
    "get_all_provider_slugs",
    "get_oauth_providers",
    "get_providers_by_category",
    "get_statistics",
]
