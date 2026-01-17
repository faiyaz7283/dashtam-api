"""API tests for file import endpoints.

Tests the complete HTTP request/response cycle for file imports:
- POST /api/v1/imports (import from file)
- GET /api/v1/imports/formats (list supported formats)

Architecture:
- Uses FastAPI TestClient with real app + dependency overrides
- Tests validation, authorization, and RFC 9457 error responses
- Mocks handlers to test HTTP layer behavior
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.application.commands.handlers.import_from_file_handler import (
    ImportFromFileHandler,
)
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles (matching actual application DTOs)
# =============================================================================


@dataclass
class MockImportResult:
    """Mock DTO matching ImportResult from import_from_file_handler.py."""

    connection_id: UUID
    accounts_created: int
    accounts_updated: int
    transactions_created: int
    transactions_skipped: int
    message: str


class MockImportFromFileHandler:
    """Mock handler for file imports."""

    def __init__(
        self,
        result: MockImportResult | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result
        self._error = error

    async def handle(self, command: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._result)


# =============================================================================
# Authentication Mock
# =============================================================================


@dataclass
class MockCurrentUser:
    """Mock user for auth override."""

    user_id: UUID
    email: str = "test@example.com"
    roles: list[str] | None = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = ["user"]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user_id():
    """Provide consistent user ID for tests."""
    return uuid7()


@pytest.fixture
def mock_connection_id():
    """Provide consistent connection ID for tests."""
    return uuid7()


@pytest.fixture
def mock_import_result(mock_connection_id):
    """Create a mock import result."""
    return MockImportResult(
        connection_id=mock_connection_id,
        accounts_created=1,
        accounts_updated=0,
        transactions_created=15,
        transactions_skipped=0,
        message="Imported from test.qfx: 1 accounts created, 0 updated, 15 transactions imported, 0 skipped",
    )


@pytest.fixture(autouse=True)
def override_auth(mock_user_id):
    """Override authentication for all tests."""
    from src.presentation.routers.api.middleware.auth_dependencies import (
        get_current_user,
    )

    mock_user = MockCurrentUser(user_id=mock_user_id)

    async def mock_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    """Provide test client."""
    return TestClient(app)


@pytest.fixture
def sample_qfx_content():
    """Provide sample QFX file content for tests."""
    return b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20241215120000
<LANGUAGE>ENG
<FI>
<ORG>Chase
<FID>10898
</FI>
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>0
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<BANKID>021000021
<ACCTID>123456789
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20241101
<DTEND>20241215
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20241210
<TRNAMT>-50.00
<FITID>TEST123456
<NAME>TEST PURCHASE
<MEMO>Test transaction
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>1000.00
<DTASOF>20241215
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""


# =============================================================================
# GET /api/v1/imports/formats Tests
# =============================================================================


@pytest.mark.api
class TestListSupportedFormats:
    """Test GET /api/v1/imports/formats endpoint."""

    def test_list_formats_returns_supported_formats(self, client):
        """Test listing supported file formats returns QFX and OFX."""
        # Act
        response = client.get("/api/v1/imports/formats")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "formats" in data
        formats = data["formats"]
        assert len(formats) >= 2

        # Check QFX format
        qfx_format = next((f for f in formats if f["format"] == "qfx"), None)
        assert qfx_format is not None
        assert qfx_format["name"] == "Quicken Financial Exchange"
        assert ".qfx" in qfx_format["extensions"]
        assert "chase_file" in qfx_format["provider_slugs"]

        # Check OFX format
        ofx_format = next((f for f in formats if f["format"] == "ofx"), None)
        assert ofx_format is not None
        assert ofx_format["name"] == "Open Financial Exchange"
        assert ".ofx" in ofx_format["extensions"]

    def test_list_formats_requires_no_auth(self, client, override_auth):
        """Test formats endpoint is accessible (auth applied but not strictly required)."""
        # Note: Auth is applied via autouse fixture, but endpoint should work
        response = client.get("/api/v1/imports/formats")
        assert response.status_code == 200


# =============================================================================
# POST /api/v1/imports Tests
# =============================================================================


@pytest.mark.api
class TestImportFromFile:
    """Test POST /api/v1/imports endpoint."""

    def test_import_qfx_file_success(
        self, client, mock_import_result, sample_qfx_content
    ):
        """Test successful QFX file import."""
        # Arrange - mock handler using handler_factory key
        mock_handler = MockImportFromFileHandler(result=mock_import_result)
        factory_key = handler_factory(ImportFromFileHandler)
        app.dependency_overrides[factory_key] = lambda: mock_handler

        try:
            # Act
            response = client.post(
                "/api/v1/imports",
                files={
                    "file": (
                        "test.qfx",
                        BytesIO(sample_qfx_content),
                        "application/octet-stream",
                    )
                },
            )

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["accounts_created"] == 1
            assert data["accounts_updated"] == 0
            assert data["transactions_created"] == 15
            assert data["transactions_skipped"] == 0
            assert "connection_id" in data
        finally:
            app.dependency_overrides.pop(factory_key, None)

    def test_import_ofx_file_success(
        self, client, mock_import_result, sample_qfx_content
    ):
        """Test successful OFX file import (same format as QFX)."""
        # Arrange - mock handler using handler_factory key
        mock_handler = MockImportFromFileHandler(result=mock_import_result)
        factory_key = handler_factory(ImportFromFileHandler)
        app.dependency_overrides[factory_key] = lambda: mock_handler

        try:
            # Act - use .ofx extension
            response = client.post(
                "/api/v1/imports",
                files={
                    "file": (
                        "test.ofx",
                        BytesIO(sample_qfx_content),
                        "application/octet-stream",
                    )
                },
            )

            # Assert
            assert response.status_code == 201
        finally:
            app.dependency_overrides.pop(factory_key, None)

    def test_import_unsupported_format_returns_415(self, client):
        """Test importing unsupported file format returns 415."""
        # Act
        response = client.post(
            "/api/v1/imports",
            files={"file": ("test.csv", BytesIO(b"col1,col2\nval1,val2"), "text/csv")},
        )

        # Assert
        assert response.status_code == 415
        data = response.json()
        assert "Unsupported file format" in data["detail"]
        assert ".csv" in data["detail"]

    def test_import_empty_file_returns_400(self, client):
        """Test importing empty file returns 400."""
        # Act
        response = client.post(
            "/api/v1/imports",
            files={"file": ("empty.qfx", BytesIO(b""), "application/octet-stream")},
        )

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "Empty file" in data["detail"]

    def test_import_invalid_file_returns_400(self, client):
        """Test importing invalid/unparseable file returns 400."""
        # Arrange - handler returns parse error
        mock_handler = MockImportFromFileHandler(
            error="Invalid or unparseable file: Failed to parse QFX file"
        )
        factory_key = handler_factory(ImportFromFileHandler)
        app.dependency_overrides[factory_key] = lambda: mock_handler

        try:
            # Act
            response = client.post(
                "/api/v1/imports",
                files={
                    "file": (
                        "bad.qfx",
                        BytesIO(b"not valid qfx"),
                        "application/octet-stream",
                    )
                },
            )

            # Assert
            assert response.status_code == 400
            data = response.json()
            assert (
                "invalid" in data["detail"].lower()
                or "unparseable" in data["detail"].lower()
            )
        finally:
            app.dependency_overrides.pop(factory_key, None)

    def test_import_no_accounts_returns_400(self, client):
        """Test file with no account data returns 400."""
        # Arrange
        mock_handler = MockImportFromFileHandler(error="File contains no account data")
        factory_key = handler_factory(ImportFromFileHandler)
        app.dependency_overrides[factory_key] = lambda: mock_handler

        try:
            # Act
            response = client.post(
                "/api/v1/imports",
                files={
                    "file": (
                        "empty_data.qfx",
                        BytesIO(b"<OFX></OFX>"),
                        "application/octet-stream",
                    )
                },
            )

            # Assert
            assert response.status_code == 400
            data = response.json()
            assert "no account" in data["detail"].lower()
        finally:
            app.dependency_overrides.pop(factory_key, None)

    def test_import_requires_authentication(self, client):
        """Test import endpoint requires authentication."""
        from src.presentation.routers.api.middleware.auth_dependencies import (
            get_current_user,
        )

        # Remove auth override to simulate unauthenticated request
        app.dependency_overrides.pop(get_current_user, None)

        try:
            # Act
            response = client.post(
                "/api/v1/imports",
                files={
                    "file": ("test.qfx", BytesIO(b"test"), "application/octet-stream")
                },
            )

            # Assert - should get 401 or 403
            assert response.status_code in [401, 403, 422]
        finally:
            # Restore for other tests (autouse fixture will handle next test)
            pass

    def test_import_file_without_extension_returns_415(self, client):
        """Test file without extension returns 415."""
        # Act
        response = client.post(
            "/api/v1/imports",
            files={
                "file": ("noextension", BytesIO(b"data"), "application/octet-stream")
            },
        )

        # Assert
        assert response.status_code == 415

    def test_import_case_insensitive_extension(
        self, client, mock_import_result, sample_qfx_content
    ):
        """Test file extension matching is case-insensitive."""
        # Arrange
        mock_handler = MockImportFromFileHandler(result=mock_import_result)
        factory_key = handler_factory(ImportFromFileHandler)
        app.dependency_overrides[factory_key] = lambda: mock_handler

        try:
            # Act - uppercase extension
            response = client.post(
                "/api/v1/imports",
                files={
                    "file": (
                        "test.QFX",
                        BytesIO(sample_qfx_content),
                        "application/octet-stream",
                    )
                },
            )

            # Assert
            assert response.status_code == 201
        finally:
            app.dependency_overrides.pop(factory_key, None)


# =============================================================================
# Response Schema Validation Tests
# =============================================================================


@pytest.mark.api
class TestImportResponseSchema:
    """Test import response matches expected schema."""

    def test_success_response_contains_all_fields(
        self, client, mock_import_result, sample_qfx_content
    ):
        """Test successful import response contains all required fields."""
        mock_handler = MockImportFromFileHandler(result=mock_import_result)
        factory_key = handler_factory(ImportFromFileHandler)
        app.dependency_overrides[factory_key] = lambda: mock_handler

        try:
            response = client.post(
                "/api/v1/imports",
                files={
                    "file": (
                        "test.qfx",
                        BytesIO(sample_qfx_content),
                        "application/octet-stream",
                    )
                },
            )

            assert response.status_code == 201
            data = response.json()

            # Verify all expected fields present
            assert "connection_id" in data
            assert "accounts_created" in data
            assert "accounts_updated" in data
            assert "transactions_created" in data
            assert "transactions_skipped" in data
            assert "message" in data

            # Verify types
            assert isinstance(data["accounts_created"], int)
            assert isinstance(data["accounts_updated"], int)
            assert isinstance(data["transactions_created"], int)
            assert isinstance(data["transactions_skipped"], int)
            assert isinstance(data["message"], str)
        finally:
            app.dependency_overrides.pop(factory_key, None)

    def test_error_response_is_rfc7807_compliant(self, client):
        """Test error responses follow RFC 9457 Problem Details format."""
        # Act - trigger 415 error
        response = client.post(
            "/api/v1/imports",
            files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
        )

        # Assert
        assert response.status_code == 415
        data = response.json()

        # RFC 9457 required fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data

        # Verify values
        assert data["status"] == 415
        assert data["instance"] == "/api/v1/imports"
