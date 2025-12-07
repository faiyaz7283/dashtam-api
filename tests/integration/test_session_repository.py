"""Integration tests for SessionRepository.

Tests cover:
- Save and retrieve session
- Find by ID, user_id, refresh_token_id
- Count active sessions
- Revoke single session
- Revoke all sessions for user (bulk)
- Get oldest active session (FIFO eviction)
- Delete operations
- Cleanup expired sessions

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations

Note:
    Uses clean_session_tables autouse fixture to ensure test isolation.
    Each test starts with empty sessions and users tables.
"""

from datetime import UTC, datetime
from uuid_extensions import uuid7
from freezegun import freeze_time

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.domain.entities.user import User
from src.domain.protocols.session_repository import SessionData
from src.infrastructure.persistence.repositories.session_repository import (
    SessionRepository,
)
from src.infrastructure.persistence.repositories.user_repository import (
    UserRepository,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_session_tables(test_database):
    """Clean sessions and users tables before each test.

    This fixture ensures complete test isolation by truncating
    tables that are used in these tests. Uses TRUNCATE with
    CASCADE and RESTART IDENTITY for complete cleanup.

    Note:
        autouse=True means this runs for every test in this file.
        Sessions must be deleted first due to FK constraint.
    """
    async with test_database.get_session() as db_session:
        # Delete sessions first (FK to users), then users
        await db_session.execute(text("TRUNCATE TABLE sessions CASCADE"))
        await db_session.execute(text("TRUNCATE TABLE users CASCADE"))
        await db_session.commit()
    yield
    # No cleanup needed after - next test will truncate


@freeze_time("2024-01-01 12:00:00")
def create_test_user(user_id=None, email=None):
    """Create a test User with all required fields."""
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    user_id = user_id or uuid7()
    return User(
        id=user_id,
        email=email or f"test_{user_id}@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )


@freeze_time("2024-01-01 12:00:00")
def create_test_session(
    session_id=None,
    user_id=None,
    device_info="Chrome on Windows",
    ip_address="192.168.1.1",
    location="New York, US",
    expires_at=None,
    is_revoked=False,
    created_at=None,
):
    """Create a test SessionData with all required fields.

    Args:
        session_id: Optional session UUID.
        user_id: Required user UUID.
        device_info: Device description.
        ip_address: Client IP.
        location: Geographic location.
        expires_at: Optional expiration time.
        is_revoked: Whether session is revoked.
        created_at: Optional creation time (for testing ordering).
    """
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    return SessionData(
        id=session_id or uuid7(),
        user_id=user_id or uuid7(),
        device_info=device_info,
        user_agent="Mozilla/5.0 Chrome/120.0",
        ip_address=ip_address,
        location=location,
        created_at=created_at or now,
        last_activity_at=now,
        expires_at=expires_at
        or datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC),  # 30 days later
        is_revoked=is_revoked,
        is_trusted=False,
        revoked_at=None,
        revoked_reason=None,
        refresh_token_id=None,
        last_ip_address=None,
        suspicious_activity_count=0,
        last_provider_accessed=None,
        last_provider_sync_at=None,
        providers_accessed=None,
    )


@pytest.mark.integration
class TestSessionRepositorySave:
    """Test SessionRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_session_persists_to_database(self, test_database):
        """Test saving a session persists it to the database."""
        # Arrange - Create user first (sessions require user FK)
        user = create_test_user()
        session_id = uuid7()
        session = create_test_session(session_id=session_id, user_id=user.id)

        # Save user first
        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        # Act - Save session
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(session)

        # Assert - Verify persistence
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_id(session_id)

            assert found is not None
            assert found.id == session_id
            assert found.user_id == user.id
            assert found.device_info == "Chrome on Windows"
            assert found.location == "New York, US"

    @pytest.mark.asyncio
    async def test_save_session_updates_existing(self, test_database):
        """Test saving an existing session updates it."""
        # Arrange
        user = create_test_user()
        session_id = uuid7()
        session = create_test_session(session_id=session_id, user_id=user.id)

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(session)

        # Act - Update session
        session.device_info = "Safari on macOS"
        session.location = "San Francisco, US"

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(session)

        # Assert
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_id(session_id)

            assert found.device_info == "Safari on macOS"
            assert found.location == "San Francisco, US"


@pytest.mark.integration
class TestSessionRepositoryFindByUserId:
    """Test SessionRepository find_by_user_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_user_id_returns_all_sessions(self, test_database):
        """Test find_by_user_id returns all sessions for user."""
        # Arrange
        user = create_test_user()
        sessions = [
            create_test_session(user_id=user.id, device_info="Chrome"),
            create_test_session(user_id=user.id, device_info="Safari"),
            create_test_session(user_id=user.id, device_info="Firefox"),
        ]

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            for session in sessions:
                await repo.save(session)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_user_id(user.id)

        # Assert
        assert len(found) == 3
        device_infos = {s.device_info for s in found}
        assert device_infos == {"Chrome", "Safari", "Firefox"}

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_find_by_user_id_active_only(self, test_database):
        """Test find_by_user_id with active_only filter."""
        # Arrange
        user = create_test_user()
        active_session = create_test_session(
            user_id=user.id, device_info="Active", is_revoked=False
        )
        revoked_session = create_test_session(
            user_id=user.id, device_info="Revoked", is_revoked=True
        )

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(active_session)
            await repo.save(revoked_session)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_user_id(user.id, active_only=True)

        # Assert
        assert len(found) == 1
        assert found[0].device_info == "Active"

    @pytest.mark.asyncio
    async def test_find_by_user_id_returns_empty_list(self, test_database):
        """Test find_by_user_id returns empty list when no sessions."""
        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_user_id(uuid7())

        # Assert
        assert found == []


@pytest.mark.integration
class TestSessionRepositoryCountActiveSessions:
    """Test SessionRepository count_active_sessions operations."""

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_count_active_sessions_counts_only_active(self, test_database):
        """Test count_active_sessions only counts non-revoked, non-expired."""
        # Arrange
        user = create_test_user()
        active1 = create_test_session(user_id=user.id, is_revoked=False)
        active2 = create_test_session(user_id=user.id, is_revoked=False)
        revoked = create_test_session(user_id=user.id, is_revoked=True)
        expired = create_test_session(
            user_id=user.id,
            is_revoked=False,
            expires_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC),  # 1 hour ago
        )

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(active1)
            await repo.save(active2)
            await repo.save(revoked)
            await repo.save(expired)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            count = await repo.count_active_sessions(user.id)

        # Assert
        assert count == 2


@pytest.mark.integration
class TestSessionRepositoryRevokeAll:
    """Test SessionRepository revoke_all_for_user operations."""

    @pytest.mark.asyncio
    async def test_revoke_all_revokes_all_active_sessions(self, test_database):
        """Test revoke_all_for_user revokes all active sessions."""
        # Arrange
        user = create_test_user()
        sessions = [
            create_test_session(user_id=user.id, is_revoked=False),
            create_test_session(user_id=user.id, is_revoked=False),
            create_test_session(user_id=user.id, is_revoked=False),
        ]

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            for session in sessions:
                await repo.save(session)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            revoked_count = await repo.revoke_all_for_user(
                user_id=user.id, reason="password_changed"
            )

        # Assert
        assert revoked_count == 3

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_user_id(user.id)
            for session in found:
                assert session.is_revoked is True
                assert session.revoked_reason == "password_changed"

    @pytest.mark.asyncio
    async def test_revoke_all_excludes_current_session(self, test_database):
        """Test revoke_all_for_user excludes specified session."""
        # Arrange
        user = create_test_user()
        current_session_id = uuid7()
        current_session = create_test_session(
            session_id=current_session_id, user_id=user.id
        )
        other_sessions = [
            create_test_session(user_id=user.id),
            create_test_session(user_id=user.id),
        ]

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(current_session)
            for session in other_sessions:
                await repo.save(session)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            revoked_count = await repo.revoke_all_for_user(
                user_id=user.id,
                reason="logout_everywhere",
                except_session_id=current_session_id,
            )

        # Assert
        assert revoked_count == 2

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            current = await repo.find_by_id(current_session_id)
            assert current.is_revoked is False


@pytest.mark.integration
class TestSessionRepositoryGetOldestActiveSession:
    """Test SessionRepository get_oldest_active_session operations."""

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_get_oldest_returns_oldest_by_created_at(self, test_database):
        """Test get_oldest_active_session returns oldest session."""
        # Arrange
        user = create_test_user()

        # Create sessions with different creation times using the factory parameter
        oldest = create_test_session(
            user_id=user.id,
            device_info="Oldest",
            created_at=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),  # 3 hours ago
        )
        middle = create_test_session(
            user_id=user.id,
            device_info="Middle",
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),  # 2 hours ago
        )
        newest = create_test_session(
            user_id=user.id,
            device_info="Newest",
            created_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC),  # 1 hour ago
        )

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        # Save in random order to verify sorting works
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(newest)
            await repo.save(oldest)
            await repo.save(middle)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.get_oldest_active_session(user.id)

        # Assert
        assert found is not None
        assert found.device_info == "Oldest"

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_get_oldest_excludes_revoked_sessions(self, test_database):
        """Test get_oldest_active_session excludes revoked sessions."""
        # Arrange
        user = create_test_user()

        # Oldest is revoked
        oldest_revoked = create_test_session(
            user_id=user.id,
            device_info="OldestRevoked",
            is_revoked=True,
            created_at=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),  # 3 hours ago
        )
        # Second oldest is active
        oldest_active = create_test_session(
            user_id=user.id,
            device_info="OldestActive",
            is_revoked=False,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),  # 2 hours ago
        )

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(oldest_revoked)
            await repo.save(oldest_active)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.get_oldest_active_session(user.id)

        # Assert
        assert found is not None
        assert found.device_info == "OldestActive"


@pytest.mark.integration
class TestSessionRepositoryDelete:
    """Test SessionRepository delete operations."""

    @pytest.mark.asyncio
    async def test_delete_removes_session(self, test_database):
        """Test delete removes session from database."""
        # Arrange
        user = create_test_user()
        session_id = uuid7()
        session = create_test_session(session_id=session_id, user_id=user.id)

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(session)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            deleted = await repo.delete(session_id)

        # Assert
        assert deleted is True

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_id(session_id)
            assert found is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, test_database):
        """Test delete returns False when session doesn't exist."""
        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            deleted = await repo.delete(uuid7())

        # Assert
        assert deleted is False


@pytest.mark.integration
class TestSessionRepositoryCleanup:
    """Test SessionRepository cleanup operations."""

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_cleanup_removes_expired_sessions(self, test_database):
        """Test cleanup_expired_sessions removes old sessions."""
        # Arrange
        user = create_test_user()

        expired = create_test_session(
            user_id=user.id,
            device_info="Expired",
            expires_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC),  # 1 hour ago
        )
        active = create_test_session(
            user_id=user.id,
            device_info="Active",
            expires_at=datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC),  # 30 days later
        )

        async with test_database.get_session() as db_session:
            user_repo = UserRepository(session=db_session)
            await user_repo.save(user)
            await db_session.commit()

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            await repo.save(expired)
            await repo.save(active)

        # Act
        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            cleaned_count = await repo.cleanup_expired_sessions()

        # Assert
        assert cleaned_count == 1

        async with test_database.get_session() as db_session:
            repo = SessionRepository(session=db_session)
            found = await repo.find_by_user_id(user.id, active_only=False)
            assert len(found) == 1
            assert found[0].device_info == "Active"
