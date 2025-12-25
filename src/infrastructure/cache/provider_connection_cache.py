"""Redis implementation of ProviderConnectionCache protocol.

Provides fast (<5ms) provider connection lookups via Redis caching.
Reduces database queries for connection status checks.

Key Patterns:
    - provider:conn:{connection_id} -> JSON serialized ProviderConnection

Architecture:
    - Implements ProviderConnectionCache protocol (structural typing)
    - Uses CacheProtocol for low-level Redis operations
    - Returns None on cache miss (fail-open for resilience)
    - Database is always source of truth

Reference:
    - docs/architecture/cache-key-patterns.md
"""

import logging
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from src.core.config import settings
from src.core.result import Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.protocols.cache_protocol import CacheProtocol
from src.domain.value_objects.provider_credentials import ProviderCredentials

logger = logging.getLogger(__name__)


class RedisProviderConnectionCache:
    """Redis implementation of ProviderConnectionCache protocol.

    Provides fast connection lookups to reduce database queries for
    connection status checks during account/transaction operations.

    Note: Does NOT inherit from ProviderConnectionCache protocol (uses structural typing).

    Key Patterns:
        - provider:conn:{connection_id} -> Full connection data (JSON)

    Attributes:
        _cache: Cache instance implementing CacheProtocol.
    """

    def __init__(self, cache: CacheProtocol) -> None:
        """Initialize provider connection cache.

        Args:
            cache: Cache instance implementing CacheProtocol.
        """
        self._cache = cache
        self._ttl = settings.cache_provider_ttl

    def _connection_key(self, connection_id: UUID) -> str:
        """Generate cache key for provider connection.

        Args:
            connection_id: Connection identifier.

        Returns:
            Cache key string.
        """
        return f"provider:conn:{connection_id}"

    async def get(self, connection_id: UUID) -> ProviderConnection | None:
        """Get provider connection from cache.

        Args:
            connection_id: Connection identifier.

        Returns:
            ProviderConnection if cached, None otherwise (cache miss or error).
        """
        key = self._connection_key(connection_id)
        result = await self._cache.get_json(key)

        match result:
            case Success(value=None):
                return None
            case Success(value=data) if data is not None:
                try:
                    return self._from_dict(data)
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(
                        "Failed to deserialize provider connection from cache",
                        extra={"connection_id": str(connection_id), "error": str(e)},
                    )
                    return None
            case _:
                # Cache error - fail open (return None)
                logger.warning(
                    "Cache error getting provider connection",
                    extra={"connection_id": str(connection_id)},
                )
                return None

    async def set(
        self,
        connection: ProviderConnection,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store provider connection in cache.

        Args:
            connection: Provider connection to cache.
            ttl_seconds: Cache TTL in seconds. If None, uses CACHE_PROVIDER_TTL.
        """
        if ttl_seconds is None:
            ttl_seconds = self._ttl

        key = self._connection_key(connection.id)
        data = self._to_dict(connection)

        result = await self._cache.set_json(key, data, ttl=ttl_seconds)
        if not isinstance(result, Success):
            logger.warning(
                "Failed to cache provider connection",
                extra={"connection_id": str(connection.id)},
            )

    async def delete(self, connection_id: UUID) -> bool:
        """Remove provider connection from cache.

        Args:
            connection_id: Connection identifier.

        Returns:
            True if deleted, False if not found or error.
        """
        key = self._connection_key(connection_id)
        result = await self._cache.delete(key)

        match result:
            case Success(value=deleted):
                return deleted
            case _:
                logger.warning(
                    "Cache error deleting provider connection",
                    extra={"connection_id": str(connection_id)},
                )
                return False

    async def exists(self, connection_id: UUID) -> bool:
        """Check if provider connection exists in cache.

        Args:
            connection_id: Connection identifier.

        Returns:
            True if connection exists in cache, False otherwise.
        """
        key = self._connection_key(connection_id)
        result = await self._cache.exists(key)

        match result:
            case Success(value=exists):
                return exists
            case _:
                return False

    # =========================================================================
    # Serialization helpers
    # =========================================================================

    def _to_dict(self, connection: ProviderConnection) -> dict[str, object]:
        """Convert ProviderConnection to dict for JSON serialization.

        Args:
            connection: ProviderConnection to convert.

        Returns:
            Dictionary representation.
        """
        data = asdict(connection)

        # Convert UUIDs to strings
        data["id"] = str(connection.id)
        data["user_id"] = str(connection.user_id)
        data["provider_id"] = str(connection.provider_id)

        # Convert ConnectionStatus enum to string
        data["status"] = connection.status.value

        # Convert credentials to dict (ProviderCredentials is a dataclass)
        if connection.credentials:
            # encrypted_data is bytes, convert to string for JSON
            encrypted_str = connection.credentials.encrypted_data.decode("utf-8")
            data["credentials"] = {
                "encrypted_data": encrypted_str,
                "credential_type": connection.credentials.credential_type.value,
                "expires_at": (
                    connection.credentials.expires_at.isoformat()
                    if connection.credentials.expires_at
                    else None
                ),
            }
        else:
            data["credentials"] = None

        # Convert datetimes to ISO strings
        for dt_field in ["connected_at", "last_sync_at", "created_at", "updated_at"]:
            if data.get(dt_field) is not None:
                data[dt_field] = data[dt_field].isoformat()

        return data

    def _from_dict(self, data: dict[str, object]) -> ProviderConnection:
        """Convert dict to ProviderConnection.

        Args:
            data: Dictionary from cache.

        Returns:
            ProviderConnection instance.

        Raises:
            KeyError: If required field missing.
            ValueError: If UUID or datetime parsing fails.
        """
        # Parse UUIDs
        connection_id = UUID(str(data["id"]))
        user_id = UUID(str(data["user_id"]))
        provider_id = UUID(str(data["provider_id"]))

        # Parse status enum
        status = ConnectionStatus(str(data["status"]))

        # Parse datetimes
        def parse_dt(val: object | None) -> datetime | None:
            if val is None:
                return None
            return datetime.fromisoformat(str(val))

        # Parse credentials if present
        credentials = None
        credentials_data = data.get("credentials")
        if credentials_data and isinstance(credentials_data, dict):
            expires_at = parse_dt(credentials_data.get("expires_at"))
            # encrypted_data is stored as string in JSON, convert back to bytes
            encrypted_bytes = str(credentials_data["encrypted_data"]).encode("utf-8")
            credential_type_value = str(credentials_data["credential_type"])
            credentials = ProviderCredentials(
                encrypted_data=encrypted_bytes,
                credential_type=CredentialType(credential_type_value),
                expires_at=expires_at,
            )

        # Extract optional fields
        alias = str(data["alias"]) if data.get("alias") else None

        return ProviderConnection(
            id=connection_id,
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=str(data["provider_slug"]),
            status=status,
            alias=alias,
            credentials=credentials,
            connected_at=parse_dt(data.get("connected_at")),
            last_sync_at=parse_dt(data.get("last_sync_at")),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
            updated_at=parse_dt(data.get("updated_at")) or datetime.now(),
        )
