"""API tests for provider management endpoints.

These tests use FastAPI's TestClient to test endpoints synchronously,
verifying the full request/response cycle including validation,
authentication, and database operations.
"""

from fastapi import status
from fastapi.testclient import TestClient

from src.models.provider import Provider, ProviderConnection
from src.models.user import User


class TestProviderInstanceEndpoints:
    """Test suite for provider instance management."""

    def test_create_provider_instance(
        self, client_with_mock_auth: TestClient, test_user: User
    ):
        """Test creating a new provider instance."""
        payload = {"provider_key": "schwab", "alias": "My Schwab Account"}

        response = client_with_mock_auth.post("/api/v1/providers", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify response structure
        assert "id" in data
        assert data["provider_key"] == "schwab"
        assert data["alias"] == "My Schwab Account"
        assert data["status"] == "pending"
        assert data["is_connected"] is False
        assert data["needs_reconnection"] is True

    def test_create_provider_invalid_key(self, client_with_mock_auth: TestClient):
        """Test creating a provider with invalid provider_key."""
        payload = {"provider_key": "nonexistent_provider", "alias": "Test"}

        response = client_with_mock_auth.post("/api/v1/providers", json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not available" in response.json()["detail"].lower()

    def test_create_provider_duplicate_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test creating a provider with duplicate alias fails."""
        # Create first provider
        provider1 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="My Account"
        )
        db_session.add(provider1)
        db_session.commit()

        # Try to create second with same alias
        payload = {"provider_key": "schwab", "alias": "My Account"}

        response = client_with_mock_auth.post("/api/v1/providers", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already have a provider" in response.json()["detail"]

    def test_list_user_providers(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test listing all providers for the current user."""
        # Create test providers
        providers = [
            Provider(user_id=test_user.id, provider_key="schwab", alias=f"Schwab {i}")
            for i in range(3)
        ]
        for provider in providers:
            db_session.add(provider)
        db_session.commit()

        response = client_with_mock_auth.get("/api/v1/providers/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify paginated response structure
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data
        assert "has_next" in data
        assert "has_prev" in data

        # Should return at least our created providers
        assert len(data["items"]) >= 3
        aliases = [p["alias"] for p in data["items"]]
        assert "Schwab 0" in aliases
        assert "Schwab 1" in aliases
        assert "Schwab 2" in aliases

    def test_list_providers_pagination(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test provider list pagination."""
        # Create 15 test providers
        providers = [
            Provider(
                user_id=test_user.id, provider_key="schwab", alias=f"Provider {i}"
            )
            for i in range(15)
        ]
        for provider in providers:
            db_session.add(provider)
        db_session.commit()

        # Test page 1 with 10 items per page
        response = client_with_mock_auth.get("/api/v1/providers?page=1&per_page=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["page"] == 1
        assert data["per_page"] == 10
        assert data["total"] >= 15
        assert len(data["items"]) == 10
        assert data["has_next"] is True
        assert data["has_prev"] is False

        # Test page 2
        response = client_with_mock_auth.get("/api/v1/providers?page=2&per_page=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["page"] == 2
        assert len(data["items"]) >= 5  # At least 5 more
        assert data["has_prev"] is True

    def test_list_providers_filtering_by_provider_key(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test filtering providers by provider_key."""
        # Create providers of different types
        schwab_provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Schwab Account"
        )
        db_session.add(schwab_provider)
        db_session.commit()

        # Filter by schwab
        response = client_with_mock_auth.get(
            "/api/v1/providers?provider_key=schwab"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for item in data["items"]:
            assert item["provider_key"] == "schwab"

    def test_list_providers_sorting(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test sorting providers by alias."""
        # Create providers with specific aliases
        providers = [
            Provider(user_id=test_user.id, provider_key="schwab", alias="Zebra"),
            Provider(user_id=test_user.id, provider_key="schwab", alias="Alpha"),
            Provider(user_id=test_user.id, provider_key="schwab", alias="Beta"),
        ]
        for provider in providers:
            db_session.add(provider)
        db_session.commit()

        # Test ascending sort
        response = client_with_mock_auth.get(
            "/api/v1/providers?sort=alias&order=asc"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        aliases = [item["alias"] for item in data["items"]]
        # Check if aliases are sorted
        assert aliases == sorted(aliases)

    def test_list_providers_invalid_sort_field(
        self, client_with_mock_auth: TestClient
    ):
        """Test that invalid sort field returns 400."""
        response = client_with_mock_auth.get("/api/v1/providers?sort=invalid_field")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot sort" in response.json()["detail"]

    def test_get_provider_by_id(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test getting a specific provider by ID."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Provider"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        response = client_with_mock_auth.get(f"/api/v1/providers/{provider.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(provider.id)
        assert data["alias"] == "Test Provider"
        assert data["provider_key"] == "schwab"

    def test_get_provider_not_found(self, client_with_mock_auth: TestClient):
        """Test getting a non-existent provider returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client_with_mock_auth.get(f"/api/v1/providers/{fake_uuid}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_provider(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test deleting a provider instance."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="To Delete"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        provider_id = provider.id

        response = client_with_mock_auth.delete(f"/api/v1/providers/{provider_id}")

        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]

        # Verify provider is actually deleted
        from sqlmodel import select

        result = db_session.execute(select(Provider).where(Provider.id == provider_id))
        assert result.scalar_one_or_none() is None

    def test_delete_provider_not_found(self, client_with_mock_auth: TestClient):
        """Test deleting a non-existent provider returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client_with_mock_auth.delete(f"/api/v1/providers/{fake_uuid}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestProviderConnectionStatus:
    """Test suite for provider connection status."""

    def test_provider_with_pending_connection(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test provider with pending connection shows correct status."""
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Pending Connection"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(provider)

        response = client_with_mock_auth.get(f"/api/v1/providers/{provider.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "pending"
        assert data["is_connected"] is False
        # Note: needs_reconnection is derived from connection status in the response

    def test_provider_with_active_connection(
        self, client_with_mock_auth: TestClient, test_provider_with_connection
    ):
        """Test provider with active connection shows correct status."""
        provider = test_provider_with_connection

        response = client_with_mock_auth.get(f"/api/v1/providers/{provider.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "active"
        assert data["is_connected"] is True
        assert data["needs_reconnection"] is False

    def test_list_providers_includes_connection_info(
        self, client_with_mock_auth: TestClient, test_provider_with_connection
    ):
        """Test that listing providers includes connection information."""
        response = client_with_mock_auth.get("/api/v1/providers/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Find our test provider in paginated items
        provider_data = next(
            (
                p
                for p in data["items"]
                if p["id"] == str(test_provider_with_connection.id)
            ),
            None,
        )

        assert provider_data is not None
        assert "status" in provider_data
        assert "is_connected" in provider_data
        assert "needs_reconnection" in provider_data
        assert "connected_at" in provider_data


class TestProviderValidation:
    """Test suite for request validation."""

    def test_create_provider_missing_fields(self, client_with_mock_auth: TestClient):
        """Test creating provider with missing required fields."""
        # Missing alias
        response = client_with_mock_auth.post(
            "/api/v1/providers", json={"provider_key": "schwab"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Missing provider_key
        response = client_with_mock_auth.post(
            "/api/v1/providers", json={"alias": "Test"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_provider_invalid_json(self, client_with_mock_auth: TestClient):
        """Test creating provider with invalid JSON."""
        response = client_with_mock_auth.post(
            "/api/v1/providers",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_get_provider_invalid_uuid(self, client_with_mock_auth: TestClient):
        """Test getting provider with invalid UUID format."""
        response = client_with_mock_auth.get("/api/v1/providers/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_provider_empty_alias(self, client_with_mock_auth: TestClient):
        """Test creating provider with empty alias is rejected."""
        payload = {"provider_key": "schwab", "alias": ""}

        response = client_with_mock_auth.post("/api/v1/providers", json=payload)

        # Empty alias should be rejected by validation (min_length=1)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestProviderResponseStructure:
    """Test suite for response structure validation."""

    def test_provider_response_has_all_fields(
        self, client_with_mock_auth: TestClient, test_provider_with_connection
    ):
        """Test that provider response includes all expected fields."""
        response = client_with_mock_auth.get(
            f"/api/v1/providers/{test_provider_with_connection.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Required fields
        required_fields = [
            "id",
            "provider_key",
            "alias",
            "status",
            "is_connected",
            "needs_reconnection",
            "accounts_count",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Optional fields (may be None)
        optional_fields = ["connected_at", "last_sync_at"]
        for field in optional_fields:
            assert field in data, f"Missing field: {field}"

    def test_provider_list_response_structure(self, client_with_mock_auth: TestClient):
        """Test that provider list returns correctly structured paginated data."""
        response = client_with_mock_auth.get("/api/v1/providers/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify paginated response structure
        assert isinstance(data, dict)
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data
        assert "has_next" in data
        assert "has_prev" in data

        # If any providers exist, check item structure
        if data["items"]:
            provider = data["items"][0]
            assert "id" in provider
            assert "provider_key" in provider
            assert "alias" in provider
            assert "status" in provider


class TestProviderUpdate:
    """Test suite for PATCH /providers/{id} endpoint."""

    def test_update_provider_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test successfully updating provider alias."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Original Name"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        # Update alias
        payload = {"alias": "Updated Name"}
        response = client_with_mock_auth.patch(
            f"/api/v1/providers/{provider.id}", json=payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["alias"] == "Updated Name"
        assert data["id"] == str(provider.id)
        assert data["provider_key"] == "schwab"

    def test_update_provider_same_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test updating provider with same alias (no-op)."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="My Account"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        # Update with same alias
        payload = {"alias": "My Account"}
        response = client_with_mock_auth.patch(
            f"/api/v1/providers/{provider.id}", json=payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["alias"] == "My Account"

    def test_update_provider_duplicate_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test updating provider with alias that already exists."""
        # Create two providers
        provider1 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Account 1"
        )
        provider2 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Account 2"
        )
        db_session.add(provider1)
        db_session.add(provider2)
        db_session.commit()

        # Try to update provider2 with provider1's alias
        payload = {"alias": "Account 1"}
        response = client_with_mock_auth.patch(
            f"/api/v1/providers/{provider2.id}", json=payload
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already have a provider" in response.json()["detail"]

    def test_update_provider_not_found(self, client_with_mock_auth: TestClient):
        """Test updating non-existent provider returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        payload = {"alias": "New Name"}
        response = client_with_mock_auth.patch(
            f"/api/v1/providers/{fake_uuid}", json=payload
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_provider_empty_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test updating provider with empty alias is rejected."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Original"
        )
        db_session.add(provider)
        db_session.commit()

        # Try to update with empty alias
        payload = {"alias": ""}
        response = client_with_mock_auth.patch(
            f"/api/v1/providers/{provider.id}", json=payload
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_update_provider_missing_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test updating provider without alias field is rejected."""
        # Create test provider
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Original"
        )
        db_session.add(provider)
        db_session.commit()

        # Try to update with no payload
        response = client_with_mock_auth.patch(
            f"/api/v1/providers/{provider.id}", json={}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_update_provider_invalid_uuid(self, client_with_mock_auth: TestClient):
        """Test updating provider with invalid UUID format."""
        payload = {"alias": "New Name"}
        response = client_with_mock_auth.patch(
            "/api/v1/providers/not-a-uuid", json=payload
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
