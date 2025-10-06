# Flow Template

Use this template when adding a new manual API flow. Keep it focused on the user journey and include only the essential commands and validation tips.

## Purpose
- What is the user trying to accomplish?
- Why this flow exists and when to use it.

## Prerequisites
- Dev environment running with TLS
- Required environment variables set

```bash
# Dev environment (TLS)
make dev-up
BASE_URL=https://localhost:8000
CALLBACK_URL=https://127.0.0.1:8182
# Per-flow variables (example)
TEST_EMAIL='tester+'$(date +%s)'@example.com'
TEST_PASSWORD='SecurePass123!'
```

## Steps

### 1) Step title
- Brief explanation
```bash
# Quote-safe JSON via heredoc
cat <<JSON >/tmp/payload.json
{
  "key": "value"
}
JSON

curl -sk -X {METHOD} "$BASE_URL{/path}" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  --data-binary @/tmp/payload.json | python3 -m json.tool
```
Expected (snippet):
```json
{"key": "value"}
```

### 2) Step title
- Brief explanation
```bash
# command here
```

## Cleanup (optional)
- Commands to revert or remove test data

## Development: Token Extraction

**For flows requiring email-based tokens (verification, password reset):**

In development mode (`DEBUG=True`), emails are logged to console instead of being sent. Extract tokens from logs:

```bash
# View recent email logs
docker logs dashtam-dev-app --tail 100 2>&1 | grep -A 20 '📧 EMAIL'

# Look for the token in the URL:
# https://localhost:3000/verify-email?token=YOUR_TOKEN_HERE

# Extract and set the token
export VERIFICATION_TOKEN="<token-from-logs>"
```

**Why this works**: The `EmailService` automatically operates in development mode when `DEBUG=True`, logging all emails with full content including verification/reset tokens.

## Troubleshooting

- **SSL issues**: Use `-k` with curl to accept self-signed TLS certificates in dev
- **401 Unauthorized**: Access token expired or invalid → refresh or re-login
- **403 Forbidden**: Email not verified or account inactive
- **404 Not Found**: Check endpoint URL and ensure service is running
- **422 Validation Error**: Check request payload format and required fields
- **Missing tokens in logs**: Ensure development environment is running (`make dev-up`)
- **4xx/5xx errors**: Check environment variables, payloads, and application logs

## Related Flows

- Link to prerequisite flows (e.g., registration before login)
- Link to next step flows (e.g., login after email verification)
- Link to relevant architecture docs
