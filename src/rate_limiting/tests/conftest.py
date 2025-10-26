"""Pytest configuration for rate limiting tests.

This module imports fixtures from the main tests/conftest.py to make them
available to rate limiting tests. This follows the bounded context pattern
where rate limiting tests are co-located with implementation but still use
shared test infrastructure.

Architecture:
    - Rate limiting is an independent bounded context (DDD)
    - Tests are co-located for portability (future extraction)
    - Shared fixtures imported from main conftest
    - No duplicate fixture definitions

Available Fixtures (imported from tests/conftest.py):
    - db_session: Synchronous database session
    - db: Session-scoped database session
    - client: FastAPI TestClient
    - test_user: Test user fixture
    - test_settings: Test configuration settings
"""

import sys
from pathlib import Path

# Add project root to path for importing main conftest fixtures
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import all fixtures from main conftest
# This makes them available to rate limiting tests
from tests.conftest import (  # noqa: F401
    db,
    db_session,
    client,
    client_with_mock_auth,
    test_user,
    test_settings,
    setup_test_database,
    reset_rate_limits,
)

# Note: All fixtures are imported with F401 noqa to suppress "unused import"
# warnings. They are used implicitly by pytest's fixture discovery mechanism.
