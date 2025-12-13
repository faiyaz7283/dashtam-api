"""Test suite for Dashtam application.

Test structure follows the test pyramid:
- unit/: Unit tests (70%) - Test domain logic in isolation
- integration/: Integration tests (20%) - Test cross-module interactions
- api/: API endpoint tests (10%) - Test HTTP endpoints end-to-end
- smoke/: Smoke tests - Critical user journeys

All tests are run in Docker containers with isolated test database and Redis.
"""
