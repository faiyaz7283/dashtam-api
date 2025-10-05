"""API tests for provider type catalog endpoints.

These tests verify the provider type endpoints that return the catalog
of available providers (templates), separate from provider instances.
"""

from fastapi import status
from fastapi.testclient import TestClient


class TestProviderTypeListingEndpoints:
    """Test suite for provider type catalog endpoints."""

    def test_list_all_provider_types(self, client: TestClient):
        """Test getting list of all available provider types."""
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
        """Test filtering for only configured providers."""
        response = client.get("/api/v1/provider-types?configured=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned providers should be configured
        for provider in data:
            assert provider["is_configured"] is True

    def test_list_unconfigured_provider_types(self, client: TestClient):
        """Test filtering for only unconfigured providers."""
        response = client.get("/api/v1/provider-types?configured=false")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned providers should NOT be configured
        for provider in data:
            assert provider["is_configured"] is False

    def test_get_specific_provider_type(self, client: TestClient):
        """Test getting details of a specific provider type."""
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
        """Test getting a non-existent provider type returns 404."""
        response = client.get("/api/v1/provider-types/nonexistent_provider")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


class TestProviderTypeResponseStructure:
    """Test suite for provider type response structure validation."""

    def test_provider_type_has_all_required_fields(self, client: TestClient):
        """Test that provider type response includes all expected fields."""
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
        """Test that supported_features is always a list."""
        response = client.get("/api/v1/provider-types")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for provider in data:
            assert isinstance(provider["supported_features"], list), (
                "supported_features should be a list"
            )


class TestProviderTypeNoAuthRequired:
    """Test suite to verify provider type endpoints don't require authentication."""

    def test_list_provider_types_no_auth(self, client_no_auth: TestClient):
        """Test that listing provider types doesn't require authentication."""
        response = client_no_auth.get("/api/v1/provider-types")

        # Should work without authentication
        assert response.status_code == status.HTTP_200_OK

    def test_get_provider_type_no_auth(self, client_no_auth: TestClient):
        """Test that getting specific provider type doesn't require auth."""
        # Get a valid provider key first
        list_response = client_no_auth.get("/api/v1/provider-types")
        providers = list_response.json()
        if len(providers) > 0:
            provider_key = providers[0]["key"]

            response = client_no_auth.get(f"/api/v1/provider-types/{provider_key}")

            # Should work without authentication
            assert response.status_code == status.HTTP_200_OK
