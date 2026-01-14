"""CQRS Registry - Single Source of Truth for Commands and Queries.

This module catalogs ALL commands and queries in the system with their metadata.
Used for:
- Container auto-wiring (automated handler factory generation)
- Validation tests (verify no drift between commands/handlers)
- Documentation generation (always accurate)
- Gap detection (missing handlers, result DTOs, etc.)

Architecture:
- Application layer (commands/queries are use cases)
- Imported by container for automated wiring
- Verified by tests to catch drift

Adding new commands/queries:
1. Define command/query dataclass in appropriate *_commands.py/*_queries.py file
2. Create handler class in handlers/ directory
3. Add entry to COMMAND_REGISTRY or QUERY_REGISTRY
4. Run tests - they'll tell you what's missing:
   - Handler classes needed
   - Result DTO references needed
   - Container wiring needed (auto-wired)

Reference:
    - docs/architecture/registry.md
    - docs/architecture/cqrs-registry.md
"""

# Metadata types
from src.application.cqrs.metadata import (
    CachePolicy,
    CommandMetadata,
    CQRSCategory,
    QueryMetadata,
)

# Registry constants
from src.application.cqrs.registry import (
    COMMAND_REGISTRY,
    QUERY_REGISTRY,
)

# Computed views and helper functions
from src.application.cqrs.computed_views import (
    get_all_commands,
    get_all_queries,
    get_command_metadata,
    get_commands_by_category,
    get_commands_emitting_events,
    get_queries_by_category,
    get_query_metadata,
    get_statistics,
    validate_registry_consistency,
)

__all__ = [
    # Metadata types
    "CachePolicy",
    "CommandMetadata",
    "CQRSCategory",
    "QueryMetadata",
    # Registry constants
    "COMMAND_REGISTRY",
    "QUERY_REGISTRY",
    # Helper functions
    "get_all_commands",
    "get_all_queries",
    "get_command_metadata",
    "get_commands_by_category",
    "get_commands_emitting_events",
    "get_queries_by_category",
    "get_query_metadata",
    "get_statistics",
    "validate_registry_consistency",
]
