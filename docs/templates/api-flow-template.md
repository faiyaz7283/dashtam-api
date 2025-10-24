# [API Flow Name]

[Brief 1-2 sentence description of what this API flow demonstrates]

---

<!-- TABLE OF CONTENTS

NOTE: MkDocs Material auto-generates the Table of Contents from headings.
Do NOT include a manual TOC section in your document.

The sections listed below are the REQUIRED top-level (##) sections for this template.
All other content must be organized as subsections (###, ####) under these main sections.

Required Top-Level Sections (in order):
- Purpose
- Prerequisites
- Steps
- Troubleshooting
- Related Flows
- Document Information

MkDocs will automatically create a clickable TOC sidebar from these headings.
-->

---

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

---

## Document Information

**Template:** [api-flow-template.md](api-flow-template.md)
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
