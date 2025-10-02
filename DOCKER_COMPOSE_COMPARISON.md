# Docker Compose Configuration Comparison

## Overview
Comparison between `docker-compose.test.yml` (local testing) and `docker-compose.ci.yml` (CI/CD pipeline)

## Key Differences

### 1. **Container Names & Network**
| Aspect | Test | CI | Impact |
|--------|------|----|----|
| Network name | `dashtam-test-network` | `dashtam-ci-network` | ✅ Isolation |
| Container prefix | `dashtam-test-*` | `dashtam-ci-*` | ✅ Isolation |
| Compose project name | `dashtam-test` | `dashtam-ci` | ✅ Isolation |

**Verdict:** ✅ Good - properly isolated

---

### 2. **Port Mappings**
| Service | Test | CI | Impact |
|---------|------|----|----|
| App | `8001:8000` | ❌ None | ⚠️ Different external access |
| PostgreSQL | `5433:5432` | ❌ None | ⚠️ Different external access |
| Redis | `6380:6379` | ❌ None | ⚠️ Different external access |
| Callback | `8183:8182` | ❌ Not included | 🚨 **MISSING SERVICE** |

**Verdict:** 🚨 **CRITICAL ISSUE** - CI doesn't have callback server at all!

---

### 3. **Environment Variables**
| Variable | Test | CI | Impact |
|----------|------|----|----|
| `DATABASE_URL` | ✅ Same | ✅ Same | ✅ Match |
| `REDIS_URL` | ✅ Same | ✅ Same | ✅ Match |
| `ENVIRONMENT` | `testing` | `testing` | ✅ Match |
| `LOG_LEVEL` | `INFO` | `WARNING` | ⚠️ Different verbosity |
| `API_BASE_URL` | `http://localhost:8001` | ❌ **MISSING** | 🚨 **CRITICAL** |
| `CALLBACK_BASE_URL` | `http://127.0.0.1:8183` | ❌ **MISSING** | 🚨 **CRITICAL** |
| `CI` | Not set | `true` | ℹ️ Info only |
| `TESTING` | `true` | `true` | ✅ Match |
| `DISABLE_EXTERNAL_CALLS` | `true` | `true` | ✅ Match |
| `MOCK_PROVIDERS` | `true` | `true` | ✅ Match |
| `.env` file | `.env.test` | `.env.ci` | ⚠️ Different configs |

**Verdict:** 🚨 **CRITICAL** - Missing essential environment variables in CI

---

### 4. **Service Configuration**

#### App Service
| Aspect | Test | CI | Impact |
|--------|------|----|----|
| Dockerfile target | `development` | `development` | ✅ Match |
| Command | `tail -f /dev/null` (wait) | Runs tests & exits | ⚠️ Different behavior |
| Volumes | Read-write | Read-only | ⚠️ Different permissions |
| Init DB | Manual | Via `init_test_db.py` | ⚠️ Different initialization |

**Verdict:** ⚠️ Different workflows but intentional for CI

#### Callback Service
| Aspect | Test | CI | Impact |
|--------|------|----|----|
| Exists? | ✅ Yes | ❌ **NO** | 🚨 **CRITICAL MISSING SERVICE** |
| Target | `callback` | N/A | Tests requiring OAuth will fail |
| Environment | Has `API_BASE_URL` | N/A | Cannot communicate with app |

**Verdict:** 🚨 **CRITICAL** - Callback service completely missing from CI

---

### 5. **PostgreSQL Configuration**
| Setting | Test | CI | Impact |
|---------|------|----|----|
| Storage | `tmpfs` | `tmpfs` | ✅ Match |
| Extra settings | Default | Speed-optimized | ⚠️ CI sacrifices durability |
| `fsync` | on (default) | off | ⚠️ Faster but unsafe |
| `synchronous_commit` | on (default) | off | ⚠️ Faster but unsafe |
| Healthcheck interval | 5s | 2s | ℹ️ CI more aggressive |

**Verdict:** ⚠️ Acceptable for CI (speed over safety)

---

### 6. **Test Execution**
| Aspect | Test | CI | Impact |
|--------|------|----|----|
| Execution method | Manual `pytest` | Auto-run in command | ⚠️ Different |
| Exit behavior | Stays running | Exits after tests | ⚠️ Different |
| Coverage reports | Optional | Always generated | ℹ️ CI generates reports |
| Test failure handling | `--maxfail=5` in CI | None in test | ⚠️ Different |

**Verdict:** ⚠️ Intentionally different for CI automation

---

## 🚨 CRITICAL ISSUES FOUND

### Issue #1: Missing Callback Service in CI
**Problem:** `docker-compose.ci.yml` does not include the OAuth callback server that exists in `docker-compose.test.yml`

**Impact:** 
- Any tests that involve OAuth flows will fail
- API endpoints that depend on callback redirects cannot be tested
- Tests expecting callback server communication will fail with connection errors

**Solution:** Add callback service to CI compose file

### Issue #2: Missing Environment Variables in CI
**Problem:** CI config missing:
- `API_BASE_URL` 
- `CALLBACK_BASE_URL`

**Impact:**
- Application may not know its own URL
- OAuth flows cannot construct callback URLs
- Tests may fail due to undefined environment variables

**Solution:** Add missing environment variables to CI app service

### Issue #3: Different .env Files
**Problem:** Test uses `.env.test`, CI uses `.env.ci` which may have different configurations

**Impact:**
- Environment variable mismatches between local and CI
- Tests passing locally but failing in CI due to config differences

**Solution:** Ensure `.env.ci` has all variables that `.env.test` has

---

## Recommendations

### High Priority (Breaking Tests)
1. ✅ **Add callback service to `docker-compose.ci.yml`**
   - Copy from test compose but without port mappings (internal only)
   - Ensure it has correct `API_BASE_URL` pointing to `app:8000`

2. ✅ **Add missing environment variables to CI app service**
   - `API_BASE_URL: http://app:8000` (internal Docker network)
   - `CALLBACK_BASE_URL: http://callback:8182` (internal Docker network)

3. ✅ **Verify .env.ci exists and has all required variables**
   - Check against `.env.ci.example`
   - Ensure parity with `.env.test` for test-relevant variables

### Medium Priority (Consistency)
4. ⚠️ **Consider using same initialization method**
   - Test: Manual pytest execution
   - CI: Auto-runs with init_test_db.py
   - Recommendation: Use same init method for parity

5. ⚠️ **Match LOG_LEVEL** (optional)
   - Test: INFO
   - CI: WARNING
   - Lower verbosity in CI is fine for performance, but consider INFO for debugging failures

### Low Priority (Nice to Have)
6. ℹ️ **Document differences clearly**
   - Current documentation is good
   - Add "CI vs Test differences" section to README.md

---

## Environment Parity Analysis

### Should CI Match Development/Production?

**Best Practice:** Yes, with intentional exceptions for CI optimization.

**Current Status:**

| Aspect | Dev | Test | CI | Prod (Future) | Status |
|--------|-----|------|----|----|--------|
| Python version | 3.13 | 3.13 | 3.13 | 3.13 | ✅ |
| PostgreSQL version | 17.6 | 17.6 | 17.6 | 17.6 | ✅ |
| Redis version | 8.2.1 | 8.2.1 | 8.2.1 | 8.2.1 | ✅ |
| Docker target | development | development | development | production | ⚠️ CI should match prod target |
| Services | All | All | ❌ Missing callback | All | 🚨 Fix needed |
| Environment vars | Full set | Full set | ❌ Incomplete | Full set | 🚨 Fix needed |
| Database persistence | Yes | No (tmpfs) | No (tmpfs) | Yes | ✅ Appropriate |
| Port mappings | Yes | Yes | No | Yes | ✅ Appropriate for CI |

**Recommendation:** 
- ✅ CI should test with **production Docker target** instead of development
- 🚨 CI must have **all services** that production will have
- ✅ CI can have **optimizations** (tmpfs, no ports) as long as they don't affect test validity

---

## Summary

### What's Working ✅
- Version parity (Python, PostgreSQL, Redis)
- Network isolation
- Database speed optimizations in CI
- Test environment variables mostly complete

### What's Broken 🚨
1. **Callback service missing in CI** - Causes OAuth test failures
2. **Missing environment variables in CI** - Causes undefined variable errors
3. **Different service configuration** - May cause integration test failures

### Next Steps
1. Update `docker-compose.ci.yml` to add callback service
2. Add missing environment variables to CI
3. Verify `.env.ci.example` has all required variables
4. Re-run CI tests to confirm fixes
5. Consider using production Docker target in CI for better parity
