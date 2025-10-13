# Smoke Tests

This directory contains smoke tests for the Dashtam application - quick, critical-path tests that validate the system is operational.

## What are Smoke Tests?

Smoke tests are a subset of tests that:

- **Validate critical functionality** - Essential user journeys work end-to-end
- **Run quickly** - Complete in under 5 minutes
- **Catch showstopper bugs** - Block deployment if they fail
- **Test happy paths** - Focus on the "golden path" through the application

## Tests in this Directory

### `test_complete_auth_flow.py` (5 tests)

Comprehensive authentication flow validation covering:

**Complete Auth Flow (1 test with 18 steps)**:

1. User Registration
2. Email Verification Token Extraction
3. Email Verification
4. Login
5. Get User Profile
6. Update Profile
7. Token Refresh
8. Verify New Access Token
9. Password Reset Request
10. Extract Reset Token
11. Verify Reset Token
12. Confirm Password Reset
13. Old Refresh Token Revoked
14. Old Access Token Still Works
15. Login with New Password
16. Logout
17. Refresh Token Revoked After Logout
18. Access Token Still Works After Logout

**Independent Validation Tests (4 tests)**:

- System health check
- API documentation accessibility
- Invalid login rejection
- Weak password rejection

**Note**: All tests run in **isolated pytest session** using `@pytest.mark.smoke` marker.

## Running Smoke Tests

**CRITICAL**: Smoke tests run in **isolated pytest sessions** to prevent database state conflicts with main tests.

### Run All Smoke Tests

**Recommended** (uses project Makefile with isolation):

```bash
make test-smoke  # Runs: pytest -m smoke -v
```

This automatically:

- ✅ Starts test environment if not running
- ✅ Runs ONLY tests marked with `@pytest.mark.smoke`
- ✅ Isolates from main test suite (no state conflicts)
- ✅ Provides clear test output

**Manual pytest commands** (inside container):

```bash
# Using test environment (recommended)
docker compose -f compose/docker-compose.test.yml exec -T app uv run pytest -m smoke -v

# Run specific smoke test
docker compose -f compose/docker-compose.test.yml exec -T app uv run pytest -m smoke -k test_complete_authentication_flow -v
```

### Test Isolation

**Why isolated sessions?**

Smoke tests run in a **separate pytest session** from main tests because:

1. **State persistence**: Auth flow needs state to persist across API calls
2. **Database isolation**: Prevents conflicts with main test fixtures
3. **Clear output**: Shows smoke test progress independently
4. **CI visibility**: GitHub Actions displays smoke tests separately

**Implementation**:

- All smoke tests marked with `@pytest.mark.smoke`
- Main tests excluded with `-m "not smoke"`
- Smoke tests selected with `-m smoke`
- `make test` runs both suites sequentially

### How Token Extraction Works

Smoke tests use **pytest's `caplog` fixture** to extract verification and password reset tokens from application logs:

1. **EmailService logs tokens** in development mode (plain text in log messages)
2. **pytest's caplog captures** all log records during test execution
3. **Tests extract tokens** by searching caplog.records for URL patterns
4. **Works everywhere**: Docker containers, CI/CD, local development

**Example**:

```python
# Register user and capture logs
with caplog.at_level(logging.INFO):
    response = client.post("/api/v1/auth/register", json={...})

# Extract token from captured logs (after with block closes)
token = extract_token_from_caplog(caplog, "verify-email?token=")
```

**Benefits over shell script approach**:

- ✅ Works inside Docker containers (no Docker CLI needed)
- ✅ Works in all environments (dev, test, CI/CD)
- ✅ Pure pytest implementation (no subprocess calls)
- ✅ Better error messages and debugging
- ✅ Integrated with test framework

## Smoke Tests vs. Other Tests

| Test Type | Purpose | Scope | Duration | Frequency |
|-----------|---------|-------|----------|-----------|
| **Smoke** | Verify system is alive | Critical paths only | < 5 min | Every deployment |
| **Unit** | Test individual components | Single functions/classes | < 2 min | Every commit |
| **Integration** | Test component interactions | Multiple services | 5-15 min | Every commit |
| **E2E** | Test complete user journeys | All user flows | 10-30 min | Before release |

## Migration from Shell Script

These pytest-based smoke tests replace the previous `scripts/test-api-flows.sh` shell script.

**Benefits of pytest over shell script**:

- ✅ Better error messages and debugging
- ✅ Integrated with existing test framework
- ✅ Automatic test discovery
- ✅ JUnit XML output for CI/CD
- ✅ Code coverage integration
- ✅ Easier to maintain (Python vs. Bash)
- ✅ Reuses existing fixtures and utilities

## Adding New Smoke Tests

When adding new smoke tests:

1. **Mark with `@pytest.mark.smoke`** - REQUIRED for isolation
2. **Keep them fast** - Smoke tests should complete quickly (< 5 min total)
3. **Test critical paths** - Focus on essential functionality
4. **Use descriptive names** - `test_smoke_api_endpoint_works` not `test_1`
5. **Follow existing patterns** - Use the same fixture structure
6. **Document the test** - Include docstring explaining what's being tested

Example:

```python
@pytest.mark.smoke  # REQUIRED: Marks test for isolated session
def test_smoke_user_can_view_dashboard(client):
    \"\"\"Smoke: User can access their dashboard after login.\"\"\"
    # Smoke tests should be independent or use shared fixtures
    response = client.get(
        "/api/v1/dashboard",
        headers={"Authorization": "Bearer <token>"},
    )
    assert response.status_code == 200
    assert "accounts" in response.json()
```

## CI/CD Integration

Smoke tests are designed to run in CI/CD pipelines as a deployment gate:

```yaml
# Example GitHub Actions workflow
- name: Run Smoke Tests
  run: make ci-test tests/smoke/
  
- name: Deploy
  if: success()  # Only deploy if smoke tests pass
  run: make deploy
```

## Troubleshooting

**Smoke tests failing locally but passing in CI**:

- Ensure test database is clean: `make test-restart`
- Check environment variables: `env/.env.test`

**Smoke tests timing out**:

- Check database connection: `make test-status`
- Verify services are healthy: `docker compose -f compose/docker-compose.test.yml ps`

**Token/authentication errors**:

- Ensure fixtures are module-scoped: `@pytest.fixture(scope="module")`
- Check that `smoke_test_user` fixture completes successfully

## Related Documentation

- [Testing Strategy](../docs/development/testing/strategy.md)
- [Testing Guide](../docs/development/testing/guide.md)
- [API Flows (Manual Testing)](../docs/api-flows/)
- [Shell Script (Deprecated)](../../scripts/test-api-flows.sh)
