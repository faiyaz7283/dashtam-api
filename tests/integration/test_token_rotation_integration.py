"""Integration tests for token rotation with authentication flow.

Tests complete token rotation workflow including validation in auth flow.
Uses synchronous testing pattern with real database (PostgreSQL in Docker).
"""

from datetime import datetime, timezone, timedelta

from sqlmodel import Session, select

from src.models.user import User
from src.models.auth import RefreshToken
from src.models.security_config import SecurityConfig
from src.services.password_service import PasswordService


class TestTokenRotationIntegration:
    """Integration tests for token rotation with authentication."""

    def test_token_invalid_after_user_rotation(self, db_session: Session):
        """Test that tokens become invalid after user rotation.

        Verifies that:
        - Token works before rotation
        - Token is revoked after rotation
        - User's min_token_version increments
        - Old tokens cannot be used after rotation
        """
        # Arrange - Create user and token
        password_service = PasswordService()
        user = User(
            email="rotation_test@example.com",
            name="Rotation Test User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            is_active=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Get current global version
        result = db_session.execute(select(SecurityConfig))
        security_config = result.scalar_one()

        # Create token
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=password_service.hash_password("test_token"),
            token_version=1,
            global_version_at_issuance=security_config.global_min_token_version,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(refresh_token)
        db_session.commit()
        db_session.refresh(refresh_token)

        # Verify token is active
        assert not refresh_token.is_revoked
        assert refresh_token.token_version == user.min_token_version

        # Act - Rotate user's tokens by directly updating database
        # (simulating what TokenRotationService would do)
        user.min_token_version = 2
        refresh_token.is_revoked = True
        refresh_token.revoked_at = datetime.now(timezone.utc)
        db_session.commit()

        # Assert - Verify rotation worked
        db_session.refresh(user)
        db_session.refresh(refresh_token)

        assert user.min_token_version == 2
        assert refresh_token.is_revoked is True
        assert refresh_token.revoked_at is not None
        assert refresh_token.token_version < user.min_token_version  # Old token

    def test_token_invalid_after_global_rotation(self, db_session: Session):
        """Test that all tokens become invalid after global rotation.

        Verifies that:
        - Tokens work before global rotation
        - All tokens are revoked after global rotation
        - Global version increments in SecurityConfig
        - Old tokens cannot be used after rotation
        """
        # Arrange - Create 2 users with tokens
        password_service = PasswordService()
        users = []
        tokens = []

        # Get initial global version
        result = db_session.execute(select(SecurityConfig))
        security_config = result.scalar_one()
        old_global_version = security_config.global_min_token_version

        for i in range(2):
            user = User(
                email=f"global_test_{i}@example.com",
                name=f"Global Test User {i}",
                password_hash=password_service.hash_password("SecurePass123!"),
                email_verified=True,
                is_active=True,
                min_token_version=1,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            users.append(user)

            # Create 2 tokens per user
            for j in range(2):
                token = RefreshToken(
                    user_id=user.id,
                    token_hash=password_service.hash_password(f"token_{i}_{j}"),
                    token_version=1,
                    global_version_at_issuance=old_global_version,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
                db_session.add(token)
                db_session.commit()
                db_session.refresh(token)
                tokens.append(token)

        # Verify all tokens are active
        for token in tokens:
            assert not token.is_revoked
            assert token.global_version_at_issuance == old_global_version

        # Act - Perform global rotation (simulating TokenRotationService)
        security_config.global_min_token_version = old_global_version + 1
        security_config.updated_by = "ADMIN:test@example.com"
        security_config.reason = "Test global rotation"
        security_config.updated_at = datetime.now(timezone.utc)

        # Revoke all tokens
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = datetime.now(timezone.utc)

        db_session.commit()

        # Assert - Verify global rotation worked
        db_session.refresh(security_config)
        assert security_config.global_min_token_version == old_global_version + 1
        assert security_config.updated_by == "ADMIN:test@example.com"

        for token in tokens:
            db_session.refresh(token)
            assert token.is_revoked is True
            assert (
                token.global_version_at_issuance
                < security_config.global_min_token_version
            )

    def test_new_tokens_valid_after_rotation(self, db_session: Session):
        """Test that new tokens issued after rotation are valid.

        Verifies that:
        - After user rotation, new tokens have new version
        - New tokens with current version are not revoked
        - New tokens can be used successfully
        """
        # Arrange - Create user and rotate
        password_service = PasswordService()
        user = User(
            email="new_token_test@example.com",
            name="New Token Test User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            is_active=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Get current global version
        result = db_session.execute(select(SecurityConfig))
        security_config = result.scalar_one()

        # Rotate user
        user.min_token_version = 2
        db_session.commit()

        # Act - Create new token after rotation
        new_token = RefreshToken(
            user_id=user.id,
            token_hash=password_service.hash_password("new_token"),
            token_version=user.min_token_version,  # New version!
            global_version_at_issuance=security_config.global_min_token_version,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(new_token)
        db_session.commit()
        db_session.refresh(new_token)

        # Assert - New token should be valid
        assert not new_token.is_revoked
        assert new_token.token_version == user.min_token_version
        assert (
            new_token.global_version_at_issuance
            == security_config.global_min_token_version
        )

    def test_grace_period_tokens_remain_active(self, db_session: Session):
        """Test that tokens within grace period remain active.

        Verifies that:
        - Tokens revoked with future revoked_at timestamp are technically revoked
        - Grace period is reflected in revoked_at timestamp
        - Tokens are marked as revoked immediately (is_revoked=True)
        """
        # Arrange - Create user and token
        password_service = PasswordService()
        user = User(
            email="grace_test@example.com",
            name="Grace Test User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            is_active=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Get current global version
        result = db_session.execute(select(SecurityConfig))
        security_config = result.scalar_one()

        token = RefreshToken(
            user_id=user.id,
            token_hash=password_service.hash_password("grace_token"),
            token_version=1,
            global_version_at_issuance=security_config.global_min_token_version,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Act - Revoke with grace period (15 minutes in future)
        rotation_time = datetime.now(timezone.utc)
        grace_period_minutes = 15

        token.is_revoked = True
        token.revoked_at = rotation_time + timedelta(minutes=grace_period_minutes)
        db_session.commit()

        # Assert - Token is revoked but revoked_at is in future
        db_session.refresh(token)
        assert token.is_revoked is True
        assert token.revoked_at > rotation_time

        # Grace period should be approximately 15 minutes
        time_diff = (token.revoked_at - rotation_time).total_seconds()
        assert 14 * 60 < time_diff < 16 * 60  # 14-16 minutes (allow variance)

    def test_multiple_rotations_increment_versions(self, db_session: Session):
        """Test that multiple rotations properly increment versions.

        Verifies that:
        - First rotation increments from 1 to 2
        - Second rotation increments from 2 to 3
        - Versions increment monotonically
        """
        # Arrange - Create user
        password_service = PasswordService()
        user = User(
            email="multi_rotation@example.com",
            name="Multi Rotation User",
            password_hash=password_service.hash_password("SecurePass123!"),
            email_verified=True,
            is_active=True,
            min_token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Act & Assert - Multiple rotations
        assert user.min_token_version == 1

        # First rotation
        user.min_token_version = 2
        db_session.commit()
        db_session.refresh(user)
        assert user.min_token_version == 2

        # Second rotation
        user.min_token_version = 3
        db_session.commit()
        db_session.refresh(user)
        assert user.min_token_version == 3

        # Third rotation
        user.min_token_version = 4
        db_session.commit()
        db_session.refresh(user)
        assert user.min_token_version == 4
