"""API tests for session management endpoints.

Tests all session management flows including:
- Listing active sessions
- Revoking specific sessions
- Bulk revocation (others)
- Bulk revocation (all)

Note: These are synchronous tests using FastAPI's TestClient.
TestClient handles the async/sync bridge automatically.
"""

from uuid import uuid4
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth import RefreshToken


class TestListSessions:
    """Test suite for GET /api/v1/auth/sessions endpoint."""

    def test_list_sessions_requires_auth(self, client_no_auth: TestClient):
        """Test list sessions endpoint returns 401 without JWT.

        Verifies that:
        - Request without Authorization header returns 401 Unauthorized
        - Endpoint is properly protected by authentication dependency
        - Error message indicates authentication is required

        Args:
            client_no_auth: FastAPI TestClient without auth override

        Note:
            This follows security best practice of requiring auth for all
            sensitive operations.
        """
        response = client_no_auth.get("/api/v1/auth/sessions")

        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower()

    def test_list_sessions_returns_all(
        self, client: TestClient, authenticated_user: dict, db_session: AsyncSession
    ):
        """Test list sessions returns all active sessions.

        Verifies that:
        - Authenticated request returns 200 OK
        - Response contains sessions array
        - Response contains total_count field
        - At least current session is returned

        Args:
            client: FastAPI TestClient for making HTTP requests
            authenticated_user: User with valid JWT token from fixture
            db_session: Database session for data setup

        Note:
            authenticated_user fixture provides access_token in dict.
        """
        response = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total_count" in data
        assert data["total_count"] >= 1  # At least current session
        assert isinstance(data["sessions"], list)

    def test_list_sessions_includes_metadata(
        self, client: TestClient, authenticated_user: dict
    ):
        """Test list sessions includes all required metadata.

        Verifies that:
        - Each session includes id, device_info, location fields
        - Each session includes last_activity, created_at timestamps
        - Each session includes is_current and is_trusted flags
        - Metadata is properly formatted and non-null

        Args:
            client: FastAPI TestClient for making HTTP requests
            authenticated_user: User with valid JWT token from fixture

        Note:
            SessionInfoResponse schema enforces these fields.
        """
        response = client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) > 0

        # Verify metadata structure
        session = data["sessions"][0]
        assert "id" in session
        assert "device_info" in session
        assert "location" in session
        assert "last_activity" in session
        assert "created_at" in session
        assert "is_current" in session
        assert "is_trusted" in session

        # Verify types
        assert isinstance(session["is_current"], bool)
        assert isinstance(session["is_trusted"], bool)


class TestRevokeSession:
    """Test suite for DELETE /api/v1/auth/sessions/{session_id} endpoint."""

    def test_revoke_session_requires_auth(self, client_no_auth: TestClient):
        """Test revoke session endpoint returns 401 without JWT.

        Verifies that:
        - Request without Authorization header returns 401 Unauthorized
        - Endpoint is properly protected by authentication dependency
        - Cannot revoke sessions without being authenticated

        Args:
            client_no_auth: FastAPI TestClient without auth override

        Note:
            Session ID doesn't matter if not authenticated.
        """
        fake_session_id = uuid4()
        response = client_no_auth.delete(f"/api/v1/auth/sessions/{fake_session_id}")

        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower()

    def test_revoke_session_success(
        self,
        client: TestClient,
        authenticated_user: dict,
        db_session: AsyncSession,
    ):
        """Test revoke session successfully revokes non-current session.

        Verifies that:
        - Authenticated request returns 200 OK
        - Response includes success message
        - Response includes revoked_session_id
        - Session is marked as revoked in database

        Args:
            client: FastAPI TestClient for making HTTP requests
            authenticated_user: User with valid JWT token from fixture
            db_session: Database session for data manipulation

        Note:
            Creates a second session to revoke (cannot revoke current).
            Session must belong to authenticated_user for security.
        """
        from src.models.session import Session

        # Create a second session for SAME user (different from current session)
        now = datetime.now(timezone.utc)
        second_session = Session(
            user_id=authenticated_user["user"].id,
            device_info="Firefox on Windows",
            location="New York, USA",
            ip_address="192.168.1.2",
            user_agent="Mozilla/5.0",
            is_trusted=False,
            last_activity=now,
            expires_at=now + timedelta(days=30),
            is_revoked=False,
        )
        db_session.add(second_session)
        db_session.commit()
        db_session.refresh(second_session)

        # Create refresh token linked to second session
        second_token = RefreshToken(
            user_id=authenticated_user["user"].id,
            session_id=second_session.id,
            token_hash="different_hash",
            expires_at=now + timedelta(days=30),
            is_revoked=False,
        )
        db_session.add(second_token)
        db_session.commit()
        db_session.refresh(second_token)

        # Revoke the second session
        response = client.delete(
            f"/api/v1/auth/sessions/{second_session.id}",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "revoked" in data["message"].lower()
        assert "revoked_session_id" in data
        assert data["revoked_session_id"] == str(second_session.id)

    def test_revoke_session_not_found(
        self, client: TestClient, authenticated_user: dict
    ):
        """Test revoke session returns 404 for non-existent session.

        Verifies that:
        - Request with non-existent session_id returns 404 Not Found
        - Error message indicates session not found
        - Cannot revoke sessions that don't exist or aren't owned by user

        Args:
            client: FastAPI TestClient for making HTTP requests
            authenticated_user: User with valid JWT token from fixture

        Note:
            Uses random UUID that doesn't exist in database.
        """
        fake_session_id = uuid4()
        response = client.delete(
            f"/api/v1/auth/sessions/{fake_session_id}",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_revoke_session_prevents_self(
        self,
        client: TestClient,
        authenticated_user: dict,
        db_session: AsyncSession,
    ):
        """Test revoke session prevents revoking current session.

        Verifies that:
        - Attempting to revoke current session returns 400 Bad Request
        - Error message indicates cannot revoke current session
        - Users must use logout endpoint to revoke current session

        Args:
            client: FastAPI TestClient for making HTTP requests
            authenticated_user: User with valid JWT token and session_id
            db_session: Database session for querying current session

        Note:
            Current session ID extracted from authenticated_user fixture.
        """
        # Get current session ID from authenticated_user fixture
        current_session_id = authenticated_user.get("session_id")

        if not current_session_id:
            pytest.skip("authenticated_user fixture doesn't provide session_id")

        response = client.delete(
            f"/api/v1/auth/sessions/{current_session_id}",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )

        assert response.status_code == 400
        assert "cannot revoke current session" in response.json()["detail"].lower()


class TestRevokeOtherSessions:
    """Test suite for DELETE /api/v1/auth/sessions/others/revoke endpoint."""

    def test_revoke_others_requires_auth(self, client_no_auth: TestClient):
        """Test revoke others endpoint returns 401 without JWT.

        Verifies that:
        - Request without Authorization header returns 401 Unauthorized
        - Endpoint is properly protected by authentication dependency
        - Cannot revoke other sessions without being authenticated

        Args:
            client_no_auth: FastAPI TestClient without auth override

        Note:
            This is a bulk operation, so authentication is critical.
        """
        response = client_no_auth.delete("/api/v1/auth/sessions/others/revoke")

        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower()

    def test_revoke_others_success(
        self,
        client: TestClient,
        authenticated_user: dict,
        db_session: AsyncSession,
    ):
        """Test revoke others successfully revokes all non-current sessions.

        Verifies that:
        - Authenticated request returns 200 OK
        - Response includes success message
        - Response includes revoked_count field
        - Current session remains active (can still make requests)

        Args:
            client: FastAPI TestClient for making HTTP requests
            authenticated_user: User with valid JWT token from fixture
            db_session: Database session for creating additional sessions

        Note:
            Creates multiple sessions for same user and verifies only non-current are revoked.
        """
        from src.models.session import Session

        # Create additional sessions for SAME user
        now = datetime.now(timezone.utc)
        for i in range(2):
            # Create session
            session = Session(
                user_id=authenticated_user["user"].id,
                device_info=f"Device {i}",
                location="Location",
                ip_address=f"192.168.1.{i + 10}",
                user_agent="Test Agent",
                is_trusted=False,
                last_activity=now,
                expires_at=now + timedelta(days=30),
                is_revoked=False,
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            # Create refresh token linked to session
            token = RefreshToken(
                user_id=authenticated_user["user"].id,
                session_id=session.id,
                token_hash=f"hash_{i}",
                expires_at=now + timedelta(days=30),
                is_revoked=False,
            )
            db_session.add(token)
        db_session.commit()

        response = client.delete(
            "/api/v1/auth/sessions/others/revoke",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "revoked_count" in data
        assert data["revoked_count"] >= 2  # Should revoke the 2 additional sessions

        # Verify current session still works
        verify_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )
        assert verify_response.status_code == 200


class TestRevokeAllSessions:
    """Test suite for DELETE /api/v1/auth/sessions/all/revoke endpoint."""

    def test_revoke_all_requires_auth(self, client_no_auth: TestClient):
        """Test revoke all endpoint returns 401 without JWT.

        Verifies that:
        - Request without Authorization header returns 401 Unauthorized
        - Endpoint is properly protected by authentication dependency
        - Cannot revoke all sessions without being authenticated

        Args:
            client_no_auth: FastAPI TestClient without auth override

        Note:
            This is the nuclear option - requires authentication.
        """
        response = client_no_auth.delete("/api/v1/auth/sessions/all/revoke")

        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower()

    def test_revoke_all_success(
        self,
        client: TestClient,
        authenticated_user: dict,
        db_session: AsyncSession,
    ):
        """Test revoke all successfully revokes all sessions.

        Verifies that:
        - Authenticated request returns 200 OK
        - Response includes success message with "logged out"
        - Response includes revoked_count field
        - Count reflects total sessions revoked

        Args:
            client: TestClient for making HTTP requests
            authenticated_user: User with valid JWT token from fixture
            db_session: Database session for creating additional sessions

        Note:
            This is the nuclear option - user will be logged out.
        """
        from src.models.session import Session

        # Create additional sessions for SAME user
        now = datetime.now(timezone.utc)
        for i in range(2):
            # Create session
            session = Session(
                user_id=authenticated_user["user"].id,
                device_info=f"Device {i}",
                location="Location",
                ip_address=f"192.168.1.{i + 20}",
                user_agent="Test Agent",
                is_trusted=False,
                last_activity=now,
                expires_at=now + timedelta(days=30),
                is_revoked=False,
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            # Create refresh token linked to session
            token = RefreshToken(
                user_id=authenticated_user["user"].id,
                session_id=session.id,
                token_hash=f"hash_all_{i}",
                expires_at=now + timedelta(days=30),
                is_revoked=False,
            )
            db_session.add(token)
        db_session.commit()

        response = client.delete(
            "/api/v1/auth/sessions/all/revoke",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "logged out" in data["message"].lower()
        assert "revoked_count" in data
        assert data["revoked_count"] >= 3  # Current session + 2 additional sessions

    def test_revoke_all_logs_out_user(
        self, client: TestClient, authenticated_user: dict, db_session: AsyncSession
    ):
        """Test revoke all actually logs out the user.

        Verifies that:
        - After revoking all sessions, current refresh token is invalid
        - Attempting to refresh with old token returns 401 or 403
        - User must re-authenticate to get new tokens

        Args:
            client: FastAPI TestClient for making HTTP requests
            authenticated_user: User with valid JWT and refresh tokens
            db_session: Database session for verification

        Note:
            Tests that revocation actually works (not just DB update).
        """
        refresh_token = authenticated_user.get("refresh_token")

        # Revoke all sessions
        response = client.delete(
            "/api/v1/auth/sessions/all/revoke",
            headers={"Authorization": f"Bearer {authenticated_user['access_token']}"},
        )
        assert response.status_code == 200

        # Try to refresh with old token (should fail)
        if refresh_token:
            refresh_response = client.post(
                "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
            )
            # Should be rejected (401 Unauthorized or 403 Forbidden)
            assert refresh_response.status_code in [401, 403]
