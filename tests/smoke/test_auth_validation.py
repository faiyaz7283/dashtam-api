"""Smoke Tests: Authentication Validation & Security

These tests validate that authentication security controls are working:
- Invalid login attempts are rejected
- Weak passwords are rejected
- Security policies are enforced

These are independent tests that verify security mechanisms are active
and properly rejecting invalid attempts.
"""

import pytest


@pytest.mark.smoke
def test_smoke_invalid_login_rejected(client):
    """Smoke: Invalid login credentials are rejected.

    Validates:
    - Authentication system rejects invalid credentials
    - Returns 401 Unauthorized status
    - Basic security controls are functional

    This test ensures that the authentication system is not
    accepting arbitrary credentials, which would be a critical
    security vulnerability.
    """
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401


@pytest.mark.smoke
def test_smoke_weak_password_rejected(client):
    """Smoke: Weak passwords are rejected during registration.

    Validates:
    - Password strength requirements are enforced
    - Returns 422 Unprocessable Entity (validation error)
    - Security policies are active

    This test ensures that the password validation middleware
    is active and enforcing complexity requirements before
    user accounts are created.
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
