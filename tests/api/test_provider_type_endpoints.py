"""API tests for provider type catalog endpoints.

These tests verify the provider type endpoints that return the catalog
of available providers (templates), separate from provider instances.
"""

from fastapi import status
from fastapi.testclient import TestClient


class TestProviderTypeListingEndpoints:
    """Test suite for provider type catalog endpoints.

    Tests read-only catalog endpoints for available provider types (templates),
    separate from user-specific provider instances.
    """

    def test_list_all_provider_types(self, client: TestClient):
        """Test GET /api/v1/provider-types returns all provider type templates.

        Verifies that:
        - Endpoint returns 200 OK
        - Response is a list of provider types
        - At least one provider type returned
        - Each type has required fields (key, name, provider_type, is_configured, supported_features)

        Args:
            client: Authenticated test client fixture

        Note:
            Provider types are templates/catalog, not user instances.
        """
        response = client.get("/api/v1/provider-types")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return a list of providers
        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure of first provider
        provider_info = data[0]
        assert "key" in provider_info
        assert "name" in provider_info
        assert "provider_type" in provider_info
        assert "is_configured" in provider_info
        assert "supported_features" in provider_info

    def test_list_configured_provider_types(self, client: TestClient):
        """Test GET /api/v1/provider-types?configured=true filters configured providers.

        Verifies that:
        - Query parameter configured=true works
        - All returned providers have is_configured=True
        - Only providers with API credentials configured returned

        Args:
            client: Authenticated test client fixture

        Note:
            Configured means API keys/secrets set in environment.
        """
        response = client.get("/api/v1/provider-types?configured=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned providers should be configured
        for provider in data:
            assert provider["is_configured"] is True

    def test_list_unconfigured_provider_types(self, client: TestClient):
        """Test GET /api/v1/provider-types?configured=false filters unconfigured.

        Verifies that:
        - Query parameter configured=false works
        - All returned providers have is_configured=False
        - Only providers without API credentials returned

        Args:
            client: Authenticated test client fixture

        Note:
            Shows providers user cannot connect to yet.
        """
        response = client.get("/api/v1/provider-types?configured=false")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned providers should NOT be configured
        for provider in data:
            assert provider["is_configured"] is False

    def test_get_specific_provider_type(self, client: TestClient):
        """Test GET /api/v1/provider-types/{key} returns specific provider type.

        Verifies that:
        - Endpoint returns 200 OK for valid provider key
        - Response contains provider type details
        - key matches requested provider
        - All standard fields included

        Args:
            client: Authenticated test client fixture

        Note:
            Gets catalog info for one provider type.
        """
        # First get list to find a valid provider key
        list_response = client.get("/api/v1/provider-types")
        assert list_response.status_code == status.HTTP_200_OK
        providers = list_response.json()
        assert len(providers) > 0

        provider_key = providers[0]["key"]

        # Now get the specific provider
        response = client.get(f"/api/v1/provider-types/{provider_key}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["key"] == provider_key
        assert "name" in data
        assert "provider_type" in data
        assert "is_configured" in data

    def test_get_nonexistent_provider_type(self, client: TestClient):
        """Test GET /api/v1/provider-types/{invalid_key} returns 404.

        Verifies that:
        - Endpoint returns 404 Not Found
        - Error message mentions "not found"
        - Invalid provider key handled gracefully

        Args:
            client: Authenticated test client fixture
        """
        response = client.get("/api/v1/provider-types/nonexistent_provider")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


class TestProviderTypeResponseStructure:
    """Test suite for provider type response structure validation.

    Validates response schemas match expected structure for provider type catalog.
    """

    def test_provider_type_has_all_required_fields(self, client: TestClient):
        """Test provider type response schema includes all required fields.

        Verifies that:
        - All required fields present (key, name, provider_type, description, is_configured, supported_features)
        - Optional field icon_url included (may be None)
        - Response conforms to ProviderType schema

        Args:
            client: Authenticated test client fixture

        Note:
            Schema validation for consistency.
        """
        response = client.get("/api/v1/provider-types")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) > 0

        provider = data[0]

        # Required fields
        required_fields = [
            "key",
            "name",
            "provider_type",
            "description",
            "is_configured",
            "supported_features",
        ]
        for field in required_fields:
            assert field in provider, f"Missing field: {field}"

        # Optional fields (icon_url may be None)
        assert "icon_url" in provider

    def test_supported_features_is_list(self, client: TestClient):
        """Test supported_features field is always a list type.

        Verifies that:
        - supported_features is Python list type
        - Field type consistent across all provider types
        - No null or invalid values

        Args:
            client: Authenticated test client fixture

        Note:
            Type safety validation for API contract.
        """
        response = client.get("/api/v1/provider-types")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for provider in data:
            assert isinstance(provider["supported_features"], list), (
                "supported_features should be a list"
            )


class TestProviderTypeNoAuthRequired:
    """Test suite to verify provider type endpoints don't require authentication.

    Provider type catalog is public information - no user auth required.
    """

    def test_list_provider_types_no_auth(self, client_no_auth: TestClient):
        """Test GET /api/v1/provider-types works without authentication.

        Verifies that:
        - Endpoint returns 200 OK without auth
        - Provider catalog is public
        - No authentication required to browse

        Args:
            client_no_auth: Unauthenticated test client fixture

        Note:
            Public endpoint for discovery.
        """
        response = client_no_auth.get("/api/v1/provider-types")

        # Should work without authentication
        assert response.status_code == status.HTTP_200_OK

    def test_get_provider_type_no_auth(self, client_no_auth: TestClient):
        """Test GET /api/v1/provider-types/{key} works without authentication.

        Verifies that:
        - Endpoint returns 200 OK without auth
        - Specific provider details are public
        - No authentication required

        Args:
            client_no_auth: Unauthenticated test client fixture

        Note:
            Public endpoint for provider info.
        """
        # Get a valid provider key first
        list_response = client_no_auth.get("/api/v1/provider-types")
        providers = list_response.json()
        if len(providers) > 0:
            provider_key = providers[0]["key"]

            response = client_no_auth.get(f"/api/v1/provider-types/{provider_key}")

            # Should work without authentication
            assert response.status_code == status.HTTP_200_OK
