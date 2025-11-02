"""Unit tests for AuthService password reset delegation.

Tests that AuthService properly delegates to PasswordResetService.
The detailed password reset logic (session revocation, token validation, etc.)
is now tested in test_password_reset_service.py.

These tests verify:
- AuthService.request_password_reset() delegates to PasswordResetService.request_reset()
- AuthService.reset_password() delegates to PasswordResetService.reset_password()
- Return values are properly passed through

Note:
    After Phase 3 refactoring, password reset logic moved to PasswordResetService.
    AuthService now acts as an orchestrator that delegates to specialized services.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.models.user import User
from src.services.auth_service import AuthService


class TestAuthServicePasswordResetDelegation:
    """Test suite for AuthService password reset delegation.

    Validates that AuthService properly delegates password reset operations
    to PasswordResetService.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_password_service(self):
        """Create a mock PasswordService."""
        with patch("src.services.auth_service.PasswordService") as mock_cls:
            service = Mock()
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hashed_password",
            name="Test User",
            email_verified=True,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def mock_password_reset_service(self, sample_user):
        """Create a mock PasswordResetService for delegation testing."""
        with patch("src.services.auth_service.PasswordResetService") as mock_cls:
            service = AsyncMock()
            service.reset_password = AsyncMock(return_value=sample_user)
            service.request_reset = AsyncMock()
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def auth_service(
        self, mock_session, mock_password_service, mock_password_reset_service
    ):
        """Create AuthService with mocked dependencies."""
        return AuthService(mock_session)

    def test_reset_password_delegates_to_service(
        self, auth_service, mock_password_reset_service, sample_user
    ):
        """Test AuthService.reset_password() delegates to PasswordResetService.

        Verifies that:
        - AuthService calls PasswordResetService.reset_password()
        - Passes token, new_password, and session metadata correctly
        - Returns the user object from PasswordResetService

        Note:
            Actual password reset logic (session revocation, validation, etc.)
            is tested in test_password_reset_service.py.
        """
        # Act
        user = asyncio.run(
            auth_service.reset_password(
                token="test_token",
                new_password="NewSecurePass123!",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
            )
        )

        # Assert
        assert user is not None
        assert user.id == sample_user.id
        mock_password_reset_service.reset_password.assert_called_once_with(
            "test_token",
            "NewSecurePass123!",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

    def test_request_password_reset_delegates_to_service(
        self, auth_service, mock_password_reset_service
    ):
        """Test AuthService.request_password_reset() delegates to PasswordResetService.

        Verifies that:
        - AuthService calls PasswordResetService.request_reset()
        - Passes email correctly
        """
        # Act
        asyncio.run(auth_service.request_password_reset("user@example.com"))

        # Assert
        mock_password_reset_service.request_reset.assert_called_once_with(
            "user@example.com"
        )
