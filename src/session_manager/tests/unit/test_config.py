"""Unit tests for session manager configuration models.

Tests configuration validation, defaults, and pre-configured scenarios.
"""

from datetime import timedelta

import pytest

from src.session_manager.models.config import (
    DEVELOPMENT_CONFIG,
    PRODUCTION_CONFIG,
    TESTING_CONFIG,
    AuditConfig,
    EnricherConfig,
    SessionConfig,
    StorageConfig,
)


class TestSessionConfig:
    """Test SessionConfig validation and defaults."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SessionConfig()

        assert config.session_ttl == timedelta(days=30)
        assert config.inactive_ttl == timedelta(days=7)
        assert config.max_sessions_per_user == 5
        assert config.backend_type == "jwt"
        assert config.storage_type == "database"
        assert config.audit_type == "logger"
        assert config.enable_enrichment is True
        assert config.trust_forwarded_ip is False
        assert config.require_user_agent is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SessionConfig(
            session_ttl=timedelta(days=60),
            max_sessions_per_user=10,
            storage_type="cache",
            audit_type="database",
        )

        assert config.session_ttl == timedelta(days=60)
        assert config.max_sessions_per_user == 10
        assert config.storage_type == "cache"
        assert config.audit_type == "database"

    def test_validation_positive_session_ttl(self):
        """Test validation: session_ttl must be positive."""
        with pytest.raises(ValueError, match="session_ttl must be positive"):
            SessionConfig(session_ttl=timedelta(seconds=0))

        with pytest.raises(ValueError, match="session_ttl must be positive"):
            SessionConfig(session_ttl=timedelta(seconds=-1))

    def test_validation_positive_inactive_ttl(self):
        """Test validation: inactive_ttl must be positive."""
        with pytest.raises(ValueError, match="inactive_ttl must be positive"):
            SessionConfig(inactive_ttl=timedelta(seconds=0))

    def test_validation_max_sessions(self):
        """Test validation: max_sessions_per_user must be at least 1."""
        with pytest.raises(
            ValueError, match="max_sessions_per_user must be at least 1"
        ):
            SessionConfig(max_sessions_per_user=0)

        with pytest.raises(
            ValueError, match="max_sessions_per_user must be at least 1"
        ):
            SessionConfig(max_sessions_per_user=-1)


class TestStorageConfig:
    """Test StorageConfig defaults."""

    def test_default_storage_config(self):
        """Test default storage configuration."""
        config = StorageConfig()

        assert config.cache_ttl == timedelta(days=30)
        assert config.cache_key_prefix == "session:"
        assert config.database_pool_size == 10
        assert config.enable_cache_fallback is False

    def test_custom_storage_config(self):
        """Test custom storage configuration."""
        config = StorageConfig(
            cache_ttl=timedelta(hours=1),
            cache_key_prefix="app:session:",
            database_pool_size=20,
            enable_cache_fallback=True,
        )

        assert config.cache_ttl == timedelta(hours=1)
        assert config.cache_key_prefix == "app:session:"
        assert config.database_pool_size == 20
        assert config.enable_cache_fallback is True


class TestAuditConfig:
    """Test AuditConfig validation and defaults."""

    def test_default_audit_config(self):
        """Test default audit configuration."""
        config = AuditConfig()

        assert config.retention_days == 90
        assert config.sample_rate == 1.0
        assert config.log_level == "INFO"
        assert config.enable_metrics is False

    def test_custom_audit_config(self):
        """Test custom audit configuration."""
        config = AuditConfig(
            retention_days=30,
            sample_rate=0.5,
            log_level="DEBUG",
            enable_metrics=True,
        )

        assert config.retention_days == 30
        assert config.sample_rate == 0.5
        assert config.log_level == "DEBUG"
        assert config.enable_metrics is True

    def test_validation_retention_days(self):
        """Test validation: retention_days must be at least 1."""
        with pytest.raises(ValueError, match="retention_days must be at least 1"):
            AuditConfig(retention_days=0)

    def test_validation_sample_rate(self):
        """Test validation: sample_rate must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="sample_rate must be between 0.0 and 1.0"):
            AuditConfig(sample_rate=-0.1)

        with pytest.raises(ValueError, match="sample_rate must be between 0.0 and 1.0"):
            AuditConfig(sample_rate=1.1)

        # Valid boundaries
        AuditConfig(sample_rate=0.0)  # Should not raise
        AuditConfig(sample_rate=1.0)  # Should not raise


class TestEnricherConfig:
    """Test EnricherConfig defaults."""

    def test_default_enricher_config(self):
        """Test default enricher configuration."""
        config = EnricherConfig()

        assert config.enable_geolocation is False
        assert config.geolocation_provider is None
        assert config.geolocation_api_key is None
        assert config.enable_device_fingerprint is False
        assert config.device_parser == "user-agents"

    def test_custom_enricher_config(self):
        """Test custom enricher configuration."""
        config = EnricherConfig(
            enable_geolocation=True,
            geolocation_provider="ipapi",
            geolocation_api_key="test-key",
            enable_device_fingerprint=True,
            device_parser="ua-parser",
        )

        assert config.enable_geolocation is True
        assert config.geolocation_provider == "ipapi"
        assert config.geolocation_api_key == "test-key"
        assert config.enable_device_fingerprint is True
        assert config.device_parser == "ua-parser"


class TestPreConfiguredScenarios:
    """Test pre-configured configuration scenarios."""

    def test_default_config(self):
        """Test DEFAULT_CONFIG pre-configured scenario."""
        from src.session_manager.models.config import DEFAULT_CONFIG

        config = DEFAULT_CONFIG

        assert config.session_ttl == timedelta(days=30)
        assert config.storage_type == "database"
        assert config.audit_type == "logger"

    def test_development_config(self):
        """Test DEVELOPMENT_CONFIG pre-configured scenario."""
        config = DEVELOPMENT_CONFIG

        assert config.session_ttl == timedelta(days=7)
        assert config.storage_type == "memory"
        assert config.audit_type == "logger"
        assert config.enable_enrichment is False

    def test_production_config(self):
        """Test PRODUCTION_CONFIG pre-configured scenario."""
        config = PRODUCTION_CONFIG

        assert config.session_ttl == timedelta(days=30)
        assert config.storage_type == "database"
        assert config.audit_type == "database"
        assert config.enable_enrichment is True

    def test_testing_config(self):
        """Test TESTING_CONFIG pre-configured scenario."""
        config = TESTING_CONFIG

        assert config.session_ttl == timedelta(minutes=5)
        assert config.storage_type == "memory"
        assert config.audit_type == "noop"
        assert config.enable_enrichment is False
