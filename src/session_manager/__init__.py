"""Session Manager Package.

A framework-agnostic, pluggable session management package following SOLID principles.

This package provides comprehensive session management capabilities with zero coupling
to specific frameworks, databases, or authentication mechanisms.

Key Features:
    - Database/cache-agnostic storage
    - Pluggable audit backends
    - Optional session enrichment
    - Framework adapters (FastAPI)
    - 100% SOLID principles compliance

Usage:
    ```python
    from src.session_manager.factory import get_session_manager
    from src.models.session import Session  # App's concrete model

    manager = get_session_manager(
        session_model=Session,
        backend_type="jwt",
        storage_type="database",
        db_session=db_session
    )
    ```
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
