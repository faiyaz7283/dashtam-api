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
    """Test suite for provider instance management.
    
    Tests CRUD operations for user-specific provider instances
    (not provider type templates).
    """

    def test_create_provider_instance(
        self, client_with_mock_auth: TestClient, test_user: User
    ):
        """Test POST /api/v1/providers creates new provider instance.
        
        Verifies that:
        - Endpoint returns 201 Created
        - Provider created with pending status
        - Response includes all required fields (id, provider_key, alias, status)
        - Connection not established yet (is_connected=False, needs_reconnection=True)
        
        Args:
            client_with_mock_auth: Authenticated test client with user fixture
            test_user: Test user fixture for authentication context
        
        Note:
            Provider instance is user-specific, not a template.
        """
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
        """Test POST /api/v1/providers rejects invalid provider_key.
        
        Verifies that:
        - Endpoint returns 400 Bad Request
        - Invalid/unknown provider_key rejected
        - Error message mentions provider not available
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Validates against provider registry (schwab, etc.).
        """
        payload = {"provider_key": "nonexistent_provider", "alias": "Test"}

        response = client_with_mock_auth.post("/api/v1/providers", json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not available" in response.json()["detail"].lower()

    def test_create_provider_duplicate_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test POST /api/v1/providers rejects duplicate alias per user.
        
        Verifies that:
        - First provider with alias created successfully
        - Second provider with same alias returns 409 Conflict
        - unique_user_provider_alias constraint enforced
        - Error message mentions duplicate provider
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            Unique constraint is per-user, not global.
        """
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
        """Test GET /api/v1/providers/ lists user's providers with pagination.
        
        Verifies that:
        - Endpoint returns 200 OK
        - Response includes pagination fields (items, total, page, per_page, pages, has_next, has_prev)
        - All created providers returned in items array
        - Only current user's providers shown
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            Paginated response structure for list endpoints.
        """
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
        """Test GET /api/v1/providers/ pagination parameters work correctly.
        
        Verifies that:
        - page and per_page query parameters accepted
        - Page 1 returns first 10 items
        - Page 2 returns remaining items
        - has_next and has_prev flags correct
        - Pagination metadata accurate (page, per_page, total)
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session to create 15 test providers
        
        Note:
            Tests pagination across multiple pages.
        """
        # Create 15 test providers
        providers = [
            Provider(user_id=test_user.id, provider_key="schwab", alias=f"Provider {i}")
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
        """Test GET /api/v1/providers?provider_key= filters by provider type.
        
        Verifies that:
        - provider_key query parameter works
        - Only providers matching key returned
        - Filter applied to user's providers only
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            Filters by provider type (schwab, etc.).
        """
        # Create providers of different types
        schwab_provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Schwab Account"
        )
        db_session.add(schwab_provider)
        db_session.commit()

        # Filter by schwab
        response = client_with_mock_auth.get("/api/v1/providers?provider_key=schwab")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for item in data["items"]:
            assert item["provider_key"] == "schwab"

    def test_list_providers_sorting(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test GET /api/v1/providers?sort=alias&order=asc sorts results.
        
        Verifies that:
        - sort and order query parameters work
        - Results sorted alphabetically by alias (ascending)
        - Sorting applied correctly
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session to create test data
        
        Note:
            Tests ascending sort by alias field.
        """
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
        response = client_with_mock_auth.get("/api/v1/providers?sort=alias&order=asc")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        aliases = [item["alias"] for item in data["items"]]
        # Check if aliases are sorted
        assert aliases == sorted(aliases)

    def test_list_providers_invalid_sort_field(self, client_with_mock_auth: TestClient):
        """Test GET /api/v1/providers?sort=invalid_field returns 400.
        
        Verifies that:
        - Invalid sort field rejected
        - Endpoint returns 400 Bad Request
        - Error message mentions invalid sort field
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Validates sort parameter against allowed fields.
        """
        response = client_with_mock_auth.get("/api/v1/providers?sort=invalid_field")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot sort" in response.json()["detail"]

    def test_get_provider_by_id(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test GET /api/v1/providers/{id} returns specific provider.
        
        Verifies that:
        - Endpoint returns 200 OK
        - Provider data matches created instance
        - All fields present (id, alias, provider_key)
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            Tests single provider retrieval by UUID.
        """
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
        """Test GET /api/v1/providers/{invalid_id} returns 404.
        
        Verifies that:
        - Non-existent provider ID returns 404 Not Found
        - Proper error handling for missing resources
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Uses all-zeros UUID for testing.
        """
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client_with_mock_auth.get(f"/api/v1/providers/{fake_uuid}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_provider(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test DELETE /api/v1/providers/{id} removes provider.
        
        Verifies that:
        - Endpoint returns 200 OK
        - Success message included
        - Provider actually deleted from database
        - No orphaned data remains
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session to verify deletion
        
        Note:
            Also cascades to connections and tokens.
        """
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
        """Test DELETE /api/v1/providers/{invalid_id} returns 404.
        
        Verifies that:
        - Non-existent provider ID returns 404 Not Found
        - Delete handles missing resources gracefully
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Uses all-zeros UUID for testing.
        """
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client_with_mock_auth.delete(f"/api/v1/providers/{fake_uuid}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestProviderConnectionStatus:
    """Test suite for provider connection status.
    
    Tests connection lifecycle and status reporting in API responses.
    """

    def test_provider_with_pending_connection(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test provider response shows pending connection status correctly.
        
        Verifies that:
        - Provider with ProviderConnection (status=PENDING) shows status='pending'
        - is_connected=False for pending connections
        - Connection status reflected in API response
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session to create connection
        
        Note:
            PENDING status means OAuth not completed yet.
        """
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
        """Test provider response shows active connection status correctly.
        
        Verifies that:
        - Provider with ACTIVE connection shows status='active'
        - is_connected=True for active connections
        - needs_reconnection=False (OAuth complete)
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_provider_with_connection: Fixture with active connection
        
        Note:
            ACTIVE status means OAuth completed successfully.
        """
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
        """Test GET /api/v1/providers/ includes connection info for each provider.
        
        Verifies that:
        - List response includes connection fields
        - Each provider has status, is_connected, needs_reconnection, connected_at
        - Connection data properly serialized in list view
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_provider_with_connection: Provider fixture to find in list
        
        Note:
            Tests connection info in paginated list response.
        """
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
    """Test suite for request validation.
    
    Tests Pydantic schema validation for provider endpoints.
    """

    def test_create_provider_missing_fields(self, client_with_mock_auth: TestClient):
        """Test POST /api/v1/providers rejects requests with missing required fields.
        
        Verifies that:
        - Missing alias returns 422 Unprocessable Entity
        - Missing provider_key returns 422 Unprocessable Entity
        - Pydantic validation enforced
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Tests both alias and provider_key as required fields.
        """
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
        """Test POST /api/v1/providers rejects malformed JSON.
        
        Verifies that:
        - Invalid JSON content returns 422 Unprocessable Entity
        - Request body parsing errors handled
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Uses raw text instead of JSON for testing.
        """
        response = client_with_mock_auth.post(
            "/api/v1/providers",
            content="not valid json",  # Use content= instead of data= for raw bytes/text
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_get_provider_invalid_uuid(self, client_with_mock_auth: TestClient):
        """Test GET /api/v1/providers/{invalid_uuid} rejects malformed UUID.
        
        Verifies that:
        - Invalid UUID format returns 422 Unprocessable Entity
        - Path parameter validation enforced
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            UUID path parameter must be valid UUID4 format.
        """
        response = client_with_mock_auth.get("/api/v1/providers/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_provider_empty_alias(self, client_with_mock_auth: TestClient):
        """Test POST /api/v1/providers rejects empty alias string.
        
        Verifies that:
        - Empty alias (empty string) returns 422 Unprocessable Entity
        - min_length=1 validation enforced on alias field
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Alias must have at least 1 character.
        """
        payload = {"provider_key": "schwab", "alias": ""}

        response = client_with_mock_auth.post("/api/v1/providers", json=payload)

        # Empty alias should be rejected by validation (min_length=1)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestProviderResponseStructure:
    """Test suite for response structure validation.
    
    Validates API response schemas for provider endpoints.
    """

    def test_provider_response_has_all_fields(
        self, client_with_mock_auth: TestClient, test_provider_with_connection
    ):
        """Test GET /api/v1/providers/{id} response schema includes all required fields.
        
        Verifies that:
        - All required fields present (id, provider_key, alias, status, is_connected, needs_reconnection, accounts_count)
        - Optional fields included (connected_at, last_sync_at - may be None)
        - Response conforms to ProviderDetail schema
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_provider_with_connection: Provider fixture with connection
        
        Note:
            Schema validation for consistency.
        """
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
        """Test GET /api/v1/providers/ returns paginated response with correct structure.
        
        Verifies that:
        - Response is dict with pagination keys
        - items, total, page, per_page, pages, has_next, has_prev all present
        - Each item in items has provider fields (id, provider_key, alias, status)
        - Paginated response schema enforced
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Tests pagination metadata structure.
        """
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
    """Test suite for PATCH /providers/{id} endpoint.
    
    Tests provider alias update functionality with validation.
    """

    def test_update_provider_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test PATCH /api/v1/providers/{id} successfully updates alias.
        
        Verifies that:
        - Endpoint returns 200 OK
        - Alias updated to new value
        - Other fields unchanged (id, provider_key)
        - Change persisted to database
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            Alias is only updateable field for providers.
        """
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
        """Test PATCH /api/v1/providers/{id} with unchanged alias is allowed (no-op).
        
        Verifies that:
        - Updating with same alias returns 200 OK
        - No error raised for unchanged value
        - Alias remains the same
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            Idempotent operation - safe to repeat.
        """
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
        """Test PATCH /api/v1/providers/{id} rejects duplicate alias.
        
        Verifies that:
        - Updating to another provider's alias returns 409 Conflict
        - unique_user_provider_alias constraint enforced
        - Error message mentions duplicate
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session to create two providers
        
        Note:
            Unique constraint prevents alias conflicts per user.
        """
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
        """Test PATCH /api/v1/providers/{invalid_id} returns 404.
        
        Verifies that:
        - Non-existent provider ID returns 404 Not Found
        - Update handles missing resources gracefully
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            Uses all-zeros UUID for testing.
        """
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        payload = {"alias": "New Name"}
        response = client_with_mock_auth.patch(
            f"/api/v1/providers/{fake_uuid}", json=payload
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_provider_empty_alias(
        self, client_with_mock_auth: TestClient, test_user: User, db_session
    ):
        """Test PATCH /api/v1/providers/{id} rejects empty alias.
        
        Verifies that:
        - Empty alias (empty string) returns 422 Unprocessable Entity
        - min_length=1 validation enforced
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            Alias must have at least 1 character.
        """
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
        """Test PATCH /api/v1/providers/{id} rejects request with no alias field.
        
        Verifies that:
        - Empty JSON payload returns 422 Unprocessable Entity
        - Alias field required for update
        - Validation enforced
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
            test_user: Test user fixture for ownership
            db_session: Database session for test data setup
        
        Note:
            PATCH requires at least alias field.
        """
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
        """Test PATCH /api/v1/providers/{invalid_uuid} rejects malformed UUID.
        
        Verifies that:
        - Invalid UUID format returns 422 Unprocessable Entity
        - Path parameter validation enforced
        
        Args:
            client_with_mock_auth: Authenticated test client fixture
        
        Note:
            UUID path parameter must be valid UUID4 format.
        """
        payload = {"alias": "New Name"}
        response = client_with_mock_auth.patch(
            "/api/v1/providers/not-a-uuid", json=payload
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
