# MagicReview GitHub App Example

This folder documents local GitHub App development. It does not include real credentials.

## Environment

```bash
GITHUB_APP_ID=12345
GITHUB_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET="local-secret"
GITHUB_APP_NAME="MagicReview"
MGREVIEW_GITHUB_ENABLE_INLINE_COMMENTS=true
MGREVIEW_GITHUB_ENABLE_SUMMARY_COMMENT=true
MGREVIEW_GITHUB_MAX_INLINE_COMMENTS=30
```

## Start

```bash
python -m magicreview.integrations.github.app
```

Installed console script:

```bash
mgreview-github-app
```

## Webhook Payload Shape

```json
{
  "action": "opened",
  "installation": {"id": 123},
  "repository": {
    "name": "repo",
    "owner": {"login": "octo"}
  },
  "pull_request": {
    "number": 7,
    "head": {"sha": "head-sha"},
    "base": {"sha": "base-sha"}
  }
}
```

Use a tunnel such as ngrok for local GitHub webhook delivery:

```text
https://your-tunnel.example.com/webhook
```
