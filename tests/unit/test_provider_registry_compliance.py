"""Provider registry compliance tests.

Self-enforcing tests that verify provider registry completeness and prevent drift.
These tests fail if:
- Registry entry exists but no factory in container
- Factory exists but no registry entry
- Metadata incomplete (missing display_name, etc.)
- OAuth providers mismatch between registry and reality

Pattern:
    Same as F7.7 Domain Events Registry - tests enforce single source of truth.
    Cannot merge PR if registry/factory drift occurs.

Reference:
    - docs/architecture/provider-registry-architecture.md
    - docs/architecture/registry-pattern-architecture.md (F7.7)
"""

import pytest

from src.core.container.providers import get_provider, is_oauth_provider
from src.domain.providers.registry import (
    PROVIDER_REGISTRY,
    ProviderAuthType,
    ProviderCategory,
    get_all_provider_slugs,
    get_oauth_providers,
    get_provider_metadata,
    get_providers_by_category,
    get_statistics,
)


class TestProviderRegistryCompleteness:
    """Test suite for provider registry completeness and consistency."""

    def test_all_providers_can_be_instantiated(self):
        """Verify all registered providers have working factories.

        This test fails if:
        - Provider in registry but no factory case in container
        - Provider factory raises exception (settings validation, etc.)

        Note: Providers with required_settings will be skipped in CI
        if settings not present. This is expected behavior.
        """
        for metadata in PROVIDER_REGISTRY:
            # Skip providers requiring settings (they'll fail in CI without real keys)
            if metadata.required_settings:
                pytest.skip(
                    f"Provider {metadata.slug} requires settings: "
                    f"{', '.join(metadata.required_settings)}"
                )

            # This will raise if factory missing or settings invalid
            provider = get_provider(metadata.slug)

            # Verify slug matches
            assert provider.slug == metadata.slug, (
                f"Provider factory returned wrong slug. "
                f"Expected: {metadata.slug}, Got: {provider.slug}"
            )

    def test_all_providers_have_display_names(self):
        """Verify all providers have user-facing display names.

        Display names are shown in UI, logs, and documentation.
        This test fails if display_name is empty or None.
        """
        for metadata in PROVIDER_REGISTRY:
            assert metadata.display_name, (
                f"Provider {metadata.slug} missing display_name. "
                f"All providers must have user-facing names."
            )
            assert len(metadata.display_name) > 0, (
                f"Provider {metadata.slug} has empty display_name"
            )

    def test_registry_slugs_are_unique(self):
        """Verify no duplicate slugs in registry.

        Slugs are used as unique identifiers in URLs, database, and code.
        Duplicate slugs would cause ambiguity and routing errors.
        """
        slugs = get_all_provider_slugs()
        duplicates = [slug for slug in slugs if slugs.count(slug) > 1]

        assert len(slugs) == len(set(slugs)), (
            f"Duplicate slugs found in registry: {set(duplicates)}. "
            f"Each provider must have a unique slug."
        )

    def test_all_providers_have_capabilities(self):
        """Verify all providers have at least one capability enabled.

        Providers must support at least one of:
        - accounts
        - transactions
        - holdings
        - balance_history

        This test fails if all capability flags are False.
        """
        for metadata in PROVIDER_REGISTRY:
            has_capability = (
                metadata.supports_accounts
                or metadata.supports_transactions
                or metadata.supports_holdings
                or metadata.supports_balance_history
            )

            assert has_capability, (
                f"Provider {metadata.slug} has no capabilities enabled. "
                f"At least one of supports_accounts, supports_transactions, "
                f"supports_holdings, or supports_balance_history must be True."
            )

    def test_all_providers_have_required_settings(self):
        """Verify required_settings field is properly configured.

        Required settings must be:
        - A list (not None for providers with settings)
        - Empty list for providers without settings (file import, etc.)
        - Valid settings.Config attribute names

        This test verifies field presence, not actual settings values.
        """
        for metadata in PROVIDER_REGISTRY:
            # required_settings should be a list or None
            assert metadata.required_settings is not None or isinstance(
                metadata.required_settings, list
            ), (
                f"Provider {metadata.slug} has invalid required_settings. "
                f"Must be a list (empty for no settings) or None."
            )

            # If list, verify it's actually a list type
            if metadata.required_settings is not None:
                assert isinstance(metadata.required_settings, list), (
                    f"Provider {metadata.slug} required_settings must be a list"
                )

    def test_oauth_providers_match_registry(self):
        """Verify OAuth provider list matches registry metadata.

        get_oauth_providers() should return exactly those providers
        with auth_type == ProviderAuthType.OAUTH.

        This test detects drift between OAuth list and auth_type metadata.
        """
        oauth_slugs = set(get_oauth_providers())
        expected_oauth_slugs = {
            p.slug for p in PROVIDER_REGISTRY if p.auth_type == ProviderAuthType.OAUTH
        }

        assert oauth_slugs == expected_oauth_slugs, (
            f"OAuth providers mismatch. "
            f"get_oauth_providers() returned: {oauth_slugs}, "
            f"but registry has OAuth auth_type: {expected_oauth_slugs}. "
            f"Difference: {oauth_slugs.symmetric_difference(expected_oauth_slugs)}"
        )

    def test_get_provider_metadata_returns_correct_data(self):
        """Verify get_provider_metadata() returns correct metadata for each provider."""
        for metadata in PROVIDER_REGISTRY:
            retrieved = get_provider_metadata(metadata.slug)

            assert retrieved is not None, (
                f"get_provider_metadata('{metadata.slug}') returned None. "
                f"Provider should be in registry."
            )

            # Verify it's the same object
            assert retrieved == metadata, (
                f"get_provider_metadata('{metadata.slug}') returned different metadata. "
                f"Expected: {metadata}, Got: {retrieved}"
            )

        # Test non-existent provider
        assert get_provider_metadata("nonexistent") is None, (
            "get_provider_metadata() should return None for unknown providers"
        )

    def test_get_oauth_providers_filters_correctly(self):
        """Verify get_oauth_providers() only returns OAuth providers."""
        oauth_slugs = get_oauth_providers()

        for slug in oauth_slugs:
            metadata = get_provider_metadata(slug)
            assert metadata is not None, f"OAuth provider {slug} not in registry"
            assert metadata.auth_type == ProviderAuthType.OAUTH, (
                f"Provider {slug} in OAuth list but auth_type is {metadata.auth_type}"
            )

        # Verify non-OAuth providers are excluded
        non_oauth_types = {
            ProviderAuthType.API_KEY,
            ProviderAuthType.FILE_IMPORT,
            ProviderAuthType.LINK_TOKEN,
            ProviderAuthType.CERTIFICATE,
        }

        for metadata in PROVIDER_REGISTRY:
            if metadata.auth_type in non_oauth_types:
                assert metadata.slug not in oauth_slugs, (
                    f"Non-OAuth provider {metadata.slug} ({metadata.auth_type}) "
                    f"incorrectly included in OAuth provider list"
                )

    def test_get_statistics_accurate(self):
        """Verify get_statistics() returns accurate counts."""
        stats = get_statistics()

        # Verify total count
        assert stats["total_providers"] == len(PROVIDER_REGISTRY), (
            f"total_providers mismatch. "
            f"Expected: {len(PROVIDER_REGISTRY)}, Got: {stats['total_providers']}"
        )

        # Verify OAuth count
        expected_oauth = len(get_oauth_providers())
        assert stats["oauth_providers"] == expected_oauth, (
            f"oauth_providers mismatch. "
            f"Expected: {expected_oauth}, Got: {stats['oauth_providers']}"
        )

        # Verify brokerage count
        expected_brokerages = len(get_providers_by_category(ProviderCategory.BROKERAGE))
        assert stats["brokerages"] == expected_brokerages, (
            f"brokerages mismatch. "
            f"Expected: {expected_brokerages}, Got: {stats['brokerages']}"
        )

        # Verify bank count
        expected_banks = len(get_providers_by_category(ProviderCategory.BANK))
        assert stats["banks"] == expected_banks, (
            f"banks mismatch. Expected: {expected_banks}, Got: {stats['banks']}"
        )

        # Verify production_ready count
        expected_production_ready = len(
            [p for p in PROVIDER_REGISTRY if p.is_production_ready]
        )
        assert stats["production_ready"] == expected_production_ready, (
            f"production_ready mismatch. "
            f"Expected: {expected_production_ready}, Got: {stats['production_ready']}"
        )

    def test_provider_categories_valid(self):
        """Verify all provider categories are valid ProviderCategory enum values."""
        for metadata in PROVIDER_REGISTRY:
            assert isinstance(metadata.category, ProviderCategory), (
                f"Provider {metadata.slug} has invalid category type. "
                f"Expected: ProviderCategory, Got: {type(metadata.category)}"
            )

            # Verify it's one of the known categories
            valid_categories = set(ProviderCategory)
            assert metadata.category in valid_categories, (
                f"Provider {metadata.slug} has unknown category: {metadata.category}. "
                f"Valid categories: {[c.value for c in valid_categories]}"
            )


class TestProviderRegistryIntegration:
    """Test suite for provider registry integration with container."""

    def test_is_oauth_provider_matches_registry(self):
        """Verify is_oauth_provider() matches registry auth_type.

        Skip providers requiring settings (they'll fail in CI).
        """
        oauth_slugs = set(get_oauth_providers())

        for metadata in PROVIDER_REGISTRY:
            # Skip providers requiring settings
            if metadata.required_settings:
                continue

            provider = get_provider(metadata.slug)

            # Check is_oauth_provider() result
            result = is_oauth_provider(provider)

            # Verify it matches registry
            expected = metadata.slug in oauth_slugs
            assert result == expected, (
                f"is_oauth_provider() mismatch for {metadata.slug}. "
                f"Registry says OAuth: {expected}, is_oauth_provider(): {result}"
            )

    def test_get_providers_by_category_returns_correct_providers(self):
        """Verify get_providers_by_category() returns all providers in category."""
        # Test each category
        for category in ProviderCategory:
            providers = get_providers_by_category(category)

            # Verify all returned providers have correct category
            for metadata in providers:
                assert metadata.category == category, (
                    f"Provider {metadata.slug} returned for category {category} "
                    f"but has category {metadata.category}"
                )

            # Verify we didn't miss any
            expected_slugs = {
                p.slug for p in PROVIDER_REGISTRY if p.category == category
            }
            actual_slugs = {p.slug for p in providers}

            assert actual_slugs == expected_slugs, (
                f"get_providers_by_category({category}) mismatch. "
                f"Expected: {expected_slugs}, Got: {actual_slugs}"
            )

    def test_container_fails_for_unknown_provider(self):
        """Verify get_provider() raises ValueError for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_provider")

    def test_container_error_message_lists_supported_providers(self):
        """Verify error message lists all supported providers."""
        try:
            get_provider("invalid")
        except ValueError as e:
            error_msg = str(e)

            # Verify error message contains "Supported:"
            assert "Supported:" in error_msg, (
                "Error message should list supported providers"
            )

            # Verify all provider slugs are in error message
            for slug in get_all_provider_slugs():
                assert slug in error_msg, (
                    f"Provider {slug} not listed in error message: {error_msg}"
                )


class TestProviderRegistryStatistics:
    """Test suite for provider registry statistics and current state."""

    def test_current_provider_count(self):
        """Verify we have exactly 3 providers (Schwab, Alpaca, Chase).

        Update this test when adding new providers.
        """
        assert len(PROVIDER_REGISTRY) == 3, (
            f"Expected 3 providers (Schwab, Alpaca, Chase), "
            f"but registry has {len(PROVIDER_REGISTRY)}. "
            f"If you added a new provider, update this test."
        )

    def test_current_oauth_provider_count(self):
        """Verify we have exactly 1 OAuth provider (Schwab).

        Update this test when adding new OAuth providers.
        """
        oauth_count = len(get_oauth_providers())
        assert oauth_count == 1, (
            f"Expected 1 OAuth provider (Schwab), but found {oauth_count}. "
            f"OAuth providers: {get_oauth_providers()}"
        )

    def test_schwab_in_registry(self):
        """Verify Schwab provider is in registry with correct metadata."""
        metadata = get_provider_metadata("schwab")

        assert metadata is not None, "Schwab provider not in registry"
        assert metadata.display_name == "Charles Schwab"
        assert metadata.category == ProviderCategory.BROKERAGE
        assert metadata.auth_type == ProviderAuthType.OAUTH
        assert metadata.supports_accounts is True
        assert metadata.supports_transactions is True
        assert metadata.supports_holdings is True
        assert "schwab_api_key" in (metadata.required_settings or [])
        assert "schwab_api_secret" in (metadata.required_settings or [])

    def test_alpaca_in_registry(self):
        """Verify Alpaca provider is in registry with correct metadata."""
        metadata = get_provider_metadata("alpaca")

        assert metadata is not None, "Alpaca provider not in registry"
        assert metadata.display_name == "Alpaca Markets"
        assert metadata.category == ProviderCategory.BROKERAGE
        assert metadata.auth_type == ProviderAuthType.API_KEY
        assert metadata.supports_accounts is True
        assert metadata.supports_transactions is True
        assert metadata.supports_holdings is True
        assert metadata.required_settings == []  # API key per-request

    def test_chase_file_in_registry(self):
        """Verify Chase file import provider is in registry with correct metadata."""
        metadata = get_provider_metadata("chase_file")

        assert metadata is not None, "Chase file provider not in registry"
        assert metadata.display_name == "Chase Bank (File Import)"
        assert metadata.category == ProviderCategory.BANK
        assert metadata.auth_type == ProviderAuthType.FILE_IMPORT
        assert metadata.supports_accounts is True
        assert metadata.supports_transactions is True
        assert metadata.supports_holdings is False  # Banks don't have holdings
        assert metadata.required_settings == []  # File content per-request
