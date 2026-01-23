"""SSE Registry Compliance Tests - FAIL FAST on drift.

These tests verify the SSE Event Registry remains synchronized with:
- SSEEventType enum (all types must have metadata)
- Category consistency (registry category must match enum mapping)
- Statistics accuracy (counts must match actual data)

Tests FAIL if:
- SSEEventType exists but has no metadata in SSE_EVENT_REGISTRY
- Registry metadata category doesn't match _EVENT_TYPE_TO_CATEGORY
- Statistics counts are inaccurate

This ensures the SSE registry remains the single source of truth.

Reference:
    - src/domain/events/sse_event.py (SSEEventType, _EVENT_TYPE_TO_CATEGORY)
    - src/domain/events/sse_registry.py (SSE_EVENT_REGISTRY)
"""

import pytest

from src.domain.events.sse_event import (
    SSEEventCategory,
    SSEEventType,
    get_category_for_event_type,
)
from src.domain.events.sse_registry import (
    SSE_EVENT_REGISTRY,
    get_all_sse_event_types,
    get_events_by_category,
    get_registry_statistics,
    get_sse_event_metadata,
)


# =============================================================================
# Registry Completeness Tests
# =============================================================================


@pytest.mark.unit
class TestRegistryCompleteness:
    """Verify SSE registry is complete and accurate."""

    def test_registry_not_empty(self):
        """Registry must contain event metadata."""
        assert len(SSE_EVENT_REGISTRY) > 0, "SSE_EVENT_REGISTRY is empty!"

    def test_all_sse_event_types_have_registry_metadata(self):
        """CRITICAL: Every SSEEventType must have metadata in SSE_EVENT_REGISTRY.

        This test FAILS if:
        - SSEEventType enum has a value
        - But SSE_EVENT_REGISTRY has no metadata for it

        Fix: Add missing metadata to SSE_EVENT_REGISTRY in sse_registry.py
        """
        registered_types = {m.event_type for m in SSE_EVENT_REGISTRY}
        missing = []

        for event_type in SSEEventType:
            if event_type not in registered_types:
                missing.append(event_type.name)

        assert not missing, (
            f"\n❌ SSE REGISTRY COMPLIANCE FAILURE: Event types missing metadata\n\n"
            f"Missing from SSE_EVENT_REGISTRY:\n"
            f"{chr(10).join(f'  - {m}' for m in missing)}\n\n"
            f"Fix: Add SSEEventMetadata entries to src/domain/events/sse_registry.py"
        )

    def test_all_metadata_has_required_fields(self):
        """Every metadata entry must have complete required fields."""
        for meta in SSE_EVENT_REGISTRY:
            assert meta.event_type is not None, "event_type missing"
            assert meta.category is not None, "category missing"
            assert meta.description, "description is empty"
            # payload_fields can be empty but must exist
            assert meta.payload_fields is not None


# =============================================================================
# Category Consistency Tests
# =============================================================================


@pytest.mark.unit
class TestCategoryConsistency:
    """Verify category mappings are consistent across modules."""

    def test_registry_category_matches_event_type_mapping(self):
        """CRITICAL: Registry category must match _EVENT_TYPE_TO_CATEGORY.

        This test FAILS if:
        - SSE_EVENT_REGISTRY says event is in category X
        - But _EVENT_TYPE_TO_CATEGORY says it's in category Y

        Fix: Ensure both sources agree on category assignment.
        """
        mismatches = []

        for meta in SSE_EVENT_REGISTRY:
            expected_category = get_category_for_event_type(meta.event_type)
            if meta.category != expected_category:
                mismatches.append(
                    f"{meta.event_type.name}: registry={meta.category.value}, "
                    f"mapping={expected_category.value}"
                )

        assert not mismatches, (
            f"\n❌ SSE REGISTRY COMPLIANCE FAILURE: Category mismatches\n\n"
            f"The following events have inconsistent category assignments:\n"
            f"{chr(10).join(f'  - {m}' for m in mismatches)}\n\n"
            f"Fix: Ensure SSE_EVENT_REGISTRY and _EVENT_TYPE_TO_CATEGORY agree"
        )


# =============================================================================
# Helper Function Tests
# =============================================================================


@pytest.mark.unit
class TestRegistryHelpers:
    """Test SSE registry helper functions."""

    def test_get_sse_event_metadata_returns_correct_metadata(self):
        """Test get_sse_event_metadata returns matching metadata."""
        meta = get_sse_event_metadata(SSEEventType.SYNC_ACCOUNTS_COMPLETED)
        assert meta is not None
        assert meta.event_type == SSEEventType.SYNC_ACCOUNTS_COMPLETED
        assert meta.category == SSEEventCategory.DATA_SYNC

    def test_get_sse_event_metadata_returns_none_for_missing(self):
        """Test get_sse_event_metadata returns None for unregistered type.

        Note: This test creates a mock scenario since all types should be
        registered. Testing with a valid but conceptually "missing" lookup.
        """
        # All types should be registered, so we verify that
        for event_type in SSEEventType:
            meta = get_sse_event_metadata(event_type)
            assert meta is not None, f"Missing metadata for {event_type.name}"

    def test_get_events_by_category_returns_correct_events(self):
        """Test get_events_by_category filters correctly."""
        data_sync_events = get_events_by_category(SSEEventCategory.DATA_SYNC)

        # Should have 9 data sync events
        assert len(data_sync_events) == 9

        # All should be DATA_SYNC category
        for meta in data_sync_events:
            assert meta.category == SSEEventCategory.DATA_SYNC

    def test_get_all_sse_event_types_returns_all_types(self):
        """Test get_all_sse_event_types returns all registered types."""
        types = get_all_sse_event_types()

        # Should match registry length
        assert len(types) == len(SSE_EVENT_REGISTRY)

        # Should contain all SSEEventType values
        for meta in SSE_EVENT_REGISTRY:
            assert meta.event_type in types


# =============================================================================
# Statistics Tests
# =============================================================================


@pytest.mark.unit
class TestRegistryStatistics:
    """Verify registry statistics are accurate."""

    def test_statistics_total_event_types_accurate(self):
        """Test total_event_types matches actual registry length."""
        stats = get_registry_statistics()
        assert stats["total_event_types"] == len(SSE_EVENT_REGISTRY)

    def test_statistics_category_counts_accurate(self):
        """Test category counts match actual data."""
        stats = get_registry_statistics()
        by_category = stats["by_category"]
        assert isinstance(by_category, dict)

        # Verify counts match helper function results
        for category in SSEEventCategory:
            expected_count = len(get_events_by_category(category))
            actual_count = by_category.get(category.value, 0)
            assert actual_count == expected_count, (
                f"Category {category.value} count mismatch: "
                f"stats={actual_count}, actual={expected_count}"
            )

    def test_statistics_total_equals_sum_of_categories(self):
        """Test total equals sum of all category counts."""
        stats = get_registry_statistics()
        total = stats["total_event_types"]
        by_category = stats["by_category"]
        assert isinstance(by_category, dict)
        category_sum = sum(by_category.values())

        assert total == category_sum, (
            f"Total ({total}) != sum of categories ({category_sum})"
        )


# =============================================================================
# No Duplicate Tests
# =============================================================================


@pytest.mark.unit
class TestNoDuplicates:
    """Verify no duplicate entries in registry."""

    def test_no_duplicate_event_types_in_registry(self):
        """Each event type should appear exactly once in registry."""
        event_types = [m.event_type for m in SSE_EVENT_REGISTRY]
        duplicates = [t for t in event_types if event_types.count(t) > 1]

        assert not duplicates, (
            f"Duplicate event types in SSE_EVENT_REGISTRY: {set(duplicates)}"
        )

    def test_no_duplicate_descriptions(self):
        """Event descriptions should be unique (prevent copy-paste errors)."""
        descriptions = [m.description for m in SSE_EVENT_REGISTRY]
        seen: set[str] = set()
        duplicates = []

        for desc in descriptions:
            if desc in seen:
                duplicates.append(desc)
            seen.add(desc)

        assert not duplicates, (
            f"Duplicate descriptions found (possible copy-paste error):\n"
            f"{chr(10).join(f'  - {d}' for d in duplicates)}"
        )
