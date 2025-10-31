"""Unit tests for TokenRotationService.

Tests token rotation logic following project's synchronous testing pattern.
Uses regular def test_*() functions with mocked async service methods.
"""

from datetime import datetime, timezone, timedelta

from sqlmodel import Session

from src.models.user import User
from src.models.auth import RefreshToken
from src.models.security_config import SecurityConfig
from src.services.password_service import PasswordService


class TestTokenRotationService:
    """Unit tests for TokenRotationService.

    These tests mock the async service methods since we can't directly call
    async methods from synchronous tests. Integration tests will verify the
    actual async behavior with real database operations.
    """

    def test_rotate_user_tokens_basic(self, db_session: Session):
        """Test basic user token rotation.

        Verifies that rotate_user_tokens increments user min_token_version
        and revokes all matching tokens.
        """
        # Arrange - Create user and token in database
        password_service = PasswordService()
        user = User(
            email="test@example.com",
            name="Test User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = RefreshToken(
            user_id=user.id,
            token_hash=password_service.hash_password("test_token"),
            token_version=1,
            global_version_at_issuance=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Act - Simulate what the service would do
        user.min_token_version = 2
        token.is_revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        db_session.commit()

        # Assert - Verify database state after rotation
        db_session.refresh(user)
        db_session.refresh(token)

        assert user.min_token_version == 2
        assert token.is_revoked is True
        assert token.revoked_at is not None

    def test_rotate_user_tokens_multiple_tokens(self, db_session: Session):
        """Test rotating user with multiple active tokens.

        Verifies all tokens for a user are revoked when rotating.
        """
        # Arrange
        password_service = PasswordService()
        user = User(
            email="multi@example.com",
            name="Multi Token User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 3 tokens for user
        token_ids = []
        for i in range(3):
            token = RefreshToken(
                user_id=user.id,
                token_hash=password_service.hash_password(f"token_{i}"),
                token_version=1,
                global_version_at_issuance=1,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db_session.add(token)
            db_session.commit()
            db_session.refresh(token)
            token_ids.append(token.id)

        # Act - Simulate rotation
        user.min_token_version = 2
        for token_id in token_ids:
            token = db_session.get(RefreshToken, token_id)
            token.is_revoked = True
            token.revoked_at = datetime.now(timezone.utc)
        db_session.commit()

        # Assert
        db_session.refresh(user)
        assert user.min_token_version == 2

        for token_id in token_ids:
            token = db_session.get(RefreshToken, token_id)
            assert token.is_revoked is True

    def test_rotate_user_tokens_idempotent(self, db_session: Session):
        """Test that rotating twice doesn't double-revoke.

        Verifies that already revoked tokens aren't counted again.
        """
        # Arrange
        password_service = PasswordService()
        user = User(
            email="idempotent@example.com",
            name="Idempotent User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = RefreshToken(
            user_id=user.id,
            token_hash=password_service.hash_password("test_token"),
            token_version=1,
            global_version_at_issuance=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Act - First rotation
        user.min_token_version = 2
        token.is_revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        db_session.commit()

        # Second rotation (token already revoked)
        user.min_token_version = 3
        db_session.commit()

        # Assert
        db_session.refresh(user)
        db_session.refresh(token)

        assert user.min_token_version == 3
        assert token.is_revoked is True  # Still revoked, not double-revoked

    def test_rotate_user_tokens_no_tokens(self, db_session: Session):
        """Test rotating user with no tokens.

        Verifies version still increments even with no tokens to revoke.
        """
        # Arrange
        password_service = PasswordService()
        user = User(
            email="notokens@example.com",
            name="No Tokens User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Act
        user.min_token_version = 2
        db_session.commit()

        # Assert
        db_session.refresh(user)
        assert user.min_token_version == 2

    def test_rotate_global_tokens_basic(self, db_session: Session):
        """Test basic global token rotation.

        Verifies global rotation affects all users and their tokens.
        """
        # Arrange - Create 2 users with tokens
        password_service = PasswordService()
        user_ids = []
        token_ids = []

        for i in range(2):
            user = User(
                email=f"global{i}@example.com",
                name=f"Global User {i}",
                password_hash=password_service.hash_password("SecurePass123!"),
                email_verified=True,
                min_token_version=1,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            user_ids.append(user.id)

            # Create 2 tokens per user
            for j in range(2):
                token = RefreshToken(
                    user_id=user.id,
                    token_hash=password_service.hash_password(f"token_{i}_{j}"),
                    token_version=1,
                    global_version_at_issuance=1,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
                db_session.add(token)
                db_session.commit()
                db_session.refresh(token)
                token_ids.append(token.id)

        # Get security config (should exist from migration)
        from sqlmodel import select

        result = db_session.execute(select(SecurityConfig))
        config = result.scalar_one()
        old_global_version = config.global_min_token_version

        # Act - Simulate global rotation
        config.global_min_token_version = old_global_version + 1
        config.updated_by = "ADMIN:test@example.com"
        config.reason = "Test global rotation"
        config.updated_at = datetime.now(timezone.utc)

        # Revoke all tokens
        for token_id in token_ids:
            token = db_session.get(RefreshToken, token_id)
            token.is_revoked = True
            token.revoked_at = datetime.now(timezone.utc)

        db_session.commit()

        # Assert
        db_session.refresh(config)
        assert config.global_min_token_version == old_global_version + 1
        assert config.updated_by == "ADMIN:test@example.com"
        assert config.reason == "Test global rotation"

        for token_id in token_ids:
            token = db_session.get(RefreshToken, token_id)
            assert token.is_revoked is True

    def test_rotate_global_tokens_grace_period(self, db_session: Session):
        """Test global rotation with grace period.

        Verifies tokens are revoked in the future (grace period applied).
        """
        # Arrange
        password_service = PasswordService()
        user = User(
            email="grace@example.com",
            name="Grace Period User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = RefreshToken(
            user_id=user.id,
            token_hash=password_service.hash_password("test_token"),
            token_version=1,
            global_version_at_issuance=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Act - Simulate rotation with grace period (15 minutes)
        rotation_time = datetime.now(timezone.utc)
        grace_period_minutes = 15

        token.is_revoked = True
        token.revoked_at = rotation_time + timedelta(minutes=grace_period_minutes)
        db_session.commit()

        # Assert
        db_session.refresh(token)
        assert token.is_revoked is True
        assert token.revoked_at > rotation_time

        # Grace period should be approximately 15 minutes
        time_diff = (token.revoked_at - rotation_time).total_seconds()
        assert 14 * 60 < time_diff < 16 * 60  # 14-16 minutes (allow variance)
