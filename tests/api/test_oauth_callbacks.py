import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.core.result import Success, Failure
from src.domain.enums.credential_type import CredentialType
from src.domain.entities.provider import Provider as ProviderEntity
from uuid_extensions import uuid7


# ---- Test doubles ----


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get_json(self, key: str):
        v = self._store.get(key)
        return (
            Success(value=v)
            if v is not None
            else Failure(error=ValueError("not found"))
        )

    async def set_json(self, key: str, value: Any, ttl: int | None = None):
        self._store[key] = value
        return Success(value=True)

    async def delete(self, key: str):
        self._store.pop(key, None)
        return Success(value=True)


@dataclass
class StubTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str
    scope: str | None = None


class StubProvider:
    slug = "schwab"

    async def exchange_code_for_tokens(self, authorization_code: str):
        return Success(
            value=StubTokens(
                access_token="at",
                refresh_token="rt",
                expires_in=1800,
                token_type="Bearer",
                scope="api",
            )
        )


class StubEncryptionService:
    def encrypt(self, data: dict):
        return Success(value=b"encrypted")


class StubConnectProviderHandler:
    async def handle(self, cmd):
        return Success(value=None)


class StubProviderRepository:
    def __init__(self, provider_id: UUID | None = None) -> None:
        self._id = provider_id or uuid7()

    async def find_by_slug(self, slug: str):
        return ProviderEntity(
            id=self._id,
            slug="schwab",
            name="Charles Schwab",
            credential_type=CredentialType.OAUTH2,
        )


# ---- Dependency overrides ----
@pytest.fixture(autouse=True)
def _override_dependencies(monkeypatch):
    # Cache
    cache = InMemoryCache()

    def _get_cache_override():
        return cache

    app.dependency_overrides.clear()

    from src.core.container import get_cache as real_get_cache

    app.dependency_overrides[real_get_cache] = _get_cache_override

    # Encryption
    from src.core.container import get_encryption_service as real_get_enc

    def _get_enc_override():
        return StubEncryptionService()

    app.dependency_overrides[real_get_enc] = _get_enc_override

    # Connect handler
    from src.core.container import get_connect_provider_handler as real_get_handler

    def _get_handler_override():
        return StubConnectProviderHandler()

    app.dependency_overrides[real_get_handler] = _get_handler_override

    # Provider repo
    repo = StubProviderRepository()
    from src.core.container import get_provider_repository as real_get_repo

    async def _get_repo_override():
        return repo

    app.dependency_overrides[real_get_repo] = _get_repo_override

    # Monkeypatch get_provider function used directly in router
    import src.presentation.routers.oauth_callbacks as cb

    def _get_provider_stub(slug: str):
        return StubProvider()

    monkeypatch.setattr(cb, "get_provider", _get_provider_stub)

    yield cache  # Expose cache to tests

    app.dependency_overrides.clear()


def _set_state(cache: InMemoryCache, state: str, user_id: UUID):
    key = f"oauth:state:{state}"
    data = {
        "user_id": str(user_id),
        "provider_slug": "schwab",
        "created_at": datetime.now(UTC).isoformat(),
    }
    asyncio.run(cache.set_json(key, data, ttl=600))


def test_callback_missing_code_returns_400(_override_dependencies):
    client = TestClient(app)
    resp = client.get("/oauth/schwab/callback", params={"state": "s"})
    assert resp.status_code == 400
    assert "Missing Authorization Code" in resp.text


def test_callback_invalid_state_returns_400(_override_dependencies):
    client = TestClient(app)
    resp = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "invalid"}
    )
    assert resp.status_code == 400
    assert "Invalid or Expired State" in resp.text


def test_callback_success_creates_connection(_override_dependencies):
    cache: InMemoryCache = _override_dependencies  # from fixture yield
    client = TestClient(app)
    user_id = uuid7()
    _set_state(cache, state="valid", user_id=user_id)

    resp = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "valid"}
    )
    assert resp.status_code == 200
    assert "Connection Successful" in resp.text


def test_callback_provider_mismatch_returns_400(_override_dependencies):
    """State was created for different provider than URL slug."""
    cache: InMemoryCache = _override_dependencies
    client = TestClient(app)
    user_id = uuid7()
    # Set state for a different provider
    key = "oauth:state:mismatch"
    data = {
        "user_id": str(user_id),
        "provider_slug": "chase",  # Different from URL's "schwab"
        "created_at": datetime.now(UTC).isoformat(),
    }
    asyncio.run(cache.set_json(key, data, ttl=600))

    resp = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "mismatch"}
    )
    assert resp.status_code == 400
    assert "Provider Mismatch" in resp.text


def test_callback_state_consumed_on_success(_override_dependencies):
    """After successful callback, state should be deleted from cache."""
    cache: InMemoryCache = _override_dependencies
    client = TestClient(app)
    user_id = uuid7()
    _set_state(cache, state="consume_test", user_id=user_id)

    # First request succeeds
    resp = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "consume_test"}
    )
    assert resp.status_code == 200

    # Second request with same state should fail (state consumed)
    resp2 = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "consume_test"}
    )
    assert resp2.status_code == 400
    assert "Invalid or Expired State" in resp2.text


# ---- Error scenario tests with custom stubs ----


def test_callback_provider_token_exchange_failure(monkeypatch, _override_dependencies):
    """Provider fails to exchange code for tokens."""
    cache: InMemoryCache = _override_dependencies
    client = TestClient(app)
    user_id = uuid7()
    _set_state(cache, state="token_fail", user_id=user_id)

    @dataclass
    class ProviderError:
        message: str

    class FailingProvider:
        slug = "schwab"

        async def exchange_code_for_tokens(self, authorization_code: str):
            return Failure(error=ProviderError(message="Invalid authorization code"))

    import src.presentation.routers.oauth_callbacks as cb

    monkeypatch.setattr(cb, "get_provider", lambda slug: FailingProvider())

    resp = client.get(
        "/oauth/schwab/callback", params={"code": "bad", "state": "token_fail"}
    )
    assert resp.status_code == 400
    assert "Token Exchange Failed" in resp.text


def test_callback_encryption_failure(monkeypatch, _override_dependencies):
    """Encryption service fails to encrypt credentials."""
    cache: InMemoryCache = _override_dependencies
    client = TestClient(app)
    user_id = uuid7()
    _set_state(cache, state="encrypt_fail", user_id=user_id)

    class FailingEncryption:
        def encrypt(self, data: dict):
            return Failure(error=ValueError("Encryption hardware failure"))

    from src.core.container import get_encryption_service as real_get_enc

    app.dependency_overrides[real_get_enc] = lambda: FailingEncryption()

    resp = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "encrypt_fail"}
    )
    assert resp.status_code == 500
    assert "Encryption Failed" in resp.text


def test_callback_handler_failure(monkeypatch, _override_dependencies):
    """ConnectProviderHandler fails to persist connection."""
    cache: InMemoryCache = _override_dependencies
    client = TestClient(app)
    user_id = uuid7()
    _set_state(cache, state="handler_fail", user_id=user_id)

    class FailingHandler:
        async def handle(self, cmd):
            return Failure(error=ValueError("Database connection lost"))

    from src.core.container import get_connect_provider_handler as real_get_handler

    app.dependency_overrides[real_get_handler] = lambda: FailingHandler()

    resp = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "handler_fail"}
    )
    assert resp.status_code == 500
    assert "Connection Failed" in resp.text


# ---- Dynamic route tests: /oauth/{provider_slug}/callback ----


def _set_state_for_provider(
    cache: InMemoryCache, state: str, user_id: UUID, provider_slug: str
):
    """Helper to set state with arbitrary provider_slug."""
    key = f"oauth:state:{state}"
    data = {
        "user_id": str(user_id),
        "provider_slug": provider_slug,
        "created_at": datetime.now(UTC).isoformat(),
    }
    asyncio.run(cache.set_json(key, data, ttl=600))


def test_dynamic_callback_success(_override_dependencies):
    """Test dynamic route /oauth/{provider_slug}/callback with schwab."""
    cache: InMemoryCache = _override_dependencies
    client = TestClient(app)
    user_id = uuid7()
    _set_state_for_provider(
        cache, state="dyn_valid", user_id=user_id, provider_slug="schwab"
    )

    # Use the dynamic route with schwab
    resp = client.get(
        "/oauth/schwab/callback", params={"code": "abc", "state": "dyn_valid"}
    )
    assert resp.status_code == 200
    assert "Connection Successful" in resp.text


def test_dynamic_callback_missing_code(_override_dependencies):
    """Test dynamic route returns 400 for missing code."""
    client = TestClient(app)
    resp = client.get("/oauth/fidelity/callback", params={"state": "some_state"})
    assert resp.status_code == 400
    assert "Missing Authorization Code" in resp.text


def test_dynamic_callback_invalid_state(_override_dependencies):
    """Test dynamic route returns 400 for invalid state."""
    client = TestClient(app)
    resp = client.get(
        "/oauth/fidelity/callback", params={"code": "abc", "state": "bad_state"}
    )
    assert resp.status_code == 400
    assert "Invalid or Expired State" in resp.text


def test_dynamic_callback_provider_mismatch(_override_dependencies):
    """Test dynamic route returns 400 when URL slug doesn't match state's provider."""
    cache: InMemoryCache = _override_dependencies
    client = TestClient(app)
    user_id = uuid7()
    # State is for 'schwab' but we hit /oauth/fidelity/callback
    _set_state_for_provider(
        cache, state="dyn_mismatch", user_id=user_id, provider_slug="schwab"
    )

    resp = client.get(
        "/oauth/fidelity/callback", params={"code": "abc", "state": "dyn_mismatch"}
    )
    assert resp.status_code == 400
    assert "Provider Mismatch" in resp.text


def test_dynamic_callback_oauth_error_from_provider(_override_dependencies):
    """Test dynamic route handles OAuth error from provider (e.g., user denied)."""
    client = TestClient(app)
    resp = client.get(
        "/oauth/schwab/callback",
        params={"error": "access_denied", "error_description": "User denied access"},
    )
    assert resp.status_code == 400
    assert "Authorization Denied" in resp.text
    assert "User denied access" in resp.text
