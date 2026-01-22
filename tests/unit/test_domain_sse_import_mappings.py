"""Unit tests for SSE File Import Mappings (Issue #256).

Tests cover:
- All 4 domain-to-SSE mappings for file import events
- Payload extraction for each event type
- User ID extraction
- Mapping registry integration

Reference:
    - src/domain/events/sse_registry.py
    - GitHub Issue #256
"""

from typing import cast
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.domain.events.data_events import (
    FileImportAttempted,
    FileImportFailed,
    FileImportProgress,
    FileImportSucceeded,
)
from src.domain.events.sse_event import SSEEventType
from src.domain.events.sse_registry import (
    DOMAIN_TO_SSE_MAPPING,
    get_domain_event_to_sse_mapping,
    get_registry_statistics,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def user_id() -> UUID:
    """Provide a test user ID."""
    return cast(UUID, uuid7())


# =============================================================================
# Registry Tests
# =============================================================================


@pytest.mark.unit
class TestFileImportMappingsRegistry:
    """Test that file import mappings are properly registered."""

    def test_all_file_import_events_have_mappings(self):
        """Verify all 4 file import domain events have SSE mappings."""
        mapping = get_domain_event_to_sse_mapping()

        assert FileImportAttempted in mapping
        assert FileImportProgress in mapping
        assert FileImportSucceeded in mapping
        assert FileImportFailed in mapping

    def test_registry_statistics_include_import_mappings(self):
        """Verify registry statistics reflect import mappings."""
        stats = get_registry_statistics()

        # Total mappings should include 4 import mappings
        # (9 data sync + 3 provider + 4 import = 16)
        total_mappings = cast(int, stats["total_mappings"])
        assert total_mappings >= 16

    def test_mapping_list_contains_import_entries(self):
        """Verify DOMAIN_TO_SSE_MAPPING has import event entries."""
        import_types = {
            SSEEventType.IMPORT_STARTED,
            SSEEventType.IMPORT_PROGRESS,
            SSEEventType.IMPORT_COMPLETED,
            SSEEventType.IMPORT_FAILED,
        }

        mapped_types = {m.sse_event_type for m in DOMAIN_TO_SSE_MAPPING}
        assert import_types.issubset(mapped_types)


# =============================================================================
# FileImportAttempted Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestFileImportAttemptedMapping:
    """Test FileImportAttempted domain-to-SSE mapping."""

    def test_maps_to_import_started(self, user_id):
        """Test FileImportAttempted maps to IMPORT_STARTED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportAttempted]

        assert m.sse_event_type == SSEEventType.IMPORT_STARTED

    def test_payload_extraction(self, user_id):
        """Test payload extraction from FileImportAttempted."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportAttempted]

        event = FileImportAttempted(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="transactions.qfx",
            file_format="qfx",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "file_name": "transactions.qfx",
            "file_format": "qfx",
        }

    def test_user_id_extraction(self, user_id):
        """Test user_id is correctly extracted from FileImportAttempted."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportAttempted]

        event = FileImportAttempted(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="test.qfx",
            file_format="qfx",
        )
        assert m.user_id_extractor(event) == user_id


# =============================================================================
# FileImportProgress Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestFileImportProgressMapping:
    """Test FileImportProgress domain-to-SSE mapping."""

    def test_maps_to_import_progress(self, user_id):
        """Test FileImportProgress maps to IMPORT_PROGRESS."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportProgress]

        assert m.sse_event_type == SSEEventType.IMPORT_PROGRESS

    def test_payload_extraction(self, user_id):
        """Test payload extraction from FileImportProgress."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportProgress]

        event = FileImportProgress(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="transactions.qfx",
            file_format="qfx",
            progress_percent=50,
            records_processed=500,
            total_records=1000,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "file_name": "transactions.qfx",
            "progress_percent": 50,
            "records_processed": 500,
        }

    def test_user_id_extraction(self, user_id):
        """Test user_id is correctly extracted from FileImportProgress."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportProgress]

        event = FileImportProgress(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="test.qfx",
            file_format="qfx",
            progress_percent=25,
            records_processed=250,
            total_records=1000,
        )
        assert m.user_id_extractor(event) == user_id


# =============================================================================
# FileImportSucceeded Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestFileImportSucceededMapping:
    """Test FileImportSucceeded domain-to-SSE mapping."""

    def test_maps_to_import_completed(self, user_id):
        """Test FileImportSucceeded maps to IMPORT_COMPLETED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportSucceeded]

        assert m.sse_event_type == SSEEventType.IMPORT_COMPLETED

    def test_payload_extraction(self, user_id):
        """Test payload extraction from FileImportSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportSucceeded]

        event = FileImportSucceeded(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="transactions.qfx",
            file_format="qfx",
            account_count=2,
            transaction_count=150,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "file_name": "transactions.qfx",
            "records_imported": 150,
        }

    def test_user_id_extraction(self, user_id):
        """Test user_id is correctly extracted from FileImportSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportSucceeded]

        event = FileImportSucceeded(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="test.qfx",
            file_format="qfx",
            account_count=1,
            transaction_count=100,
        )
        assert m.user_id_extractor(event) == user_id


# =============================================================================
# FileImportFailed Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestFileImportFailedMapping:
    """Test FileImportFailed domain-to-SSE mapping."""

    def test_maps_to_import_failed(self, user_id):
        """Test FileImportFailed maps to IMPORT_FAILED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportFailed]

        assert m.sse_event_type == SSEEventType.IMPORT_FAILED

    def test_payload_extraction(self, user_id):
        """Test payload extraction from FileImportFailed."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportFailed]

        event = FileImportFailed(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="bad_file.qfx",
            file_format="qfx",
            reason="parse_error",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "file_name": "bad_file.qfx",
            "error": "parse_error",
        }

    def test_user_id_extraction(self, user_id):
        """Test user_id is correctly extracted from FileImportFailed."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[FileImportFailed]

        event = FileImportFailed(
            user_id=user_id,
            provider_slug="chase_file",
            file_name="test.qfx",
            file_format="qfx",
            reason="invalid_format",
        )
        assert m.user_id_extractor(event) == user_id


# =============================================================================
# SSE Event Handler Integration Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventHandlerIntegration:
    """Test that mappings work with SSEEventHandler."""

    def test_handler_has_mapping_for_all_import_events(self):
        """Verify SSEEventHandler can find mappings for import events."""
        from unittest.mock import MagicMock

        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        # All import events should have mappings
        assert handler.has_mapping_for(FileImportAttempted)
        assert handler.has_mapping_for(FileImportProgress)
        assert handler.has_mapping_for(FileImportSucceeded)
        assert handler.has_mapping_for(FileImportFailed)

    def test_handler_returns_import_events_in_mapped_types(self):
        """Verify SSEEventHandler returns import events in mapped types."""
        from unittest.mock import MagicMock

        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        mapped_types = handler.get_mapped_event_types()

        # Should include all import events
        assert FileImportAttempted in mapped_types
        assert FileImportProgress in mapped_types
        assert FileImportSucceeded in mapped_types
        assert FileImportFailed in mapped_types
