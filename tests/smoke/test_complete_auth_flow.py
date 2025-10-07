"""
Smoke Test: Complete Authentication Flow

This smoke test validates the critical path through the entire authentication
system from registration to logout, ensuring the system is operational and
ready for deployment.

This test represents a real user journey through the authentication system:
Registration → Email Verification → Login → Profile Management → Token Refresh
→ Password Reset → Login with New Password → Logout

Duration: ~3-5 seconds
Test Count: 1 comprehensive sequential test + 4 independent validation tests
Test Coverage: 18 assertions across complete auth lifecycle

Replaces: scripts/test-api-flows.sh (deprecated shell script)
Documentation: docs/api-flows/auth/complete-auth-flow.md
"""

import logging
import re
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlmodel import Session


@pytest.fixture(scope="function", autouse=True)
def clean_database_for_smoke_test(db: Session, request):
    """Clean database before each smoke test to ensure predictable state.

    Smoke tests need a clean database because they use predictable data
    (like test@example.com). When running as part of full test suite,
    other tests may have created data that conflicts.

    This fixture automatically truncates ALL tables (except alembic_version)
    ensuring smoke tests always start with a clean slate, regardless of
    how the database schema evolves.

    CRITICAL: Uses session-scoped 'db' session (not function-scoped 'db_session')
    because the 'client' fixture uses 'db', and we need to expire the same
    session that the client will use.

    This fixture runs before EVERY test in this module (autouse=True).
    Since it's defined in the smoke test module, it only affects smoke tests.
    """
    import logging

    logger = logging.getLogger(__name__)

    logger.info(f"Cleaning database before smoke test: {request.node.name}")

    # Clean database before test - truncate ALL tables
    try:
        # Get all table names from database (excluding alembic_version)
        result = db.execute(
            text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename != 'alembic_version'
            """)
        )
        tables = [row[0] for row in result.fetchall()]

        if tables:
            logger.info(f"Truncating tables: {', '.join(tables)}")
            # Disable foreign key checks, truncate all tables, re-enable checks
            # RESTART IDENTITY resets auto-increment sequences
            # CASCADE handles dependent tables
            table_list = ", ".join(tables)
            db.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
            db.commit()
            # CRITICAL: Expire all session objects after truncate
            # This clears SQLAlchemy's identity map so it doesn't reference deleted rows
            db.expire_all()
            logger.info("Database cleaned successfully")
        else:
            logger.warning("No tables found to truncate")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clean database for smoke test: {e}", exc_info=True)

    yield
    # After test: smoke tests skip cleanup (handled by db_session fixture)


def extract_token_from_caplog(caplog, pattern: str) -> str:
    """Extract token from pytest captured logs.

    This uses pytest's caplog fixture to extract tokens that are logged
    by EmailService in development mode. Works in all environments without
    needing Docker CLI access.

    Args:
        caplog: pytest's caplog fixture
        pattern: String pattern to match (e.g., 'verify-email?token=' or 'reset-password?token=')

    Returns:
        Extracted token string

    Raises:
        AssertionError: If token not found in captured logs

    Example:
        >>> token = extract_token_from_caplog(caplog, "verify-email?token=")
        >>> assert len(token) > 0
    """
    # Search through captured log records
    for record in caplog.records:
        # Check if pattern exists in message
        if pattern in record.message:
            # Extract token from URL pattern like: verify-email?token=abc123
            # Pattern: token=VALUE (terminated by &, ", space, or end of line)
            # Escape the ? in the pattern for regex
            regex_pattern = pattern.replace("?", "\\?")
            match = re.search(rf"{regex_pattern}([^&\s\"]+)", record.message)
            if match:
                return match.group(1)

    raise AssertionError(
        f"Token not found in captured logs (pattern: {pattern}). "
        f"Ensure email service is logging tokens in development mode."
    )


def test_complete_authentication_flow(client, caplog):
    """
    Smoke Test: Complete user authentication journey.

    This test validates the critical path through the authentication system,
    ensuring all core functionality works end-to-end. It represents a real
    user's journey from registration to logout.

    Test Steps (18 assertions):
    1.  User Registration - POST /api/v1/auth/register
    2.  Email Verification Token Extraction - From application logs
    3.  Email Verification - POST /api/v1/auth/verify-email
    4.  Login - POST /api/v1/auth/login
    5.  Get User Profile - GET /api/v1/auth/me
    6.  Update Profile - PATCH /api/v1/auth/me
    7.  Token Refresh - POST /api/v1/auth/refresh
    8.  Verify New Access Token - GET /api/v1/auth/me (with refreshed token)
    9.  Password Reset Request - POST /api/v1/password-resets/
    10. Extract Reset Token - From application logs
    11. Verify Reset Token - GET /api/v1/password-resets/{token}
    12. Confirm Password Reset - PATCH /api/v1/password-resets/{token}
    13. Old Refresh Token Revoked - POST /api/v1/auth/refresh (should fail)
    14. Old Access Token Still Works - GET /api/v1/auth/me (stateless JWT)
    15. Login with New Password - POST /api/v1/auth/login
    16. Logout - POST /api/v1/auth/logout
    17. Refresh Token Revoked After Logout - POST /api/v1/auth/refresh (should fail)
    18. Access Token Still Works After Logout - GET /api/v1/auth/me (stateless JWT)

    Duration: ~3-5 seconds
    Frequency: Run before every deployment (CI gate)
    Failure Action: Block deployment
    """
    # Generate unique test email to avoid conflicts
    timestamp = int(datetime.now().timestamp() * 1000)
    email = f"smoke-test-{timestamp}@example.com"
    password = "SecurePass123!"

    # =========================================================================
    # Step 1: User Registration
    # =========================================================================
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "name": "Smoke Test User",
            },
        )
    assert response.status_code == 201, f"Registration failed: {response.text}"
    assert "message" in response.json()

    # =========================================================================
    # Step 2: Extract Email Verification Token
    # =========================================================================
    verification_token = extract_token_from_caplog(caplog, "verify-email?token=")
    assert verification_token is not None
    assert len(verification_token) > 0

    # =========================================================================
    # Step 3: Email Verification
    # =========================================================================
    response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
    )
    assert response.status_code == 200, f"Email verification failed: {response.text}"

    # =========================================================================
    # Step 4: Login
    # =========================================================================
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    login_data = response.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data

    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]

    # =========================================================================
    # Step 5: Get User Profile
    # =========================================================================
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    user = response.json()
    assert user["email"] == email
    assert user["name"] == "Smoke Test User"
    assert user["is_active"] is True
    assert user["email_verified"] is True

    # =========================================================================
    # Step 6: Update Profile
    # =========================================================================
    response = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"name": "Updated Smoke Test User"},
    )
    assert response.status_code == 200
    user = response.json()
    assert user["name"] == "Updated Smoke Test User"

    # =========================================================================
    # Step 7: Token Refresh
    # =========================================================================
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens

    new_access_token = tokens["access_token"]
    # Keep existing refresh token if not rotated
    refresh_token = tokens.get("refresh_token", refresh_token)

    # Verify tokens are valid format (JWTs are long strings with dots)
    assert len(new_access_token) > 100
    assert "." in new_access_token  # JWT structure: header.payload.signature

    # =========================================================================
    # Step 8: Verify New Access Token Works
    # =========================================================================
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert response.status_code == 200
    user = response.json()
    assert user["email"] == email

    # =========================================================================
    # Step 9: Password Reset Request
    # =========================================================================
    # Save old tokens before password reset (for revocation tests)
    old_refresh_token = refresh_token
    old_access_token = access_token

    # Clear caplog to isolate password reset token
    caplog.clear()

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/password-resets/",
            json={"email": email},
        )
    assert response.status_code == 202  # Accepted

    # =========================================================================
    # Step 10: Extract Password Reset Token
    # =========================================================================
    reset_token = extract_token_from_caplog(caplog, "reset-password?token=")
    assert reset_token is not None
    assert len(reset_token) > 0

    # =========================================================================
    # Step 11: Verify Reset Token
    # =========================================================================
    response = client.get(
        f"/api/v1/password-resets/{reset_token}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True

    # =========================================================================
    # Step 12: Confirm Password Reset
    # =========================================================================
    new_password = "NewSecurePass456!"
    response = client.patch(
        f"/api/v1/password-resets/{reset_token}",
        json={"new_password": new_password},
    )
    assert response.status_code == 200

    # =========================================================================
    # Step 13: Old Refresh Token Revoked After Password Reset
    # =========================================================================
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    # Should fail - token revoked by password reset
    assert response.status_code in [401, 403], (
        f"Expected 401 or 403, got {response.status_code}. "
        "Old refresh tokens should be revoked after password reset."
    )

    # =========================================================================
    # Step 14: Old Access Token Still Works Until Expiry
    # =========================================================================
    # JWTs are stateless - they work until expiry even after password reset
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert response.status_code == 200, (
        "Old access tokens should continue working until expiry "
        "(stateless JWTs are not revoked by password reset)"
    )

    # =========================================================================
    # Step 15: Login with New Password
    # =========================================================================
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": new_password,  # New password after reset
        },
    )
    assert response.status_code == 200, (
        f"Login with new password failed: {response.text}"
    )
    tokens = response.json()

    # Update tokens for logout test
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # =========================================================================
    # Step 16: Logout
    # =========================================================================
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200

    # =========================================================================
    # Step 17: Refresh Token Revoked After Logout
    # =========================================================================
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    # Should fail - token revoked by logout
    assert response.status_code in [401, 403], (
        f"Expected 401 or 403, got {response.status_code}. "
        "Refresh tokens should be revoked after logout."
    )

    # =========================================================================
    # Step 18: Access Token Still Works After Logout
    # =========================================================================
    # JWTs are stateless - they work until expiry even after logout
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200, (
        "Access tokens should continue working until expiry "
        "(stateless JWTs are not revoked by logout)"
    )


# =============================================================================
# Additional Smoke Tests (Independent, No Shared State)
# =============================================================================


def test_smoke_health_check(client):
    """Smoke: System health check endpoint is operational.

    Validates that the basic health check endpoint responds correctly,
    indicating the application is running and ready to serve requests.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_smoke_api_docs_accessible(client):
    """Smoke: API documentation is accessible.

    Validates that the OpenAPI documentation endpoint is available,
    which is critical for developer experience and API discovery.
    """
    response = client.get("/docs")
    assert response.status_code == 200


def test_smoke_invalid_login_rejected(client):
    """Smoke: Invalid login credentials are rejected.

    Validates that the authentication system properly rejects invalid
    credentials, ensuring basic security controls are functional.
    """
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401


def test_smoke_weak_password_rejected(client):
    """Smoke: Weak passwords are rejected during registration.

    Validates that password strength requirements are enforced,
    ensuring security policies are active.
    """
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak-test@example.com",
            "password": "weak",  # Too short, doesn't meet requirements
            "name": "Test User",
        },
    )
    assert response.status_code == 422  # Unprocessable Entity (validation error)
