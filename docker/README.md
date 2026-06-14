# MagicReview Docker Guide

MagicReview can run as a local CLI image, Dashboard service, GitHub App webhook service, or MCP stdio server.

MagicReview is offline by default. The Docker image does not include `.env`, local databases, API keys, or GitHub private keys.

## Build

```bash
docker build -t magicreview .
```

## CLI

```bash
docker run --rm magicreview mgreview --help
docker run --rm magicreview mgreview --version
docker run --rm -v "$PWD:/workspace" magicreview mgreview project /workspace --format json
```

## Dashboard

```bash
docker compose up dashboard
```

Dashboard data is stored in `./.magicreview` by default.

## GitHub App

```bash
docker compose up github-app
```

Use `MGREVIEW_GITHUB_REVIEW_MODE=diff_only` for the default mode or `MGREVIEW_GITHUB_REVIEW_MODE=full_project` when full project fetch is explicitly allowed.

## MCP

```bash
docker compose --profile mcp up mcp
```

The underlying command is `mgreview mcp`.

## Environment

Use `MGREVIEW_` variables:

```bash
MGREVIEW_DB_PATH=/data/magicreview.db
MGREVIEW_LLM_PROVIDER=none
MGREVIEW_NETWORK_ENABLED=false
MGREVIEW_ALLOW_LLM=false
MGREVIEW_CODE_SHARING_MODE=none
MGREVIEW_AUTH_ENABLED=false
```

Do not bake private keys into the image. Inject `GITHUB_PRIVATE_KEY` through your deployment secret manager or `.env`.
