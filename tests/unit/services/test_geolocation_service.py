"""Unit tests for geolocation service (MaxMind GeoLite2).

Tests IP-to-location conversion with graceful degradation when database is missing.
Uses real service (not mocked) to test actual behavior.
"""

import pytest

from src.services.geolocation_service import GeolocationService, get_geolocation_service


class TestGeolocationServiceWithoutDatabase:
    """Test geolocation service when database is missing (graceful degradation)."""

    @pytest.fixture
    def geo_service_no_db(self, tmp_path):
        """Create GeolocationService with non-existent database path."""
        db_path = tmp_path / "nonexistent.mmdb"
        return GeolocationService(db_path)

    def test_get_location_returns_unknown_when_db_missing(self, geo_service_no_db):
        """Test graceful degradation when database missing."""
        location = geo_service_no_db.get_location("8.8.8.8")
        assert location == "Unknown Location"

    def test_get_location_localhost(self, geo_service_no_db):
        """Test localhost returns Unknown Location."""
        location = geo_service_no_db.get_location("127.0.0.1")
        assert location == "Unknown Location"

    def test_get_location_private_ip(self, geo_service_no_db):
        """Test private IP returns Unknown Location."""
        location = geo_service_no_db.get_location("192.168.1.1")
        assert location == "Unknown Location"

    def test_get_location_invalid_ip(self, geo_service_no_db):
        """Test invalid IP returns Unknown Location."""
        location = geo_service_no_db.get_location("invalid")
        assert location == "Unknown Location"

    def test_get_location_ipv6_localhost(self, geo_service_no_db):
        """Test IPv6 localhost returns Unknown Location."""
        location = geo_service_no_db.get_location("::1")
        assert location == "Unknown Location"

    def test_get_location_empty_string(self, geo_service_no_db):
        """Test empty string returns Unknown Location."""
        location = geo_service_no_db.get_location("")
        assert location == "Unknown Location"


class TestGeolocationServiceIPAnonymization:
    """Test IP address anonymization (privacy feature)."""

    @pytest.fixture
    def geo_service(self, tmp_path):
        """Create GeolocationService (DB not needed for anonymization)."""
        db_path = tmp_path / "nonexistent.mmdb"
        return GeolocationService(db_path)

    def test_anonymize_ipv4(self, geo_service):
        """Test IPv4 anonymization (mask last octet)."""
        anonymized = geo_service.anonymize_ip("192.168.1.100")
        assert anonymized == "192.168.1.0"

    def test_anonymize_ipv4_already_zero(self, geo_service):
        """Test IPv4 that already ends in .0."""
        anonymized = geo_service.anonymize_ip("10.0.0.0")
        assert anonymized == "10.0.0.0"

    def test_anonymize_ipv6(self, geo_service):
        """Test IPv6 anonymization (mask last segment)."""
        anonymized = geo_service.anonymize_ip("2001:4860:4860::8888")
        assert anonymized == "2001:4860:4860::"

    def test_anonymize_invalid_ip(self, geo_service):
        """Test anonymizing invalid IP returns original."""
        invalid_ip = "not-an-ip"
        anonymized = geo_service.anonymize_ip(invalid_ip)
        assert anonymized == invalid_ip  # Returns original on error


class TestGeolocationServiceSingleton:
    """Test singleton pattern for geolocation service."""

    def test_get_geolocation_service_returns_singleton(self):
        """Test get_geolocation_service() returns same instance."""
        service1 = get_geolocation_service()
        service2 = get_geolocation_service()
        assert service1 is service2

    def test_get_geolocation_service_returns_geolocation_service(self):
        """Test factory returns GeolocationService instance."""
        service = get_geolocation_service()
        assert isinstance(service, GeolocationService)


class TestGeolocationServicePerformance:
    """Test geolocation performance characteristics."""

    @pytest.fixture
    def geo_service(self, tmp_path):
        """Create GeolocationService for performance testing."""
        db_path = tmp_path / "nonexistent.mmdb"
        return GeolocationService(db_path)

    def test_multiple_lookups_are_fast(self, geo_service):
        """Test multiple lookups complete quickly."""
        import time

        ips = ["8.8.8.8", "1.1.1.1", "208.67.222.222"]

        start = time.time()
        for ip in ips:
            geo_service.get_location(ip)
        duration_ms = (time.time() - start) * 1000

        # Even without database, lookups should be fast (<50ms for 3)
        assert duration_ms < 50

    def test_anonymization_is_instant(self, geo_service):
        """Test IP anonymization is very fast."""
        import time

        start = time.time()
        for _ in range(100):
            geo_service.anonymize_ip("192.168.1.100")
        duration_ms = (time.time() - start) * 1000

        # 100 anonymizations should be instant (<10ms)
        assert duration_ms < 10
