"""Unit tests for rate limiting package.

This test suite is co-located with the rate_limiting package to maintain
complete independence and portability. The rate_limiting package can be
extracted to a separate project or PyPI package with its tests intact.

Test Organization:
    - test_config.py: Configuration module tests
    - test_algorithms.py: Algorithm tests (token bucket, etc.)
    - test_storage.py: Storage backend tests (Redis, etc.)
    - test_service.py: Service orchestrator tests

Running Tests:
    # Run all rate limiting tests
    pytest src/rate_limiting/tests/

    # Run with coverage
    pytest src/rate_limiting/tests/ --cov=src.rate_limiting

    # Run specific test file
    pytest src/rate_limiting/tests/test_config.py -v
"""
