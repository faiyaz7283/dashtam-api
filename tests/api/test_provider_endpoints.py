"""API tests for provider management endpoints.

These tests use FastAPI's TestClient to test endpoints synchronously,
verifying the full request/response cycle including validation,
authentication, and database operations.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.provider import Provider, ProviderConnection
from src.models.user import User


class TestProviderListingEndpoints:
    """Test suite for provider listing endpoints."""

    def test_get_available_providers(self, client: TestClient):
        """Test getting list of available provider types."""
        response = client.get("/api/v1/providers/available")
        
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

    def test_get_configured_providers(self, client: TestClient):
        """Test getting only configured providers."""
        response = client.get("/api/v1/providers/configured")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # All returned providers should be configured
        for provider in data:
            assert provider["is_configured"] is True


class TestProviderInstanceEndpoints:
    """Test suite for provider instance management."""

    def test_create_provider_instance(self, client: TestClient, test_user: User):
        """Test creating a new provider instance."""
        payload = {
            "provider_key": "schwab",
            "alias": "My Schwab Account"
        }
        
        response = client.post("/api/v1/providers/create", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["provider_key"] == "schwab"
        assert data["alias"] == "My Schwab Account"
        assert data["status"] == "pending"
        assert data["is_connected"] is False
        assert data["needs_reconnection"] is True

    def test_create_provider_invalid_key(self, client: TestClient):
        """Test creating a provider with invalid provider_key."""
        payload = {
            "provider_key": "nonexistent_provider",
            "alias": "Test"
        }
        
        response = client.post("/api/v1/providers/create", json=payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not available" in response.json()["detail"].lower()

    def test_create_provider_duplicate_alias(
        self, client: TestClient, test_user: User, db_session
    ):
        """Test creating a provider with duplicate alias fails."""
        # Create first provider
        provider1 = Provider(
            user_id=test_user.id,
            provider_key="schwab",
            alias="My Account"
        )
        db_session.add(provider1)
        db_session.commit()

        # Try to create second with same alias
        payload = {
            "provider_key": "schwab",
            "alias": "My Account"
        }
        
        response = client.post("/api/v1/providers/create", json=payload)
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already have a provider" in response.json()["detail"]

    def test_list_user_providers(
        self, client: TestClient, test_user: User, db_session
    ):
        """Test listing all providers for the current user."""
        # Create test providers
        providers = [
            Provider(
                user_id=test_user.id,
                provider_key="schwab",
                alias=f"Schwab {i}"
            )
            for i in range(3)
        ]
        for provider in providers:
            db_session.add(provider)
        db_session.commit()

        response = client.get("/api/v1/providers/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should return at least our created providers
        assert len(data) >= 3
        aliases = [p["alias"] for p in data]
        assert "Schwab 0" in aliases
        assert "Schwab 1" in aliases
        assert "Schwab 2" in aliases

    def test_get_provider_by_id(
        self, client: TestClient, test_user: User, db_session
    ):
        """Test getting a specific provider by ID."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id,
            provider_key="schwab",
            alias="Test Provider"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        response = client.get(f"/api/v1/providers/{provider.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == str(provider.id)
        assert data["alias"] == "Test Provider"
        assert data["provider_key"] == "schwab"

    def test_get_provider_not_found(self, client: TestClient):
        """Test getting a non-existent provider returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/v1/providers/{fake_uuid}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_provider(
        self, client: TestClient, test_user: User, db_session
    ):
        """Test deleting a provider instance."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id,
            provider_key="schwab",
            alias="To Delete"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        provider_id = provider.id
        
        response = client.delete(f"/api/v1/providers/{provider_id}")
        
        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]

        # Verify provider is actually deleted
        from sqlmodel import select
        result = db_session.execute(
            select(Provider).where(Provider.id == provider_id)
        )
        assert result.scalar_one_or_none() is None

    def test_delete_provider_not_found(self, client: TestClient):
        """Test deleting a non-existent provider returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.delete(f"/api/v1/providers/{fake_uuid}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestProviderConnectionStatus:
    """Test suite for provider connection status."""

    def test_provider_with_pending_connection(
        self, client: TestClient, test_user: User, db_session
    ):
        """Test provider with pending connection shows correct status."""
        provider = Provider(
            user_id=test_user.id,
            provider_key="schwab",
            alias="Pending Connection"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(provider)

        response = client.get(f"/api/v1/providers/{provider.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "pending"
        assert data["is_connected"] is False
        # Note: needs_reconnection is derived from connection status in the response

    def test_provider_with_active_connection(
        self, client: TestClient, test_provider_with_connection
    ):
        """Test provider with active connection shows correct status."""
        provider = test_provider_with_connection
        
        response = client.get(f"/api/v1/providers/{provider.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "active"
        assert data["is_connected"] is True
        assert data["needs_reconnection"] is False

    def test_list_providers_includes_connection_info(
        self, client: TestClient, test_provider_with_connection
    ):
        """Test that listing providers includes connection information."""
        response = client.get("/api/v1/providers/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Find our test provider
        provider_data = next(
            (p for p in data if p["id"] == str(test_provider_with_connection.id)),
            None
        )
        
        assert provider_data is not None
        assert "status" in provider_data
        assert "is_connected" in provider_data
        assert "needs_reconnection" in provider_data
        assert "connected_at" in provider_data


class TestProviderValidation:
    """Test suite for request validation."""

    def test_create_provider_missing_fields(self, client: TestClient):
        """Test creating provider with missing required fields."""
        # Missing alias
        response = client.post(
            "/api/v1/providers/create",
            json={"provider_key": "schwab"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Missing provider_key
        response = client.post(
            "/api/v1/providers/create",
            json={"alias": "Test"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_provider_invalid_json(self, client: TestClient):
        """Test creating provider with invalid JSON."""
        response = client.post(
            "/api/v1/providers/create",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_provider_invalid_uuid(self, client: TestClient):
        """Test getting provider with invalid UUID format."""
        response = client.get("/api/v1/providers/not-a-uuid")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_provider_empty_alias(self, client: TestClient):
        """Test creating provider with empty alias."""
        payload = {
            "provider_key": "schwab",
            "alias": ""
        }
        
        response = client.post("/api/v1/providers/create", json=payload)
        
        # Note: Currently empty alias is allowed at API level
        # This documents current behavior - could add validation later
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["alias"] == ""


class TestProviderResponseStructure:
    """Test suite for response structure validation."""

    def test_provider_response_has_all_fields(
        self, client: TestClient, test_provider_with_connection
    ):
        """Test that provider response includes all expected fields."""
        response = client.get(f"/api/v1/providers/{test_provider_with_connection.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Required fields
        required_fields = [
            "id", "provider_key", "alias", "status",
            "is_connected", "needs_reconnection", "accounts_count"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Optional fields (may be None)
        optional_fields = ["connected_at", "last_sync_at"]
        for field in optional_fields:
            assert field in data, f"Missing field: {field}"

    def test_provider_list_response_structure(self, client: TestClient):
        """Test that provider list returns correctly structured data."""
        response = client.get("/api/v1/providers/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        
        # If any providers exist, check structure
        if data:
            provider = data[0]
            assert "id" in provider
            assert "provider_key" in provider
            assert "alias" in provider
            assert "status" in provider
