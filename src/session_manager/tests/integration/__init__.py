"""Integration tests for session manager package.

**WIP - TESTS NOT YET PASSING**

These tests require backend/storage refactoring to be completed:
    - JWTSessionBackend needs to instantiate session_model (not return dict)
    - CacheSessionStorage needs to deserialize to session_model (not dict)
    - All unit tests need to be updated to pass session_model parameter

Test Organization:
    - test_cache_storage.py: CacheSessionStorage with fakeredis
    - test_session_lifecycle.py: End-to-end session flows

Strategy:
    - Use real package components (not mocks)
    - Use test doubles for external dependencies (fakeredis)
    - Test complete workflows and component interactions

Next Steps:
    1. Fix JWTSessionBackend to create session_model instances
    2. Fix CacheSessionStorage deserialization
    3. Update all unit tests for new backend signature
    4. Complete integration test implementation
"""
