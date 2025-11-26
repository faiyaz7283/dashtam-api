"""API tests package.

End-to-end tests for REST API endpoints using TestClient.
Tests the complete request/response cycle including:
- Request validation
- Handler orchestration
- Response formatting
- Error handling
- HTTP status codes

Note:
    API tests use mocked handlers to test the presentation layer
    in isolation. Use integration tests for full-stack testing.
"""
