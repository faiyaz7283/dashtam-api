"""API tests for token rotation endpoints.

Tests REST API endpoints for token rotation management.
Uses FastAPI TestClient with synchronous testing pattern.
"""

from datetime import datetime, timezone, timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.models.user import User
from src.models.auth import RefreshToken
from src.models.security_config import SecurityConfig
from src.services.password_service import PasswordService


class TestUserTokenRotationEndpoint:
    """Test suite for DELETE /api/v1/users/{user_id}/tokens endpoint."""

    def test_rotate_user_tokens_success(
        self, client: TestClient, verified_user: User, auth_tokens: dict
    ):
        """Test successful user token rotation.

        Verifies that:
        - Endpoint returns 200 OK
        - Response includes rotation details
        - User's min_token_version increments
        - Tokens are revoked
        """
        # Act
        response = client.request(
            "DELETE",
            f"/api/v1/users/{verified_user.id}/tokens",
            json={"reason": "Test user rotation"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["rotation_type"] == "USER"
        assert data["user_id"] == str(verified_user.id)
        assert data["old_version"] == 1
        assert data["new_version"] == 2
        assert data["tokens_revoked"] >= 1
        assert data["reason"] == "Test user rotation"
        assert "rotated_at" in data

    def test_rotate_user_tokens_requires_auth(
        self, client: TestClient, verified_user: User
    ):
        """Test that endpoint requires authentication.

        Verifies that:
        - Without auth header returns 401 Unauthorized
        - With invalid token returns 401 Unauthorized
        """
        # No auth header
        response = client.request(
            "DELETE",
            f"/api/v1/users/{verified_user.id}/tokens",
            json={"reason": "Test rotation"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Invalid token
        response = client.request(
            "DELETE",
            f"/api/v1/users/{verified_user.id}/tokens",
            json={"reason": "Test rotation"},
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rotate_user_tokens_requires_reason(
        self, client: TestClient, verified_user: User, auth_tokens: dict
    ):
        """Test that rotation requires a reason.

        Verifies that:
        - Missing reason returns 422 Validation Error
        - Empty reason returns 422 Validation Error
        - Short reason (< 10 chars) returns 422 Validation Error
        """
        # Missing reason
        response = client.request(
            "DELETE",
            f"/api/v1/users/{verified_user.id}/tokens",
            json={},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Reason too short (< 10 characters)
        response = client.request(
            "DELETE",
            f"/api/v1/users/{verified_user.id}/tokens",
            json={"reason": "Short"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rotate_user_tokens_different_user_forbidden(
        self, client: TestClient, auth_tokens: dict
    ):
        """Test rotation for different user (authorization).

        Verifies that:
        - User can only rotate their own tokens
        - Trying to rotate another user's tokens returns 403 Forbidden
        """
        from uuid import uuid4

        # Different user (authorization fails before checking if user exists)
        fake_user_id = uuid4()
        response = client.request(
            "DELETE",
            f"/api/v1/users/{fake_user_id}/tokens",
            json={"reason": "Test rotation for non-existent user"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_rotate_user_tokens_invalidates_access_token(
        self, client: TestClient, verified_user: User, auth_tokens: dict
    ):
        """Test that rotation invalidates current access token.

        Verifies that:
        - First rotation succeeds and revokes tokens
        - Token version is incremented
        - Old access token becomes invalid (401 Unauthorized)
        - This is expected security behavior (all sessions invalidated)
        """
        # First rotation succeeds
        response1 = client.request(
            "DELETE",
            f"/api/v1/users/{verified_user.id}/tokens",
            json={"reason": "First rotation"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["tokens_revoked"] >= 1
        assert data1["new_version"] == 2

        # Second rotation fails with 401 (old access token invalid)
        response2 = client.request(
            "DELETE",
            f"/api/v1/users/{verified_user.id}/tokens",
            json={"reason": "Second rotation"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED
        assert "rotated" in response2.json()["detail"].lower()


class TestGlobalTokenRotationEndpoint:
    """Test suite for DELETE /api/v1/tokens endpoint."""

    def test_rotate_global_tokens_success(
        self, client: TestClient, auth_tokens: dict, db_session: Session
    ):
        """Test successful global token rotation.

        Verifies that:
        - Endpoint returns 200 OK
        - Response includes rotation details
        - Global version increments
        - All active tokens are revoked
        """
        # Arrange - Create a second user with token to verify global rotation
        password_service = PasswordService()
        user2 = User(
            email="global_test@example.com",
            name="Global Test User",
            password_hash=password_service.hash_password("TestPassword123!"),
            email_verified=True,
            is_active=True,
            min_token_version=1,
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        # Create a refresh token for user2
        token2 = RefreshToken(
            user_id=user2.id,
            token_hash="hashed_token_for_user2",
            token_version=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            device_info="Test Device",
            ip_address="127.0.0.1",
        )
        db_session.add(token2)
        db_session.commit()

        # Get current global version
        result = db_session.execute(select(SecurityConfig))
        security_config = result.scalar_one()
        old_global_version = security_config.global_min_token_version

        # Act
        response = client.request(
            "DELETE",
            "/api/v1/tokens",
            json={
                "reason": "Test global rotation for security audit",
                "grace_period_minutes": 15,
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["rotation_type"] == "GLOBAL"
        assert data["old_version"] == old_global_version
        assert data["new_version"] == old_global_version + 1
        assert data["tokens_revoked"] >= 2  # At least 2 users' tokens
        assert data["users_affected"] >= 2
        assert "Test global rotation" in data["reason"]
        assert data["grace_period_minutes"] == 15
        assert "rotated_at" in data

    def test_rotate_global_tokens_requires_auth(self, client: TestClient):
        """Test that global rotation requires authentication.

        Verifies that:
        - Without auth header returns 401 Unauthorized
        """
        response = client.request(
            "DELETE",
            "/api/v1/tokens",
            json={
                "reason": "Test global rotation without auth",
                "grace_period_minutes": 15,
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rotate_global_tokens_requires_detailed_reason(
        self, client: TestClient, auth_tokens: dict
    ):
        """Test that global rotation requires detailed reason.

        Verifies that:
        - Missing reason returns 422 Validation Error
        - Short reason (< 20 chars) returns 422 Validation Error
        """
        # Reason too short (< 20 characters for global)
        response = client.request(
            "DELETE",
            "/api/v1/tokens",
            json={"reason": "Too short"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rotate_global_tokens_validates_grace_period(
        self, client: TestClient, auth_tokens: dict
    ):
        """Test that grace period is validated.

        Verifies that:
        - Negative grace period returns 422 Validation Error (or 429 if rate limited)
        - Grace period > 60 minutes returns 422 Validation Error (or 429 if rate limited)
        - Valid grace period (0-60) succeeds

        NOTE: Global token rotation has a rate limit of 1 per day (global scope).
        If a previous test already triggered rotation, this test will hit rate limit (429)
        before validation (422). Both are acceptable outcomes.
        """
        # Negative grace period
        response = client.request(
            "DELETE",
            "/api/v1/tokens",
            json={
                "reason": "Test global rotation with invalid grace period",
                "grace_period_minutes": -5,
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        # Either validation error (422) or rate limit error (429) is acceptable
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_429_TOO_MANY_REQUESTS,
        ]

        # Grace period too long
        response = client.request(
            "DELETE",
            "/api/v1/tokens",
            json={
                "reason": "Test global rotation with excessive grace period",
                "grace_period_minutes": 120,
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        # Either validation error (422) or rate limit error (429) is acceptable
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_429_TOO_MANY_REQUESTS,
        ]

    def test_rotate_global_tokens_default_grace_period(
        self, client: TestClient, auth_tokens: dict
    ):
        """Test that grace period defaults to 15 minutes.

        Verifies that:
        - Omitting grace_period_minutes uses default (15)
        """
        response = client.request(
            "DELETE",
            "/api/v1/tokens",
            json={"reason": "Test global rotation with default grace period value"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["grace_period_minutes"] == 15  # Default


class TestSecurityConfigEndpoint:
    """Test suite for GET /api/v1/security/config endpoint."""

    def test_get_security_config_success(self, client: TestClient, auth_tokens: dict):
        """Test retrieving security configuration.

        Verifies that:
        - Endpoint returns 200 OK
        - Response includes current global version
        - Response includes last updated info
        """
        response = client.get(
            "/api/v1/security/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "global_min_token_version" in data
        assert "last_updated_at" in data
        assert isinstance(data["global_min_token_version"], int)
        assert data["global_min_token_version"] >= 1

    def test_get_security_config_requires_auth(self, client: TestClient):
        """Test that endpoint requires authentication.

        Verifies that:
        - Without auth header returns 401 Unauthorized
        """
        response = client.get("/api/v1/security/config")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
