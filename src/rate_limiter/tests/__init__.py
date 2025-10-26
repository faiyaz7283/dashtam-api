"""Unit tests for rate limiting package.

This test suite is co-located with the rate_limiter package to maintain
complete independence and portability. The rate_limiter package can be
extracted to a separate project or PyPI package with its tests intact.

Test Organization:
    - test_config.py: Configuration module tests
    - test_algorithms.py: Algorithm tests (token bucket, etc.)
    - test_storage.py: Storage backend tests (Redis, etc.)
    - test_service.py: Service orchestrator tests

Running Tests:
    # Run all rate limiting tests
    pytest src/rate_limiter/tests/

    # Run with coverage
    pytest src/rate_limiter/tests/ --cov=src.rate_limiter

    # Run specific test file
    pytest src/rate_limiter/tests/test_config.py -v
"""
