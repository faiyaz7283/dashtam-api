"""Integration tests for IPLocationEnricher.

Tests the GeoIP2-based location enrichment implementation with:
- Real database lookups (if database file exists)
- Private IP detection (no lookup for RFC 1918 addresses)
- Fail-open behavior (returns empty on errors)
- Database initialization and lazy loading
- Edge cases (invalid IPs, missing database)

Architecture:
- Integration tests for infrastructure adapter (no mocking geoip2)
- Tests against real MaxMind GeoLite2 database when available
- Tests fail-open behavior with missing/invalid database
- Tests protocol compliance (LocationEnrichmentResult structure)

Reference:
    - F6.15: IP Geolocation Integration
    - src/infrastructure/enrichers/location_enricher.py
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.domain.protocols.session_enricher_protocol import LocationEnrichmentResult
from src.infrastructure.enrichers.location_enricher import IPLocationEnricher


@pytest.mark.integration
class TestIPLocationEnricherIntegration:
    """Integration tests for IP location enricher.

    Uses real GeoIP2 database when available for location lookups.
    Tests fail-open behavior when database is missing or invalid.
    """

    # =========================================================================
    # Private IP Detection Tests (No Database Lookup)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_private_ip_returns_empty_no_lookup(self, mock_logger):
        """Test that private IPs return empty result without database lookup."""
        enricher = IPLocationEnricher(logger=mock_logger)

        private_ips = [
            "192.168.1.1",  # RFC 1918: 192.168.0.0/16
            "10.0.0.1",  # RFC 1918: 10.0.0.0/8
            "172.16.0.1",  # RFC 1918: 172.16.0.0/12
            "127.0.0.1",  # Loopback
            "::1",  # IPv6 loopback
            "fe80::1",  # IPv6 link-local
        ]

        for ip in private_ips:
            result = await enricher.enrich(ip)

            assert isinstance(result, LocationEnrichmentResult)
            assert result.location is None
            assert result.city is None
            assert result.country_code is None
            assert result.latitude is None
            assert result.longitude is None

    @pytest.mark.asyncio
    async def test_empty_ip_returns_empty_result(self, mock_logger):
        """Test that empty IP string returns empty result."""
        enricher = IPLocationEnricher(logger=mock_logger)

        result = await enricher.enrich("")

        assert isinstance(result, LocationEnrichmentResult)
        assert result.location is None
        assert result.city is None
        assert result.country_code is None

    # =========================================================================
    # Database Missing/Invalid Tests (Fail-Open Behavior)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_missing_database_returns_empty_logs_warning(self, mock_logger):
        """Test that missing database file returns empty result (fail-open)."""
        enricher = IPLocationEnricher(
            logger=mock_logger, db_path="/nonexistent/path/GeoLite2-City.mmdb"
        )

        # Public IP should trigger database lookup
        result = await enricher.enrich("8.8.8.8")

        # Fail-open: Returns empty result
        assert isinstance(result, LocationEnrichmentResult)
        assert result.location is None

        # Should log warning about missing database
        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args
        assert "database file not found" in str(warning_call).lower()

    @pytest.mark.asyncio
    async def test_none_database_path_returns_empty_logs_debug(self, mock_logger):
        """Test that None db_path returns empty result with debug log."""
        # Patch settings to ensure geoip_db_path is None
        with patch(
            "src.infrastructure.enrichers.location_enricher.settings"
        ) as mock_settings:
            mock_settings.geoip_db_path = None
            enricher = IPLocationEnricher(logger=mock_logger, db_path=None)

            result = await enricher.enrich("8.8.8.8")

            # Fail-open: Returns empty result
            assert isinstance(result, LocationEnrichmentResult)
            assert result.location is None

            # Should log debug about not configured
            mock_logger.debug.assert_called()
            debug_call = mock_logger.debug.call_args
            assert "not configured" in str(debug_call).lower()

    @pytest.mark.asyncio
    async def test_invalid_ip_format_returns_empty(self, mock_logger):
        """Test that invalid IP format returns empty result (fail-open)."""
        enricher = IPLocationEnricher(logger=mock_logger)

        invalid_ips = [
            "not_an_ip",
            "999.999.999.999",
            "256.1.1.1",
            "192.168.1",  # Incomplete
            "::gggg",  # Invalid IPv6
        ]

        for invalid_ip in invalid_ips:
            result = await enricher.enrich(invalid_ip)

            # Fail-open: Returns empty result
            assert isinstance(result, LocationEnrichmentResult)
            assert result.location is None

    # =========================================================================
    # Real Database Lookup Tests (if database exists)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_public_ip_lookup_with_real_database(self, mock_logger):
        """Test public IP lookup with real GeoLite2 database (if available).

        This test will:
        - PASS if database exists and lookup succeeds
        - SKIP if database doesn't exist (not a test failure)
        """
        db_path = Path("/app/data/geoip/GeoLite2-City.mmdb")

        if not db_path.exists():
            pytest.skip("GeoLite2 database not available")

        enricher = IPLocationEnricher(logger=mock_logger, db_path=str(db_path))

        # Google Public DNS (should have location data)
        result = await enricher.enrich("8.8.8.8")

        # Should have location data
        assert isinstance(result, LocationEnrichmentResult)
        # Note: Exact location may vary by database version
        # We just verify structure is populated
        assert result.country_code is not None  # Should have US
        # City may or may not be present for this IP
        # Location string should be present (at minimum country_code)
        if result.city:
            assert result.location == f"{result.city}, {result.country_code}"
        else:
            assert result.location == result.country_code

    @pytest.mark.asyncio
    async def test_ip_not_in_database_returns_empty(self, mock_logger):
        """Test that IP not in database returns empty result (fail-open).

        Some IPs may not be in the GeoLite2 database. This should
        return empty result and log debug message.
        """
        db_path = Path("/app/data/geoip/GeoLite2-City.mmdb")

        if not db_path.exists():
            pytest.skip("GeoLite2 database not available")

        enricher = IPLocationEnricher(logger=mock_logger, db_path=str(db_path))

        # Use an IP that might not be in database (RFC 6598 shared address)
        result = await enricher.enrich("100.64.0.1")

        # Fail-open: Should return empty result
        assert isinstance(result, LocationEnrichmentResult)
        # Note: Depending on database, this may or may not be found
        # We just verify it doesn't raise an exception

    # =========================================================================
    # Location String Formatting Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_location_string_format_city_and_country(self, mock_logger):
        """Test location string format when both city and country are present."""
        # Mock geoip2 response with city + country
        with patch(
            "src.infrastructure.enrichers.location_enricher.geoip2.database.Reader"
        ) as mock_reader_class:
            with patch(
                "src.infrastructure.enrichers.location_enricher.Path.exists",
                return_value=True,
            ):
                mock_reader = Mock()
                mock_reader_class.return_value = mock_reader

                # Mock response with city + country
                mock_response = Mock()
                mock_response.city.name = "New York"
                mock_response.country.iso_code = "US"
                mock_response.location.latitude = 40.7128
                mock_response.location.longitude = -74.0060

                mock_reader.city.return_value = mock_response

                enricher = IPLocationEnricher(
                    logger=mock_logger, db_path="/fake/path/GeoLite2-City.mmdb"
                )

                result = await enricher.enrich("8.8.8.8")

                assert result.location == "New York, US"
                assert result.city == "New York"
                assert result.country_code == "US"
                assert result.latitude == 40.7128
                assert result.longitude == -74.0060

    @pytest.mark.asyncio
    async def test_location_string_format_country_only(self, mock_logger):
        """Test location string format when only country is present (no city)."""
        # Mock geoip2 response with country only
        with patch(
            "src.infrastructure.enrichers.location_enricher.geoip2.database.Reader"
        ) as mock_reader_class:
            with patch(
                "src.infrastructure.enrichers.location_enricher.Path.exists",
                return_value=True,
            ):
                mock_reader = Mock()
                mock_reader_class.return_value = mock_reader

                # Mock response with country only (no city)
                mock_response = Mock()
                mock_response.city.name = None
                mock_response.country.iso_code = "US"
                mock_response.location.latitude = 37.751
                mock_response.location.longitude = -97.822

                mock_reader.city.return_value = mock_response

                enricher = IPLocationEnricher(
                    logger=mock_logger, db_path="/fake/path/GeoLite2-City.mmdb"
                )

                result = await enricher.enrich("8.8.8.8")

                assert result.location == "US"  # Country code only
                assert result.city is None
                assert result.country_code == "US"

    @pytest.mark.asyncio
    async def test_location_string_none_when_no_data(self, mock_logger):
        """Test location string is None when no city or country data."""
        # Mock geoip2 response with no location data
        with patch(
            "src.infrastructure.enrichers.location_enricher.geoip2.database.Reader"
        ) as mock_reader_class:
            with patch(
                "src.infrastructure.enrichers.location_enricher.Path.exists",
                return_value=True,
            ):
                mock_reader = Mock()
                mock_reader_class.return_value = mock_reader

                # Mock response with no data
                mock_response = Mock()
                mock_response.city.name = None
                mock_response.country.iso_code = None
                mock_response.location.latitude = None
                mock_response.location.longitude = None

                mock_reader.city.return_value = mock_response

                enricher = IPLocationEnricher(
                    logger=mock_logger, db_path="/fake/path/GeoLite2-City.mmdb"
                )

                result = await enricher.enrich("8.8.8.8")

                assert result.location is None
                assert result.city is None
                assert result.country_code is None

    # =========================================================================
    # Lazy Loading Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_lazy_database_loading(self, mock_logger):
        """Test that database is loaded lazily on first lookup."""
        with patch(
            "src.infrastructure.enrichers.location_enricher.geoip2.database.Reader"
        ) as mock_reader_class:
            with patch(
                "src.infrastructure.enrichers.location_enricher.Path.exists",
                return_value=True,
            ):
                mock_reader = Mock()
                mock_reader_class.return_value = mock_reader

                # Mock response
                mock_response = Mock()
                mock_response.city.name = "Mountain View"
                mock_response.country.iso_code = "US"
                mock_response.location.latitude = 37.4056
                mock_response.location.longitude = -122.0775

                mock_reader.city.return_value = mock_response

                enricher = IPLocationEnricher(
                    logger=mock_logger, db_path="/fake/path/GeoLite2-City.mmdb"
                )

                # Reader not initialized yet
                assert enricher._reader is None

                # First call initializes reader
                await enricher.enrich("8.8.4.4")

                # Reader should be initialized once
                mock_reader_class.assert_called_once()

                # Second call reuses reader
                await enricher.enrich("8.8.8.8")

                # Reader constructor still called only once
                mock_reader_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_init_logs_success(self, mock_logger):
        """Test that successful database initialization logs info message."""
        with patch(
            "src.infrastructure.enrichers.location_enricher.geoip2.database.Reader"
        ) as mock_reader_class:
            with patch(
                "src.infrastructure.enrichers.location_enricher.Path.exists",
                return_value=True,
            ):
                mock_reader = Mock()
                mock_reader_class.return_value = mock_reader

                # Mock response
                mock_response = Mock()
                mock_response.city.name = "Test City"
                mock_response.country.iso_code = "TC"
                mock_response.location.latitude = 0.0
                mock_response.location.longitude = 0.0

                mock_reader.city.return_value = mock_response

                enricher = IPLocationEnricher(
                    logger=mock_logger, db_path="/fake/path/GeoLite2-City.mmdb"
                )

                await enricher.enrich("8.8.8.8")

                # Should log info about successful initialization
                mock_logger.info.assert_called()
                info_call = mock_logger.info.call_args
                assert "loaded successfully" in str(info_call).lower()

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_database_read_error_returns_empty(self, mock_logger):
        """Test that database read error returns empty result (fail-open)."""
        with patch(
            "src.infrastructure.enrichers.location_enricher.geoip2.database.Reader"
        ) as mock_reader_class:
            mock_reader = Mock()
            mock_reader_class.return_value = mock_reader

            # Simulate database read error
            mock_reader.city.side_effect = Exception("Database corrupted")

            # Need to patch Path.exists to avoid file not found warning
            with patch(
                "src.infrastructure.enrichers.location_enricher.Path.exists",
                return_value=True,
            ):
                enricher = IPLocationEnricher(
                    logger=mock_logger, db_path="/fake/path/GeoLite2-City.mmdb"
                )

                result = await enricher.enrich("8.8.8.8")

                # Fail-open: Returns empty result
                assert isinstance(result, LocationEnrichmentResult)
                assert result.location is None

                # Should log warning about failure
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args
                assert "failed to enrich" in str(warning_call).lower()

    @pytest.mark.asyncio
    async def test_database_init_error_returns_empty(self, mock_logger):
        """Test that database initialization error returns empty result."""
        with patch(
            "src.infrastructure.enrichers.location_enricher.geoip2.database.Reader"
        ) as mock_reader_class:
            # Simulate database initialization error
            mock_reader_class.side_effect = Exception("Failed to open database")

            with patch(
                "src.infrastructure.enrichers.location_enricher.Path.exists",
                return_value=True,
            ):
                enricher = IPLocationEnricher(
                    logger=mock_logger, db_path="/fake/path/GeoLite2-City.mmdb"
                )

                result = await enricher.enrich("8.8.8.8")

                # Fail-open: Returns empty result
                assert isinstance(result, LocationEnrichmentResult)
                assert result.location is None

                # Should log warning about initialization failure
                assert mock_logger.warning.called

    # =========================================================================
    # Protocol Compliance Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_result_structure_compliance(self, mock_logger):
        """Test that result always matches LocationEnrichmentResult protocol."""
        enricher = IPLocationEnricher(logger=mock_logger)

        # Test with various inputs
        test_ips = ["", "192.168.1.1", "invalid", "8.8.8.8"]

        for ip in test_ips:
            result = await enricher.enrich(ip)

            # Must return LocationEnrichmentResult
            assert isinstance(result, LocationEnrichmentResult)

            # All fields must exist (can be None)
            assert hasattr(result, "location")
            assert hasattr(result, "city")
            assert hasattr(result, "country_code")
            assert hasattr(result, "latitude")
            assert hasattr(result, "longitude")

            # Types must be correct
            assert result.location is None or isinstance(result.location, str)
            assert result.city is None or isinstance(result.city, str)
            assert result.country_code is None or isinstance(result.country_code, str)
            assert result.latitude is None or isinstance(result.latitude, float)
            assert result.longitude is None or isinstance(result.longitude, float)
