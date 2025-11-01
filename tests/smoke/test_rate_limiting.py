"""Smoke Tests: Rate Limiting & Brute Force Protection

These tests validate that rate limiting controls are operational:
- Brute force protection is active
- Rate limits are enforced correctly
- HTTP 429 responses work as expected
- Rate limit headers are present

These are independent tests that verify rate limiting mechanisms are active
and properly rejecting excessive requests.
"""

import pytest


@pytest.mark.smoke
def test_smoke_rate_limit_enforced_on_login(client):
    """Smoke: Rate limiting enforces brute force protection on login.

    Validates:
    - Login endpoint has rate limiting active
    - After hitting limit, returns 429 Too Many Requests
    - Rate limit headers are present in response
    - Brute force attacks are prevented

    This test ensures the rate limiting middleware is operational
    and protecting authentication endpoints from brute force attacks.

    Rate limit: 20 login attempts per 10 minutes (per IP)
    Test: Make 25 rapid requests to exceed limit
    """
    responses = []

    for i in range(25):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"brute-force-test-{i}@example.com",
                "password": "AttemptedPassword123!",
            },
        )
        responses.append(response.status_code)

        # Once we hit rate limit, verify and break
        if response.status_code == 429:
            # Verify 429 response structure
            data = response.json()
            assert "error" in data
            assert data["error"] == "Rate limit exceeded"
            assert "retry_after" in data
            assert "endpoint" in data
            assert data["endpoint"] == "POST /api/v1/auth/login"

            # Verify rate limit headers present
            assert "retry-after" in response.headers
            assert "x-ratelimit-limit" in response.headers
            assert "x-ratelimit-remaining" in response.headers
            assert response.headers["x-ratelimit-remaining"] == "0"

            break

    # Verify that rate limit was actually hit
    assert 429 in responses, (
        "Rate limit not enforced. Expected 429 after 20 requests. "
        f"Got status codes: {responses}"
    )


@pytest.mark.smoke
def test_smoke_rate_limit_headers_on_success(client):
    """Smoke: Rate limit headers present on successful requests.

    Validates:
    - Rate limit headers added to successful (2xx) responses
    - Headers provide limit, remaining, and reset information
    - Clients can track their rate limit status

    This test ensures clients receive rate limiting information
    on successful requests, not just when rate limited.

    Note: Uses login endpoint (rate limited) with invalid credentials.
    We expect 401 Unauthorized, but rate limit headers should still be present.
    """
    # Make a single request to rate-limited endpoint
    # We expect 401 (invalid credentials) but rate limit headers should be present
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword123!",
        },
    )

    # Login should fail with invalid credentials
    assert response.status_code == 401

    # But rate limit headers should still be present
    # Note: Login endpoint has limit of 20 per 10 minutes
    assert "x-ratelimit-limit" in response.headers
    assert "x-ratelimit-remaining" in response.headers
    assert "x-ratelimit-reset" in response.headers

    # Verify header values are numeric
    limit = int(response.headers["x-ratelimit-limit"])
    remaining = int(response.headers["x-ratelimit-remaining"])
    reset = int(response.headers["x-ratelimit-reset"])

    assert limit == 20, "Login rate limit should be 20 per window"
    assert remaining >= 0, "Remaining should be non-negative"
    assert reset > 0, "Reset time should be positive"
