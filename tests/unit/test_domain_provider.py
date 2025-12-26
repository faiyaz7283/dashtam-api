"""Unit tests for Provider domain entity.

Tests cover:
- Entity creation with valid data
- Validation errors for invalid data
- String representations (__str__, __repr__)
- Optional field handling

Architecture:
- Unit tests for domain entity (no database, no I/O)
- Tests business rules defined in entity
- Uses pytest parameterization for edge cases
"""

from datetime import UTC, datetime

import pytest
from uuid_extensions import uuid7

from src.domain.entities.provider import Provider
from src.domain.enums.credential_type import CredentialType
from src.domain.enums.provider_category import ProviderCategory


# =============================================================================
# Test Classes
# =============================================================================


class TestProviderCreation:
    """Test Provider entity creation."""

    def test_create_minimal_provider(self):
        """Test creating provider with required fields only."""
        provider_id = uuid7()
        provider = Provider(
            id=provider_id,
            slug="schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
        )

        assert provider.id == provider_id
        assert provider.slug == "schwab"
        assert provider.name == "Charles Schwab"
        assert provider.category == ProviderCategory.BROKERAGE
        assert provider.credential_type == CredentialType.OAUTH2
        assert provider.is_active is True  # Default
        assert provider.description is None
        assert provider.logo_url is None
        assert provider.website_url is None

    def test_create_full_provider(self):
        """Test creating provider with all fields."""
        provider_id = uuid7()
        now = datetime.now(UTC)

        provider = Provider(
            id=provider_id,
            slug="chase",
            name="Chase Bank",
            category=ProviderCategory.BANK,
            credential_type=CredentialType.API_KEY,
            description="Chase banking and credit cards",
            logo_url="https://example.com/chase-logo.png",
            website_url="https://www.chase.com",
            is_active=False,
            created_at=now,
            updated_at=now,
        )

        assert provider.id == provider_id
        assert provider.slug == "chase"
        assert provider.name == "Chase Bank"
        assert provider.category == ProviderCategory.BANK
        assert provider.credential_type == CredentialType.API_KEY
        assert provider.description == "Chase banking and credit cards"
        assert provider.logo_url == "https://example.com/chase-logo.png"
        assert provider.website_url == "https://www.chase.com"
        assert provider.is_active is False
        assert provider.created_at == now
        assert provider.updated_at == now

    def test_create_with_default_timestamps(self):
        """Test that timestamps default to current UTC time."""
        before = datetime.now(UTC)
        provider = Provider(
            id=uuid7(),
            slug="test",
            name="Test Provider",
            category=ProviderCategory.OTHER,
            credential_type=CredentialType.OAUTH2,
        )
        after = datetime.now(UTC)

        assert before <= provider.created_at <= after
        assert before <= provider.updated_at <= after

    @pytest.mark.parametrize("cred_type", list(CredentialType))
    def test_create_with_all_credential_types(self, cred_type):
        """Test creating provider with each credential type."""
        provider = Provider(
            id=uuid7(),
            slug=f"provider-{cred_type.value}",
            name=f"Provider for {cred_type.value}",
            category=ProviderCategory.OTHER,
            credential_type=cred_type,
        )

        assert provider.credential_type == cred_type


class TestProviderSlugValidation:
    """Test Provider slug validation rules."""

    def test_empty_slug_raises_error(self):
        """Test that empty slug raises ValueError."""
        with pytest.raises(ValueError, match="slug cannot be empty"):
            Provider(
                id=uuid7(),
                slug="",
                name="Test Provider",
                category=ProviderCategory.OTHER,
                credential_type=CredentialType.OAUTH2,
            )

    def test_slug_too_long_raises_error(self):
        """Test that slug > 50 chars raises ValueError."""
        long_slug = "a" * 51
        with pytest.raises(ValueError, match="cannot exceed 50 characters"):
            Provider(
                id=uuid7(),
                slug=long_slug,
                name="Test Provider",
                category=ProviderCategory.OTHER,
                credential_type=CredentialType.OAUTH2,
            )

    def test_slug_exactly_50_chars_is_valid(self):
        """Test that slug exactly 50 chars is valid."""
        slug_50 = "a" * 50
        provider = Provider(
            id=uuid7(),
            slug=slug_50,
            name="Test Provider",
            category=ProviderCategory.OTHER,
            credential_type=CredentialType.OAUTH2,
        )
        assert len(provider.slug) == 50

    def test_slug_with_special_chars_raises_error(self):
        """Test that slug with special characters raises ValueError."""
        with pytest.raises(ValueError, match="alphanumeric with hyphens/underscores"):
            Provider(
                id=uuid7(),
                slug="schwab.com",
                name="Test Provider",
                category=ProviderCategory.OTHER,
                credential_type=CredentialType.OAUTH2,
            )

    def test_slug_with_spaces_raises_error(self):
        """Test that slug with spaces raises ValueError."""
        with pytest.raises(ValueError, match="alphanumeric with hyphens/underscores"):
            Provider(
                id=uuid7(),
                slug="charles schwab",
                name="Test Provider",
                category=ProviderCategory.OTHER,
                credential_type=CredentialType.OAUTH2,
            )

    def test_uppercase_slug_raises_error(self):
        """Test that uppercase slug raises ValueError."""
        with pytest.raises(ValueError, match="must be lowercase"):
            Provider(
                id=uuid7(),
                slug="Schwab",
                name="Test Provider",
                category=ProviderCategory.OTHER,
                credential_type=CredentialType.OAUTH2,
            )

    def test_slug_with_hyphens_is_valid(self):
        """Test that slug with hyphens is valid."""
        provider = Provider(
            id=uuid7(),
            slug="charles-schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
        )
        assert provider.slug == "charles-schwab"

    def test_slug_with_underscores_is_valid(self):
        """Test that slug with underscores is valid."""
        provider = Provider(
            id=uuid7(),
            slug="charles_schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
        )
        assert provider.slug == "charles_schwab"

    def test_slug_with_numbers_is_valid(self):
        """Test that slug with numbers is valid."""
        provider = Provider(
            id=uuid7(),
            slug="provider123",
            name="Provider 123",
            category=ProviderCategory.OTHER,
            credential_type=CredentialType.OAUTH2,
        )
        assert provider.slug == "provider123"


class TestProviderNameValidation:
    """Test Provider name validation rules."""

    def test_empty_name_raises_error(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            Provider(
                id=uuid7(),
                slug="test",
                name="",
                category=ProviderCategory.OTHER,
                credential_type=CredentialType.OAUTH2,
            )

    def test_name_too_long_raises_error(self):
        """Test that name > 100 chars raises ValueError."""
        long_name = "A" * 101
        with pytest.raises(ValueError, match="cannot exceed 100 characters"):
            Provider(
                id=uuid7(),
                slug="test",
                name=long_name,
                category=ProviderCategory.OTHER,
                credential_type=CredentialType.OAUTH2,
            )

    def test_name_exactly_100_chars_is_valid(self):
        """Test that name exactly 100 chars is valid."""
        name_100 = "A" * 100
        provider = Provider(
            id=uuid7(),
            slug="test",
            name=name_100,
            category=ProviderCategory.OTHER,
            credential_type=CredentialType.OAUTH2,
        )
        assert len(provider.name) == 100


class TestProviderStringRepresentations:
    """Test Provider __str__ and __repr__ methods."""

    def test_str_active_provider(self):
        """Test __str__ for active provider."""
        provider = Provider(
            id=uuid7(),
            slug="schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
            is_active=True,
        )

        result = str(provider)
        assert "Charles Schwab" in result
        assert "schwab" in result
        assert "active" in result

    def test_str_inactive_provider(self):
        """Test __str__ for inactive provider."""
        provider = Provider(
            id=uuid7(),
            slug="legacy",
            name="Legacy Provider",
            category=ProviderCategory.OTHER,
            credential_type=CredentialType.API_KEY,
            is_active=False,
        )

        result = str(provider)
        assert "Legacy Provider" in result
        assert "legacy" in result
        assert "inactive" in result

    def test_repr_contains_key_fields(self):
        """Test __repr__ contains slug, name, and is_active."""
        provider = Provider(
            id=uuid7(),
            slug="test",
            name="Test Provider",
            category=ProviderCategory.OTHER,
            credential_type=CredentialType.OAUTH2,
            is_active=True,
        )

        result = repr(provider)
        assert "Provider(" in result
        assert "slug='test'" in result
        assert "name='Test Provider'" in result
        assert "is_active=True" in result


class TestProviderEquality:
    """Test Provider equality and hashing."""

    def test_same_id_different_instances_equal(self):
        """Test that providers with same data are equal (dataclass default)."""
        provider_id = uuid7()
        now = datetime.now(UTC)

        p1 = Provider(
            id=provider_id,
            slug="schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
            created_at=now,
            updated_at=now,
        )
        p2 = Provider(
            id=provider_id,
            slug="schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
            created_at=now,
            updated_at=now,
        )

        assert p1 == p2

    def test_different_id_not_equal(self):
        """Test that providers with different IDs are not equal."""
        p1 = Provider(
            id=uuid7(),
            slug="schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
        )
        p2 = Provider(
            id=uuid7(),
            slug="schwab",
            name="Charles Schwab",
            category=ProviderCategory.BROKERAGE,
            credential_type=CredentialType.OAUTH2,
        )

        assert p1 != p2
