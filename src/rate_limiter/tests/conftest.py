"""Rate Limiter Bounded Context Test Configuration.

This module provides test fixtures isolated to the Rate Limiter bounded context.
Following DDD principles, this bounded context is fully database-agnostic and
uses mocks for testing.

Architecture:
    - Bounded Context: Rate Limiter is a self-contained domain
    - Mock-Based Testing: No real database operations in unit tests
    - Zero Coupling: No dependencies on Dashtam's database models
    - Database-Agnostic: Works with any database/ORM

Design Philosophy:
    The Rate Limiter bounded context is designed to be extracted as a
    standalone package. Unit tests use mocks to verify behavior without
    coupling to any specific database implementation.

Integration Tests:
    Integration tests (testing Dashtam's PostgreSQL implementation) live in
    tests/integration/rate_limiter/ and use Dashtam's test fixtures.

Usage:
    Tests in src/rate_limiter/tests/ automatically use these fixtures.

    Example:
        @pytest.mark.asyncio
        async def test_audit_backend(mock_session, mock_model_class):
            backend = DatabaseAuditBackend(mock_session, mock_model_class)
            await backend.log_violation(...)
"""

# All fixtures for Rate Limiter unit tests are defined in individual test files
# to maintain test isolation and clarity. Common fixtures can be added here
# as needed.

# Example: If multiple test files need the same mock fixture, add it here:
# @pytest.fixture
# def common_mock_fixture():
#     return Mock()
