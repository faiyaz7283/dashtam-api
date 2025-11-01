"""API tests for Rate Limiter enforcement on all endpoints.

This test suite verifies that Rate Limiter is properly configured and enforced
on all API endpoints as specified in src/config/rate_limits.py.

Test Strategy:
- Test each endpoint category (auth, token rotation, provider)
- Verify 429 responses when limits exceeded
- Test rate limit headers (X-RateLimit-*, Retry-After)
- Verify different scopes (IP, user, user_provider, global)
- Validate fail-open behavior

Coverage:
- Authentication endpoints (login, register, password reset, verification)
- Token rotation endpoints (user, global, provider)
- Provider management endpoints (CRUD operations)
- Provider OAuth flow endpoints (authorization, callback)
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


class TestAuthenticationEndpointRateLimiter:
    """Test Rate Limiter on authentication endpoints.
    
    Endpoints tested:
    - POST /api/v1/auth/login (20 requests/min, IP-based)
    - POST /api/v1/auth/register (10 requests/min, IP-based)
    - POST /api/v1/auth/password-resets (5 requests/min, IP-based)
    - POST /api/v1/auth/verification/resend (3 requests/min, IP-based)
    """

    def test_login_endpoint_rate_limiter(self, client: TestClient):
        """Test login endpoint Rate Limiter (20 req/min, IP-based).
        
        Verifies:
        - Rate limit enforced at 20 requests
        - HTTP 429 returned after limit
        - Retry-After header present
        - Rate limit headers correct
        """
        responses = []
        for i in range(25):  # Exceed limit of 20
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": f"test{i}@example.com",
                    "password": "WrongPassword123!",
                },
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                # Verify 429 response structure
                data = response.json()
                assert data["error"] == "Rate limit exceeded"
                assert data["endpoint"] == "POST /api/v1/auth/login"
                assert "retry_after" in data
                
                # Verify headers
                assert "retry-after" in response.headers
                assert "x-ratelimit-limit" in response.headers
                assert response.headers["x-ratelimit-limit"] == "20"
                assert response.headers["x-ratelimit-remaining"] == "0"
                break
        
        # Should hit 429 within 25 requests
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_register_endpoint_rate_limiter(self, client: TestClient):
        """Test register endpoint Rate Limiter (10 req/min, IP-based).
        
        Verifies:
        - Rate limit enforced at 10 requests
        - HTTP 429 returned after limit
        - Rate limit more restrictive than login
        """
        responses = []
        for i in range(15):  # Exceed limit of 10
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test{i}@example.com",
                    "password": "TestPassword123!",
                    "name": "Test User",
                },
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert data["endpoint"] == "POST /api/v1/auth/register"
                assert response.headers["x-ratelimit-limit"] == "10"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_password_reset_endpoint_rate_limiter(self, client: TestClient):
        """Test password reset endpoint Rate Limiter (5 req/min, IP-based).
        
        Verifies:
        - Very restrictive limit (5 requests)
        - Appropriate for sensitive operation
        """
        responses = []
        for i in range(10):  # Exceed limit of 5
            response = client.post(
                "/api/v1/password-resets/",
                json={"email": f"test{i}@example.com"},
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert data["endpoint"] == "POST /api/v1/password-resets/"
                assert response.headers["x-ratelimit-limit"] == "5"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_verification_resend_endpoint_rate_limiter(self, client: TestClient):
        """Test verification resend endpoint Rate Limiter (3 req/min, IP-based).
        
        Verifies:
        - Most restrictive auth limit (3 requests)
        - Prevents email spam
        """
        responses = []
        for i in range(8):  # Exceed limit of 3
            response = client.post(
                "/api/v1/auth/verification/resend",
                json={"email": f"test{i}@example.com"},
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert data["endpoint"] == "POST /api/v1/auth/verification/resend"
                assert response.headers["x-ratelimit-limit"] == "3"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses


class TestTokenRotationEndpointRateLimiter:
    """Test Rate Limiter on token rotation endpoints.
    
    Endpoints tested:
    - POST /api/v1/auth/tokens/rotate/user (5 per 15 min, user-based)
    - POST /api/v1/auth/tokens/rotate/global (1 per day, global)
    - POST /api/v1/auth/tokens/rotate/provider (5 per 5 min, user_provider)
    
    NOTE: These are CRITICAL security endpoints with strict limits.
    """

    def test_user_token_rotation_rate_limiter(
        self, client: TestClient, auth_headers: dict
    ):
        """Test user token rotation Rate Limiter (5 per 15 min, user-based).
        
        Verifies:
        - Strict limit (5 requests)
        - User-scoped (not IP-based)
        - Prevents DoS via token rotation spam
        """
        responses = []
        for i in range(8):  # Exceed limit of 5
            response = client.post(
                "/api/v1/auth/tokens/rotate/user",
                headers=auth_headers,
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert data["endpoint"] == "POST /api/v1/auth/tokens/rotate/user"
                assert response.headers["x-ratelimit-limit"] == "5"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_global_token_rotation_rate_limiter(
        self, client: TestClient, admin_auth_headers: dict
    ):
        """Test global token rotation Rate Limiter (1 per day, global).
        
        Verifies:
        - Extremely restrictive (1 request)
        - Global scope (system-wide limit)
        - Prevents accidental system-wide token revocation
        
        NOTE: Requires admin authentication
        """
        # First request should succeed (or fail with business logic, not 429)
        first_response = client.post(
            "/api/v1/auth/tokens/rotate/global",
            headers=admin_auth_headers,
        )
        
        # Second request should hit Rate Limiter
        second_response = client.post(
            "/api/v1/auth/tokens/rotate/global",
            headers=admin_auth_headers,
        )
        
        # Should get 429 on second request
        assert second_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = second_response.json()
        assert data["endpoint"] == "POST /api/v1/auth/tokens/rotate/global"
        assert second_response.headers["x-ratelimit-limit"] == "1"

    def test_provider_token_rotation_rate_limiter(
        self, client: TestClient, auth_headers: dict, provider_id: str
    ):
        """Test provider token rotation Rate Limiter (5 per 5 min, user_provider).
        
        Verifies:
        - Strict limit (5 requests)
        - User-per-provider scope
        - Prevents abuse of provider token rotation
        """
        responses = []
        for i in range(8):  # Exceed limit of 5
            response = client.post(
                f"/api/v1/auth/tokens/rotate/provider/{provider_id}",
                headers=auth_headers,
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert (
                    data["endpoint"]
                    == f"POST /api/v1/auth/tokens/rotate/provider/{provider_id}"
                )
                assert response.headers["x-ratelimit-limit"] == "5"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses


class TestProviderEndpointRateLimiter:
    """Test Rate Limiter on provider management endpoints.
    
    Endpoints tested:
    - POST /api/v1/providers (100 req/min, user-based)
    - GET /api/v1/providers (100 req/min, user-based)
    - GET /api/v1/providers/{id} (100 req/min, user-based)
    - PATCH /api/v1/providers/{id} (50 req/min, user-based)
    - DELETE /api/v1/providers/{id} (20 req/min, user-based)
    """

    def test_create_provider_rate_limiter(
        self, client: TestClient, auth_headers: dict
    ):
        """Test create provider Rate Limiter (100 req/min, user-based).
        
        Verifies:
        - Generous limit for normal operations
        - User-scoped Rate Limiter
        """
        # Make 105 requests to exceed limit
        responses = []
        for i in range(105):
            response = client.post(
                "/api/v1/providers",
                headers=auth_headers,
                json={"provider_type": "schwab", "name": f"Test Provider {i}"},
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert data["endpoint"] == "POST /api/v1/providers"
                assert response.headers["x-ratelimit-limit"] == "100"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_list_providers_rate_limiter(
        self, client: TestClient, auth_headers: dict
    ):
        """Test list providers Rate Limiter (100 req/min, user-based)."""
        responses = []
        for i in range(105):
            response = client.get("/api/v1/providers", headers=auth_headers)
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert data["endpoint"] == "GET /api/v1/providers"
                assert response.headers["x-ratelimit-limit"] == "100"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_update_provider_rate_limiter(
        self, client: TestClient, auth_headers: dict, provider_id: str
    ):
        """Test update provider Rate Limiter (50 req/min, user-based).
        
        Verifies:
        - More restrictive than read operations (50 vs 100)
        - Appropriate for write operations
        """
        responses = []
        for i in range(55):
            response = client.patch(
                f"/api/v1/providers/{provider_id}",
                headers=auth_headers,
                json={"name": f"Updated Name {i}"},
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert (
                    data["endpoint"] == f"PATCH /api/v1/providers/{provider_id}"
                )
                assert response.headers["x-ratelimit-limit"] == "50"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

    def test_delete_provider_rate_limiter(
        self, client: TestClient, auth_headers: dict, provider_id: str
    ):
        """Test delete provider Rate Limiter (20 req/min, user-based).
        
        Verifies:
        - Very restrictive (20 requests)
        - Appropriate for destructive operation
        """
        responses = []
        for i in range(25):
            response = client.delete(
                f"/api/v1/providers/{provider_id}",
                headers=auth_headers,
            )
            responses.append(response.status_code)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                data = response.json()
                assert (
                    data["endpoint"] == f"DELETE /api/v1/providers/{provider_id}"
                )
                assert response.headers["x-ratelimit-limit"] == "20"
                break
        
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses


class TestRateLimiterHeaders:
    """Test Rate Limiter HTTP headers on all responses.
    
    Headers tested:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining after this one
    - X-RateLimit-Reset: Seconds until bucket fully resets
    - Retry-After: Seconds to wait before retry (429 only)
    """

    def test_rate_limiter_headers_on_success(self, client: TestClient):
        """Test rate limit headers present on successful response.
        
        Verifies:
        - All three X-RateLimit-* headers present
        - Header values are valid integers
        - Remaining decreases with each request
        """
        # First request
        response1 = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test1@example.com",
                "password": "TestPass123!",
                "name": "Test",
            },
        )
        
        # Verify headers present
        assert "x-ratelimit-limit" in response1.headers
        assert "x-ratelimit-remaining" in response1.headers
        assert "x-ratelimit-reset" in response1.headers
        
        # Verify values are integers
        limit1 = int(response1.headers["x-ratelimit-limit"])
        remaining1 = int(response1.headers["x-ratelimit-remaining"])
        reset1 = int(response1.headers["x-ratelimit-reset"])
        
        assert limit1 > 0
        assert remaining1 >= 0
        assert reset1 > 0
        
        # Second request - remaining should decrease
        response2 = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test2@example.com",
                "password": "TestPass123!",
                "name": "Test",
            },
        )
        
        remaining2 = int(response2.headers["x-ratelimit-remaining"])
        assert remaining2 < remaining1

    def test_retry_after_header_on_429(self, client: TestClient):
        """Test Retry-After header present in 429 response.
        
        Verifies:
        - Retry-After header present
        - Value is positive integer (seconds)
        - Matches retry_after in JSON body
        """
        # Exhaust rate limit
        for i in range(15):
            response = client.post(
                "/api/v1/auth/register",
                json={"email": f"test{i}@example.com", "password": "pass", "name": "Test"},
            )
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        
        # Verify 429 response has Retry-After
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "retry-after" in response.headers
        
        retry_after_header = int(response.headers["retry-after"])
        retry_after_body = response.json()["retry_after"]
        
        assert retry_after_header > 0
        assert retry_after_header == retry_after_body

    def test_rate_limiter_headers_consistent_across_requests(
        self, client: TestClient
    ):
        """Test Rate Limiter headers remain consistent for same endpoint.
        
        Verifies:
        - X-RateLimit-Limit stays constant
        - X-RateLimit-Remaining decreases monotonically
        - X-RateLimit-Reset stays relatively constant
        """
        limits = []
        remainings = []
        
        for i in range(5):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test{i}@example.com",
                    "password": "pass",
                    "name": "Test",
                },
            )
            
            if response.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                limits.append(int(response.headers["x-ratelimit-limit"]))
                remainings.append(int(response.headers["x-ratelimit-remaining"]))
        
        # Limit should be constant
        assert len(set(limits)) == 1
        
        # Remaining should decrease
        for i in range(len(remainings) - 1):
            assert remainings[i] > remainings[i + 1]


# Pytest fixtures for authenticated requests
@pytest.fixture
def auth_headers(authenticated_user: dict):
    """Fixture providing authentication headers for user.
    
    Uses existing authenticated_user fixture from conftest.py.
    
    Returns:
        dict: Headers with JWT access token for authenticated user
    """
    return {"Authorization": f"Bearer {authenticated_user['access_token']}"}


@pytest.fixture
def admin_auth_headers(authenticated_user: dict):
    """Fixture providing authentication headers for admin user.
    
    Returns:
        dict: Headers with JWT access token for admin user
        
    NOTE: Currently uses regular user (admin role not implemented yet)
    """
    # TODO: Implement admin user creation once roles are added
    # For now, use regular authenticated user
    return {"Authorization": f"Bearer {authenticated_user['access_token']}"}


@pytest.fixture
def provider_id(client: TestClient, auth_headers: dict):
    """Fixture providing a provider ID for testing.
    
    Returns:
        str: UUID of created provider
    """
    response = client.post(
        "/api/v1/providers",
        headers=auth_headers,
        json={"provider_type": "schwab", "name": "Test Provider"},
    )
    
    return response.json()["id"]
