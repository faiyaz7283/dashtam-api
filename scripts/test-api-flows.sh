#!/usr/bin/env bash
#
# Comprehensive API Flow Smoke Test
# Tests all commands from docs/api-flows/ for copy-paste accuracy
#
# Usage: ./scripts/test-api-flows.sh
#
# Requirements:
# - Development environment running (make dev-up)
# - Clean database (or unique test email)
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Test results array
declare -a FAILED_TESTS

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Dashtam API Flow Smoke Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print test result
test_result() {
    local test_name="$1"
    local result="$2"
    local details="$3"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    if [ "$result" -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo -e "  ${RED}Details: $details${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$test_name")
    fi
}

# Function to extract JSON field
extract_json() {
    local json="$1"
    local field="$2"
    echo "$json" | grep -o "\"$field\":\"[^\"]*\"" | cut -d'"' -f4 | head -1
}

# Setup environment variables
export BASE_URL="https://localhost:8000"
export TEST_EMAIL="smoke-test-$(date +%s)@example.com"
export TEST_PASSWORD="SecurePass123!"
export FRONTEND_URL="https://localhost:3000"

echo -e "${YELLOW}Test Configuration:${NC}"
echo -e "  BASE_URL: $BASE_URL"
echo -e "  TEST_EMAIL: $TEST_EMAIL"
echo -e "  TEST_PASSWORD: $TEST_PASSWORD"
echo ""

# Test 1: User Registration
echo -e "${BLUE}Test 1: User Registration${NC}"
REG_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"name\": \"Smoke Test User\"
  }")

HTTP_CODE=$(echo "$REG_RESPONSE" | tail -1)
REG_BODY=$(echo "$REG_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    USER_ID=$(extract_json "$REG_BODY" "id")
    test_result "Registration (HTTP 201)" 0
else
    test_result "Registration (HTTP 201)" 1 "Got HTTP $HTTP_CODE"
fi

# Test 2: Extract Verification Token from Logs
echo -e "${BLUE}Test 2: Extract Verification Token${NC}"
sleep 2  # Give logs time to appear

VERIFICATION_TOKEN=$(docker logs dashtam-dev-app --tail 200 2>&1 | \
    grep 'verify-email?token=' | \
    grep -o 'token=[^&" ]*' | \
    cut -d'=' -f2 | \
    tail -1)

if [ -n "$VERIFICATION_TOKEN" ]; then
    export VERIFICATION_TOKEN
    test_result "Token Extraction (from logs)" 0
else
    test_result "Token Extraction (from logs)" 1 "Token not found in logs"
fi

# Test 3: Email Verification
echo -e "${BLUE}Test 3: Email Verification${NC}"
if [ -n "$VERIFICATION_TOKEN" ]; then
    VERIFY_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/verify-email" \
      -H "Content-Type: application/json" \
      -d "{
        \"token\": \"$VERIFICATION_TOKEN\"
      }")
    
    HTTP_CODE=$(echo "$VERIFY_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        test_result "Email Verification (HTTP 200)" 0
    else
        test_result "Email Verification (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "Email Verification (HTTP 200)" 1 "Skipped (no token)"
fi

# Test 4: Login
echo -e "${BLUE}Test 4: Login${NC}"
LOGIN_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\"
  }")

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -1)
LOGIN_BODY=$(echo "$LOGIN_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    ACCESS_TOKEN=$(extract_json "$LOGIN_BODY" "access_token")
    REFRESH_TOKEN=$(extract_json "$LOGIN_BODY" "refresh_token")
    export ACCESS_TOKEN
    export REFRESH_TOKEN
    test_result "Login (HTTP 200)" 0
else
    test_result "Login (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
fi

# Test 5: Get Profile
echo -e "${BLUE}Test 5: Get User Profile${NC}"
if [ -n "$ACCESS_TOKEN" ]; then
    PROFILE_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/auth/me" \
      -H "Authorization: Bearer $ACCESS_TOKEN")
    
    HTTP_CODE=$(echo "$PROFILE_RESPONSE" | tail -1)
    PROFILE_BODY=$(echo "$PROFILE_RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        EMAIL_FROM_PROFILE=$(extract_json "$PROFILE_BODY" "email")
        if [ "$EMAIL_FROM_PROFILE" = "$TEST_EMAIL" ]; then
            test_result "Get Profile (HTTP 200, correct email)" 0
        else
            test_result "Get Profile (HTTP 200, correct email)" 1 "Email mismatch"
        fi
    else
        test_result "Get Profile (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "Get Profile" 1 "Skipped (no access token)"
fi

# Test 6: Update Profile
echo -e "${BLUE}Test 6: Update Profile${NC}"
if [ -n "$ACCESS_TOKEN" ]; then
    UPDATE_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X PATCH "$BASE_URL/api/v1/auth/me" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"name\": \"Updated Smoke Test\"
      }")
    
    HTTP_CODE=$(echo "$UPDATE_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        test_result "Update Profile (HTTP 200)" 0
    else
        test_result "Update Profile (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "Update Profile" 1 "Skipped (no access token)"
fi

# Test 7: Token Refresh
echo -e "${BLUE}Test 7: Token Refresh${NC}"
if [ -n "$REFRESH_TOKEN" ]; then
    REFRESH_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/refresh" \
      -H "Content-Type: application/json" \
      -d "{
        \"refresh_token\": \"$REFRESH_TOKEN\"
      }")
    
    HTTP_CODE=$(echo "$REFRESH_RESPONSE" | tail -1)
    REFRESH_BODY=$(echo "$REFRESH_RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        NEW_ACCESS_TOKEN=$(extract_json "$REFRESH_BODY" "access_token")
        if [ -n "$NEW_ACCESS_TOKEN" ]; then
            export NEW_ACCESS_TOKEN
            test_result "Token Refresh (HTTP 200, new access token)" 0
        else
            test_result "Token Refresh (HTTP 200, new access token)" 1 "No access token in response"
        fi
    else
        test_result "Token Refresh (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "Token Refresh" 1 "Skipped (no refresh token)"
fi

# Test 8: Verify new access token works
echo -e "${BLUE}Test 8: Verify New Access Token${NC}"
if [ -n "$NEW_ACCESS_TOKEN" ]; then
    VERIFY_TOKEN_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/auth/me" \
      -H "Authorization: Bearer $NEW_ACCESS_TOKEN")
    
    HTTP_CODE=$(echo "$VERIFY_TOKEN_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        test_result "New Access Token Works (HTTP 200)" 0
    else
        test_result "New Access Token Works (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "New Access Token Works" 1 "Skipped (no new token)"
fi

# Test 9: Password Reset Request
echo -e "${BLUE}Test 9: Password Reset Request${NC}"
RESET_REQUEST_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/password-resets/" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\"
  }")

HTTP_CODE=$(echo "$RESET_REQUEST_RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "202" ]; then
    test_result "Password Reset Request (HTTP 202)" 0
else
    test_result "Password Reset Request (HTTP 202)" 1 "Got HTTP $HTTP_CODE"
fi

# Test 10: Extract Reset Token from Logs
echo -e "${BLUE}Test 10: Extract Reset Token${NC}"
sleep 2  # Give logs time to appear

RESET_TOKEN=$(docker logs dashtam-dev-app --tail 200 2>&1 | \
    grep 'reset-password?token=' | \
    grep -o 'token=[^&" ]*' | \
    cut -d'=' -f2 | \
    tail -1)

if [ -n "$RESET_TOKEN" ]; then
    export RESET_TOKEN
    test_result "Reset Token Extraction (from logs)" 0
else
    test_result "Reset Token Extraction (from logs)" 1 "Token not found in logs"
fi

# Test 11: Verify Reset Token
echo -e "${BLUE}Test 11: Verify Reset Token${NC}"
if [ -n "$RESET_TOKEN" ]; then
    VERIFY_RESET_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/password-resets/$RESET_TOKEN")
    
    HTTP_CODE=$(echo "$VERIFY_RESET_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        test_result "Verify Reset Token (HTTP 200)" 0
    else
        test_result "Verify Reset Token (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "Verify Reset Token" 1 "Skipped (no reset token)"
fi

# Test 12: Confirm Password Reset
echo -e "${BLUE}Test 12: Confirm Password Reset${NC}"
export NEW_PASSWORD="NewSecurePass456!"

if [ -n "$RESET_TOKEN" ]; then
    CONFIRM_RESET_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X PATCH "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"new_password\": \"$NEW_PASSWORD\"
      }")
    
    HTTP_CODE=$(echo "$CONFIRM_RESET_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        test_result "Confirm Password Reset (HTTP 200)" 0
    else
        test_result "Confirm Password Reset (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "Confirm Password Reset" 1 "Skipped (no reset token)"
fi

# Test 13: Login with New Password
echo -e "${BLUE}Test 13: Login with New Password${NC}"
LOGIN2_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$NEW_PASSWORD\"
  }")

HTTP_CODE=$(echo "$LOGIN2_RESPONSE" | tail -1)
LOGIN2_BODY=$(echo "$LOGIN2_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    ACCESS_TOKEN2=$(extract_json "$LOGIN2_BODY" "access_token")
    REFRESH_TOKEN2=$(extract_json "$LOGIN2_BODY" "refresh_token")
    export ACCESS_TOKEN2
    export REFRESH_TOKEN2
    test_result "Login with New Password (HTTP 200)" 0
else
    test_result "Login with New Password (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
fi

# Test 14: Logout
echo -e "${BLUE}Test 14: Logout${NC}"
if [ -n "$ACCESS_TOKEN2" ] && [ -n "$REFRESH_TOKEN2" ]; then
    LOGOUT_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/logout" \
      -H "Authorization: Bearer $ACCESS_TOKEN2" \
      -H "Content-Type: application/json" \
      -d "{
        \"refresh_token\": \"$REFRESH_TOKEN2\"
      }")
    
    HTTP_CODE=$(echo "$LOGOUT_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        test_result "Logout (HTTP 200)" 0
    else
        test_result "Logout (HTTP 200)" 1 "Got HTTP $HTTP_CODE"
    fi
else
    test_result "Logout" 1 "Skipped (no access token)"
fi

# Test 15: Verify Refresh Token Revoked
echo -e "${BLUE}Test 15: Verify Refresh Token Revoked${NC}"
if [ -n "$REFRESH_TOKEN2" ]; then
    REVOKED_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/refresh" \
      -H "Content-Type: application/json" \
      -d "{
        \"refresh_token\": \"$REFRESH_TOKEN2\"
      }")
    
    HTTP_CODE=$(echo "$REVOKED_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "401" ]; then
        test_result "Refresh Token Revoked (HTTP 401)" 0
    else
        test_result "Refresh Token Revoked (HTTP 401)" 1 "Got HTTP $HTTP_CODE (expected 401)"
    fi
else
    test_result "Refresh Token Revoked" 1 "Skipped (no refresh token)"
fi

# Test 16: Verify Access Token Still Works
echo -e "${BLUE}Test 16: Verify Access Token Still Works After Logout${NC}"
if [ -n "$ACCESS_TOKEN2" ]; then
    STILL_VALID_RESPONSE=$(curl -k -s -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/auth/me" \
      -H "Authorization: Bearer $ACCESS_TOKEN2")
    
    HTTP_CODE=$(echo "$STILL_VALID_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        test_result "Access Token Still Valid (HTTP 200 - correct JWT behavior)" 0
    else
        test_result "Access Token Still Valid (HTTP 200)" 1 "Got HTTP $HTTP_CODE (JWT pattern may be broken)"
    fi
else
    test_result "Access Token Still Valid" 1 "Skipped (no access token)"
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Total Tests:  $TESTS_TOTAL"
echo -e "${GREEN}Passed:       $TESTS_PASSED${NC}"
echo -e "${RED}Failed:       $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}- $test${NC}"
    done
    exit 1
fi
