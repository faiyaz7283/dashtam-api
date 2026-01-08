"""Unit tests for container infrastructure module.

Tests cover:
- get_cache() Redis adapter singleton pattern and protocol compliance
- get_event_bus() event bus singleton and handler subscriptions
- get_encryption_service() encryption service singleton
- Backend selection based on environment variables

Architecture:
- Unit tests with mocked infrastructure dependencies
- Tests centralized dependency injection pattern
- Validates protocol compliance for all factories

Note:
    get_cache() and get_event_bus() use local imports inside the function,
    so we must patch at the actual import location (e.g., redis.asyncio.ConnectionPool)
    not at the container module level.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.core.container import get_cache, get_encryption_service, get_event_bus
from src.domain.protocols.cache_protocol import CacheProtocol


@pytest.mark.unit
class TestGetCacheContainer:
    """Test get_cache() container function."""

    def test_get_cache_returns_redis_adapter(self):
        """Test get_cache() returns RedisAdapter instance."""
        get_cache.cache_clear()

        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            # Patch at actual import location (inside get_cache function)
            with patch("redis.asyncio.ConnectionPool") as mock_pool_cls:
                with patch("redis.asyncio.Redis") as mock_redis_cls:
                    with patch(
                        "src.infrastructure.cache.redis_adapter.RedisAdapter"
                    ) as mock_adapter_cls:
                        mock_pool = MagicMock()
                        mock_pool_cls.from_url.return_value = mock_pool

                        mock_redis = MagicMock()
                        mock_redis_cls.return_value = mock_redis

                        mock_adapter = MagicMock()
                        mock_adapter_cls.return_value = mock_adapter

                        cache = get_cache()

                        # Should create connection pool from redis_url
                        mock_pool_cls.from_url.assert_called_once()
                        call_args = mock_pool_cls.from_url.call_args
                        assert call_args[0][0] == "redis://localhost:6379/0"
                        assert call_args[1]["max_connections"] == 50

                        # Should create Redis client with pool
                        mock_redis_cls.assert_called_once_with(
                            connection_pool=mock_pool
                        )

                        # Should create RedisAdapter with Redis client
                        mock_adapter_cls.assert_called_once_with(
                            redis_client=mock_redis
                        )

                        assert cache == mock_adapter

    def test_get_cache_uses_singleton_pattern(self):
        """Test get_cache() returns same instance on multiple calls."""
        get_cache.cache_clear()

        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            with patch("redis.asyncio.ConnectionPool"):
                with patch("redis.asyncio.Redis"):
                    with patch(
                        "src.infrastructure.cache.redis_adapter.RedisAdapter"
                    ) as mock_adapter_cls:
                        mock_adapter = MagicMock()
                        mock_adapter_cls.return_value = mock_adapter

                        # Call multiple times
                        cache1 = get_cache()
                        cache2 = get_cache()
                        cache3 = get_cache()

                        # Should only create once (singleton)
                        assert mock_adapter_cls.call_count == 1
                        assert cache1 is cache2
                        assert cache2 is cache3

    def test_get_cache_returns_protocol_compliant_adapter(self):
        """Test get_cache() returns CacheProtocol-compliant adapter."""
        get_cache.cache_clear()

        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            with patch("redis.asyncio.ConnectionPool"):
                with patch("redis.asyncio.Redis"):
                    with patch(
                        "src.infrastructure.cache.redis_adapter.RedisAdapter"
                    ) as mock_adapter_cls:
                        # Create mock adapter with protocol methods
                        mock_adapter = MagicMock(spec=CacheProtocol)
                        mock_adapter_cls.return_value = mock_adapter

                        cache = get_cache()

                        # Verify protocol methods exist
                        assert hasattr(cache, "get")
                        assert hasattr(cache, "set")
                        assert hasattr(cache, "delete")
                        assert hasattr(cache, "exists")

    def test_get_cache_configures_connection_pooling(self):
        """Test get_cache() configures Redis connection pool correctly."""
        get_cache.cache_clear()

        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            with patch("redis.asyncio.ConnectionPool") as mock_pool_cls:
                with patch("redis.asyncio.Redis"):
                    with patch("src.infrastructure.cache.redis_adapter.RedisAdapter"):
                        get_cache()

                        # Verify connection pool configuration
                        call_kwargs = mock_pool_cls.from_url.call_args[1]
                        assert call_kwargs["max_connections"] == 50
                        assert call_kwargs["decode_responses"] is False
                        assert call_kwargs["socket_connect_timeout"] == 5
                        assert call_kwargs["socket_timeout"] == 5
                        assert call_kwargs["retry_on_timeout"] is True
                        assert call_kwargs["socket_keepalive"] is True


@pytest.mark.unit
class TestGetEventBusContainer:
    """Test get_event_bus() container function."""

    def test_get_event_bus_returns_in_memory_by_default(self):
        """Test get_event_bus() returns InMemoryEventBus by default."""
        get_event_bus.cache_clear()
        from src.core.container import get_database, get_logger

        get_logger.cache_clear()
        get_database.cache_clear()

        with patch.dict(os.environ, {}, clear=False):
            # Remove EVENT_BUS_TYPE if set
            os.environ.pop("EVENT_BUS_TYPE", None)

            # Patch at actual import locations inside get_event_bus
            with patch(
                "src.core.container.infrastructure.get_logger"
            ) as mock_get_logger:
                with patch(
                    "src.core.container.infrastructure.get_database"
                ) as mock_get_database:
                    with patch("src.core.config.get_settings") as mock_get_settings:
                        with patch(
                            "src.infrastructure.events.in_memory_event_bus.InMemoryEventBus"
                        ) as mock_bus_cls:
                            with patch(
                                "src.infrastructure.events.handlers.logging_event_handler.LoggingEventHandler"
                            ):
                                with patch(
                                    "src.infrastructure.events.handlers.audit_event_handler.AuditEventHandler"
                                ):
                                    with patch(
                                        "src.infrastructure.events.handlers.email_event_handler.EmailEventHandler"
                                    ):
                                        with patch(
                                            "src.infrastructure.events.handlers.session_event_handler.SessionEventHandler"
                                        ):
                                            mock_logger = MagicMock()
                                            mock_get_logger.return_value = mock_logger

                                            mock_db = MagicMock()
                                            mock_get_database.return_value = mock_db

                                            mock_settings = MagicMock()
                                            mock_get_settings.return_value = (
                                                mock_settings
                                            )

                                            mock_bus = MagicMock()
                                            mock_bus_cls.return_value = mock_bus

                                            event_bus = get_event_bus()

                                            # Should create InMemoryEventBus with logger
                                            mock_bus_cls.assert_called_once_with(
                                                logger=mock_logger
                                            )
                                            assert event_bus == mock_bus

    def test_get_event_bus_raises_for_unsupported_type(self):
        """Test get_event_bus() raises ValueError for unsupported type."""
        get_event_bus.cache_clear()

        with patch.dict(os.environ, {"EVENT_BUS_TYPE": "unknown"}):
            with pytest.raises(ValueError) as exc_info:
                get_event_bus()

            assert "Unsupported EVENT_BUS_TYPE: unknown" in str(exc_info.value)

    def test_get_event_bus_uses_singleton_pattern(self):
        """Test get_event_bus() returns same instance on multiple calls."""
        get_event_bus.cache_clear()
        from src.core.container import get_database, get_logger

        get_logger.cache_clear()
        get_database.cache_clear()

        with patch.dict(os.environ, {"EVENT_BUS_TYPE": "in-memory"}):
            with patch(
                "src.core.container.infrastructure.get_logger"
            ) as mock_get_logger:
                with patch("src.core.container.infrastructure.get_database"):
                    with patch("src.core.config.get_settings"):
                        with patch(
                            "src.infrastructure.events.in_memory_event_bus.InMemoryEventBus"
                        ) as mock_bus_cls:
                            with patch(
                                "src.infrastructure.events.handlers.logging_event_handler.LoggingEventHandler"
                            ):
                                with patch(
                                    "src.infrastructure.events.handlers.audit_event_handler.AuditEventHandler"
                                ):
                                    with patch(
                                        "src.infrastructure.events.handlers.email_event_handler.EmailEventHandler"
                                    ):
                                        with patch(
                                            "src.infrastructure.events.handlers.session_event_handler.SessionEventHandler"
                                        ):
                                            mock_bus = MagicMock()
                                            mock_bus_cls.return_value = mock_bus
                                            mock_get_logger.return_value = MagicMock()

                                            bus1 = get_event_bus()
                                            bus2 = get_event_bus()
                                            bus3 = get_event_bus()

                                            # Should only create once
                                            assert mock_bus_cls.call_count == 1
                                            assert bus1 is bus2
                                            assert bus2 is bus3


@pytest.mark.unit
class TestGetEncryptionServiceContainer:
    """Test get_encryption_service() container function."""

    def test_get_encryption_service_returns_encryption_service(self):
        """Test get_encryption_service() returns EncryptionService instance."""
        get_encryption_service.cache_clear()

        with patch("src.core.container.infrastructure.settings") as mock_settings:
            # Valid 32-byte key (base64 encoded)
            import base64

            valid_key = base64.b64encode(b"0" * 32).decode()
            mock_settings.encryption_key = valid_key

            # Patch at actual import location
            with patch(
                "src.infrastructure.providers.encryption_service.EncryptionService"
            ) as mock_svc_cls:
                from src.core.result import Success

                mock_svc = MagicMock()
                mock_svc_cls.create.return_value = Success(value=mock_svc)

                service = get_encryption_service()

                # EncryptionService.create() receives bytes (key.encode())
                mock_svc_cls.create.assert_called_once_with(valid_key.encode("utf-8"))
                assert service == mock_svc

    def test_get_encryption_service_raises_on_invalid_key(self):
        """Test get_encryption_service() raises RuntimeError for invalid key."""
        get_encryption_service.cache_clear()

        with patch("src.core.container.infrastructure.settings") as mock_settings:
            # Use valid length but will fail at EncryptionService.create()
            mock_settings.encryption_key = "invalid-but-exactly-32-chars-x"

            with patch(
                "src.infrastructure.providers.encryption_service.EncryptionService"
            ) as mock_svc_cls:
                from src.core.result import Failure
                from src.core.enums import ErrorCode
                from src.infrastructure.providers.encryption_service import (
                    EncryptionError,
                )

                mock_svc_cls.create.return_value = Failure(
                    error=EncryptionError(
                        code=ErrorCode.ENCRYPTION_KEY_INVALID,
                        message="Invalid key format",
                    )
                )

                with pytest.raises(RuntimeError) as exc_info:
                    get_encryption_service()

                assert "Failed to initialize encryption service" in str(exc_info.value)

    def test_get_encryption_service_uses_singleton_pattern(self):
        """Test get_encryption_service() returns same instance on multiple calls."""
        get_encryption_service.cache_clear()

        with patch("src.core.container.infrastructure.settings") as mock_settings:
            import base64

            valid_key = base64.b64encode(b"0" * 32).decode()
            mock_settings.encryption_key = valid_key

            with patch(
                "src.infrastructure.providers.encryption_service.EncryptionService"
            ) as mock_svc_cls:
                from src.core.result import Success

                mock_svc = MagicMock()
                mock_svc_cls.create.return_value = Success(value=mock_svc)

                svc1 = get_encryption_service()
                svc2 = get_encryption_service()
                svc3 = get_encryption_service()

                # Should only create once
                assert mock_svc_cls.create.call_count == 1
                assert svc1 is svc2
                assert svc2 is svc3
