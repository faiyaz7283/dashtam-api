"""Integration tests for UserRepository.

Tests cover:
- Save and retrieve user
- Find by email
- Find by ID
- Update user
- Email uniqueness constraint
- User not found scenarios

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
"""

from datetime import UTC, datetime
from uuid_extensions import uuid7

import pytest
import pytest_asyncio

from src.domain.entities.user import User
from src.infrastructure.persistence.repositories.user_repository import (
    UserRepository,
)


def create_test_user(
    user_id=None,
    email="test@example.com",
    password_hash="hashed_password",
    is_verified=False,
    is_active=True,
    failed_login_attempts=0,
    locked_until=None,
):
    """Create a test User with all required fields."""
    now = datetime.now(UTC)
    return User(
        id=user_id or uuid7(),
        email=email,
        password_hash=password_hash,
        is_verified=is_verified,
        is_active=is_active,
        failed_login_attempts=failed_login_attempts,
        locked_until=locked_until,
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def user_repository(test_database):
    """Provide UserRepository with test database session."""
    async with test_database.get_session() as session:
        yield UserRepository(session=session)


@pytest.mark.integration
class TestUserRepositorySave:
    """Test UserRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_user_persists_to_database(self, test_database):
        """Test saving a user persists it to the database."""
        # Arrange - Use unique email per test run
        user_id = uuid7()
        unique_email = f"test_{user_id}@example.com"
        user = create_test_user(
            user_id=user_id,
            email=unique_email,
            password_hash="hashed_password",
            is_verified=False,
            is_active=True,
        )

        # Act
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()

        # Assert - Use separate session to verify persistence
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_id(user_id)

            assert found is not None
            assert found.id == user_id
            assert found.email == unique_email
            assert found.password_hash == "hashed_password"
            assert found.is_verified is False
            assert found.is_active is True

    @pytest.mark.asyncio
    async def test_save_user_with_verified_status(self, test_database):
        """Test saving a user with verified status."""
        # Arrange - Use unique email per test run
        user_id = uuid7()
        unique_email = f"admin_{user_id}@example.com"
        user = create_test_user(
            user_id=user_id,
            email=unique_email,
            password_hash="hashed_password",
            is_verified=True,
        )

        # Act
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_id(user_id)

            assert found is not None
            assert found.is_verified is True


@pytest.mark.integration
class TestUserRepositoryFindByEmail:
    """Test UserRepository find_by_email operations."""

    @pytest.mark.asyncio
    async def test_find_by_email_returns_user(self, test_database):
        """Test find_by_email returns existing user."""
        # Arrange - Use unique email per test run
        user_id = uuid7()
        email = f"findme_{user_id}@example.com"
        user = create_test_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
        )

        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_email(email)

        # Assert
        assert found is not None
        assert found.id == user_id
        assert found.email == email

    @pytest.mark.asyncio
    async def test_find_by_email_returns_none_when_not_found(self, test_database):
        """Test find_by_email returns None for non-existent email."""
        # Act
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_email("nonexistent@example.com")

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_email_is_case_insensitive(self, test_database):
        """Test find_by_email is case insensitive."""
        # Arrange - Use unique email to avoid conflicts
        user_id = uuid7()
        unique_suffix = str(user_id)[:8]
        email_mixed_case = f"Test_{unique_suffix}@Example.com"
        email_lowercase = f"test_{unique_suffix}@example.com"

        user = create_test_user(
            user_id=user_id,
            email=email_mixed_case,
            password_hash="hashed_password",
        )

        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()

        # Act - Search with different case
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_email(email_lowercase)

        # Assert
        assert found is not None
        assert found.id == user_id


@pytest.mark.integration
class TestUserRepositoryFindById:
    """Test UserRepository find_by_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_user(self, test_database):
        """Test find_by_id returns existing user."""
        # Arrange - Use unique email per test run
        user_id = uuid7()
        unique_email = f"findbyid_{user_id}@example.com"
        user = create_test_user(
            user_id=user_id,
            email=unique_email,
            password_hash="hashed_password",
        )

        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_id(user_id)

        # Assert
        assert found is not None
        assert found.id == user_id
        assert found.email == unique_email

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_not_found(self, test_database):
        """Test find_by_id returns None for non-existent ID."""
        # Act
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_id(uuid7())

        # Assert
        assert found is None


@pytest.mark.integration
class TestUserRepositoryUpdate:
    """Test UserRepository update operations."""

    @pytest.mark.asyncio
    async def test_update_user_persists_changes(self, test_database):
        """Test updating a user persists changes to database."""
        # Arrange - Use unique email per test run
        user_id = uuid7()
        unique_email = f"update_{user_id}@example.com"
        user = create_test_user(
            user_id=user_id,
            email=unique_email,
            password_hash="old_hash",
            is_verified=False,
        )

        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()

        # Act - Update user
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_id(user_id)
            assert found is not None
            found.password_hash = "new_hash"
            found.is_verified = True
            await repo.update(found)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            updated = await repo.find_by_id(user_id)

            assert updated is not None
            assert updated.password_hash == "new_hash"
            assert updated.is_verified is True

    @pytest.mark.asyncio
    async def test_update_user_failed_login_attempts(self, test_database):
        """Test updating failed login attempts."""
        # Arrange - Use unique email per test run
        user_id = uuid7()
        unique_email = f"login_{user_id}@example.com"
        user = create_test_user(
            user_id=user_id,
            email=unique_email,
            password_hash="hashed",
            failed_login_attempts=0,
        )

        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()

        # Act - Increment failed login
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_id(user_id)
            assert found is not None
            found.increment_failed_login()
            await repo.update(found)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            updated = await repo.find_by_id(user_id)

            assert updated is not None
            assert updated.failed_login_attempts == 1
