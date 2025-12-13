"""Integration tests for ProviderRepository.

Tests cover:
- Save and retrieve provider
- Find by ID
- Find by slug
- List all providers
- List active providers
- Exists by slug
- Update existing provider
- Entity ↔ Model mapping

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations

Note: The test database is seeded with a Schwab provider, so some tests
account for this existing data.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from uuid_extensions import uuid7

from src.domain.entities.provider import Provider
from src.domain.enums.credential_type import CredentialType
from src.infrastructure.persistence.repositories.provider_repository import (
    ProviderRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


def create_test_provider(
    provider_id=None,
    slug=None,
    name="Test Provider",
    credential_type=CredentialType.OAUTH2,
    description=None,
    logo_url=None,
    website_url=None,
    is_active=True,
) -> Provider:
    """Create a test Provider with default values.

    Args:
        provider_id: Optional UUID for the provider.
        slug: Optional slug (defaults to unique slug based on ID).
        name: Provider name.
        credential_type: Authentication type.
        description: Optional description.
        logo_url: Optional logo URL.
        website_url: Optional website URL.
        is_active: Whether provider is active.

    Returns:
        Provider domain entity.
    """
    provider_id = provider_id or uuid7()
    # Generate unique slug if not provided
    if slug is None:
        slug = f"test-{provider_id.hex[:8]}"

    now = datetime.now(UTC)
    return Provider(
        id=provider_id,
        slug=slug,
        name=name,
        credential_type=credential_type,
        description=description,
        logo_url=logo_url,
        website_url=website_url,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_test_providers(test_database):
    """Clean up test providers after each test.

    Note: We don't truncate the providers table because the seeded schwab
    provider is needed for FK constraints in other tables. Instead, we
    delete only providers created during tests (slug starting with 'test-').
    """
    yield
    # Cleanup after test
    async with test_database.get_session() as session:
        await session.execute(text("DELETE FROM providers WHERE slug LIKE 'test-%'"))
        await session.commit()


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestProviderRepositorySave:
    """Test ProviderRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_creates_new_provider(self, test_database):
        """Test saving a new provider persists it to the database."""
        # Arrange
        provider = create_test_provider(
            slug="test-new",
            name="New Provider",
            credential_type=CredentialType.OAUTH2,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_id(provider.id)

            assert found is not None
            assert found.id == provider.id
            assert found.slug == "test-new"
            assert found.name == "New Provider"
            assert found.credential_type == CredentialType.OAUTH2

    @pytest.mark.asyncio
    async def test_save_with_all_fields(self, test_database):
        """Test saving provider with all optional fields."""
        # Arrange
        provider = create_test_provider(
            slug="test-full",
            name="Full Provider",
            credential_type=CredentialType.API_KEY,
            description="A fully populated provider",
            logo_url="https://example.com/logo.png",
            website_url="https://example.com",
            is_active=False,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_id(provider.id)

            assert found is not None
            assert found.description == "A fully populated provider"
            assert found.logo_url == "https://example.com/logo.png"
            assert found.website_url == "https://example.com"
            assert found.is_active is False

    @pytest.mark.asyncio
    async def test_save_updates_existing_provider(self, test_database):
        """Test updating an existing provider."""
        # Arrange
        provider = create_test_provider(
            slug="test-update",
            name="Original Name",
            is_active=True,
        )

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Act - Update the provider
        provider.name = "Updated Name"
        provider.is_active = False
        provider.updated_at = datetime.now(UTC)

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_id(provider.id)

            assert found is not None
            assert found.name == "Updated Name"
            assert found.is_active is False


@pytest.mark.integration
class TestProviderRepositoryFindById:
    """Test ProviderRepository find_by_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_provider(self, test_database):
        """Test find_by_id returns provider when found."""
        # Arrange
        provider = create_test_provider(slug="test-findid")

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_id(provider.id)

        # Assert
        assert found is not None
        assert found.id == provider.id
        assert found.slug == "test-findid"

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_not_found(self, test_database):
        """Test find_by_id returns None for non-existent provider."""
        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_id(uuid7())

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_id_maps_credential_type(self, test_database):
        """Test find_by_id correctly maps CredentialType enum."""
        # Arrange
        provider = create_test_provider(
            slug="test-credtype",
            credential_type=CredentialType.API_KEY,
        )

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_id(provider.id)

        # Assert
        assert found is not None
        assert isinstance(found.credential_type, CredentialType)
        assert found.credential_type == CredentialType.API_KEY


@pytest.mark.integration
class TestProviderRepositoryFindBySlug:
    """Test ProviderRepository find_by_slug operations."""

    @pytest.mark.asyncio
    async def test_find_by_slug_returns_provider(self, test_database):
        """Test find_by_slug returns provider when found."""
        # Arrange
        provider = create_test_provider(slug="test-slugfind")

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_slug("test-slugfind")

        # Assert
        assert found is not None
        assert found.slug == "test-slugfind"

    @pytest.mark.asyncio
    async def test_find_by_slug_returns_none_when_not_found(self, test_database):
        """Test find_by_slug returns None for non-existent slug."""
        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found = await repo.find_by_slug("nonexistent-provider")

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_slug_is_case_sensitive(self, test_database):
        """Test that find_by_slug is case sensitive."""
        # Arrange
        provider = create_test_provider(slug="test-casesensitive")

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Act - Try with different case
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            found_lower = await repo.find_by_slug("test-casesensitive")
            found_upper = await repo.find_by_slug("TEST-CASESENSITIVE")

        # Assert
        assert found_lower is not None
        assert found_upper is None  # Not found because case matters


@pytest.mark.integration
class TestProviderRepositoryListAll:
    """Test ProviderRepository list_all operations."""

    @pytest.mark.asyncio
    async def test_list_all_returns_providers(self, test_database):
        """Test list_all returns all providers including seeded ones."""
        # Arrange - Add test providers
        p1 = create_test_provider(slug="test-listall1", name="ZZZ Last")
        p2 = create_test_provider(slug="test-listall2", name="AAA First")

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(p1)
            await repo.save(p2)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            providers = await repo.list_all()

        # Assert - Should include seeded schwab + our test providers
        slugs = {p.slug for p in providers}
        assert "schwab" in slugs  # Seeded provider
        assert "test-listall1" in slugs
        assert "test-listall2" in slugs

    @pytest.mark.asyncio
    async def test_list_all_includes_inactive(self, test_database):
        """Test list_all returns inactive providers too."""
        # Arrange
        inactive = create_test_provider(
            slug="test-inactive",
            name="Inactive Provider",
            is_active=False,
        )

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(inactive)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            providers = await repo.list_all()

        # Assert
        inactive_provider = next(
            (p for p in providers if p.slug == "test-inactive"), None
        )
        assert inactive_provider is not None
        assert inactive_provider.is_active is False

    @pytest.mark.asyncio
    async def test_list_all_ordered_by_name(self, test_database):
        """Test list_all returns providers ordered by name."""
        # Arrange - Add providers with different names
        p1 = create_test_provider(slug="test-order1", name="ZZZZ")
        p2 = create_test_provider(slug="test-order2", name="AAAA")

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(p1)
            await repo.save(p2)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            providers = await repo.list_all()

        # Assert - AAAA should come before ZZZZ
        names = [p.name for p in providers]
        aaaa_idx = names.index("AAAA")
        zzzz_idx = names.index("ZZZZ")
        assert aaaa_idx < zzzz_idx


@pytest.mark.integration
class TestProviderRepositoryListActive:
    """Test ProviderRepository list_active operations."""

    @pytest.mark.asyncio
    async def test_list_active_returns_only_active(self, test_database):
        """Test list_active excludes inactive providers."""
        # Arrange
        active = create_test_provider(
            slug="test-active",
            name="Active Provider",
            is_active=True,
        )
        inactive = create_test_provider(
            slug="test-inactive-list",
            name="Inactive Provider",
            is_active=False,
        )

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(active)
            await repo.save(inactive)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            providers = await repo.list_active()

        # Assert
        slugs = {p.slug for p in providers}
        assert "test-active" in slugs
        assert "test-inactive-list" not in slugs
        # All returned providers should be active
        for provider in providers:
            assert provider.is_active is True

    @pytest.mark.asyncio
    async def test_list_active_ordered_by_name(self, test_database):
        """Test list_active returns providers ordered by name."""
        # Arrange
        p1 = create_test_provider(slug="test-activeord1", name="ZActive")
        p2 = create_test_provider(slug="test-activeord2", name="AActive")

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(p1)
            await repo.save(p2)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            providers = await repo.list_active()

        # Assert
        test_providers = [p for p in providers if p.slug.startswith("test-")]
        names = [p.name for p in test_providers]
        assert names == sorted(names)


@pytest.mark.integration
class TestProviderRepositoryExistsBySlug:
    """Test ProviderRepository exists_by_slug operations."""

    @pytest.mark.asyncio
    async def test_exists_by_slug_returns_true_when_exists(self, test_database):
        """Test exists_by_slug returns True for existing provider."""
        # Arrange
        provider = create_test_provider(slug="test-exists")

        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            await repo.save(provider)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            exists = await repo.exists_by_slug("test-exists")

        # Assert
        assert exists is True

    @pytest.mark.asyncio
    async def test_exists_by_slug_returns_false_when_not_exists(self, test_database):
        """Test exists_by_slug returns False for non-existent provider."""
        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            exists = await repo.exists_by_slug("nonexistent-slug")

        # Assert
        assert exists is False

    @pytest.mark.asyncio
    async def test_exists_by_slug_for_seeded_provider(self, test_database):
        """Test exists_by_slug returns True for seeded Schwab provider."""
        # Act
        async with test_database.get_session() as session:
            repo = ProviderRepository(session=session)
            exists = await repo.exists_by_slug("schwab")

        # Assert
        assert exists is True


@pytest.mark.integration
class TestProviderRepositoryCredentialTypeMapping:
    """Test credential type enum mapping between domain and model."""

    @pytest.mark.asyncio
    async def test_all_credential_types_persist_correctly(self, test_database):
        """Test all CredentialType enum values work correctly."""
        for cred_type in CredentialType:
            provider = create_test_provider(
                slug=f"test-cred-{cred_type.value}",
                name=f"Provider for {cred_type.value}",
                credential_type=cred_type,
            )

            async with test_database.get_session() as session:
                repo = ProviderRepository(session=session)
                await repo.save(provider)
                await session.commit()

            async with test_database.get_session() as session:
                repo = ProviderRepository(session=session)
                found = await repo.find_by_id(provider.id)

                assert found is not None
                assert found.credential_type == cred_type
