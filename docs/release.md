# Release Guide

MagicReview releases are distributed through GitHub Releases first. PyPI publishing is prepared but not enabled by default.

## Versioning

MagicReview uses semantic versioning while preparing for public releases.

- Patch: bug fixes and packaging-only updates.
- Minor: compatible feature additions.
- Major: incompatible CLI, API, or storage changes.

The current version is defined in:

- `pyproject.toml`
- `magicreview/_version.py`

Both values must match before tagging a release.

## Update The Changelog

Update `CHANGELOG.md` before every release.

Use the Keep a Changelog sections:

- Added
- Changed
- Fixed
- Security

## Local Build

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[all,dev]"
pytest --basetemp=.pytest_tmp
mgreview --help
mgreview --version
python -m build
twine check dist/*
```

## Local Quality Gate

Run the Python/package quality gate:

```bash
python scripts/quality_gate.py
```

Include Docker checks when Docker is installed and running:

```bash
python scripts/quality_gate.py --docker
```

The script covers tests, core CLI smoke commands, package build, `twine check`,
and optionally Docker build/run plus `docker compose config`. It uses
`python -m build --no-isolation`, so run `pip install -e ".[all,dev]"` first.

The quality gate keeps MagicReview offline by default. Do not set real LLM or
GitHub credentials for normal release validation.

## CI Quality Gates

GitHub Actions workflows:

- `test.yml`: installs `.[all,dev]`, runs pytest, and smoke-tests CLI commands.
- `lint.yml`: runs `ruff check magicreview tests`.
- `package.yml`: builds wheel/sdist, runs `twine check`, installs the wheel, and smoke-tests console scripts.
- `docker.yml`: builds the Docker image, smoke-tests CLI commands in the image, and validates Compose config.
- `release.yml`: runs tests, builds distributions, checks artifacts, and creates a GitHub Release on `v*` tags.

CI sets offline defaults:

```bash
MGREVIEW_LLM_PROVIDER=none
MGREVIEW_NETWORK_ENABLED=false
MGREVIEW_ALLOW_LLM=false
MGREVIEW_CODE_SHARING_MODE=none
```

CI does not require OpenAI, Anthropic, GitHub App, or webhook secrets.

## Build Wheel And Sdist

```bash
python -m build
twine check dist/*
```

The package should include Dashboard templates, static files, prompt templates,
README, LICENSE, CHANGELOG, docs, and examples in the sdist.

## Create A GitHub Release

Tag and push the version:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow will:

1. Run tests.
2. Build wheel and sdist.
3. Run `twine check`.
4. Create a GitHub Release.
5. Upload `dist/*` as release assets.

## Optional PyPI Publishing

PyPI publishing is intentionally not enabled by default.

Future releases can use either:

- PyPI Trusted Publishing from GitHub Actions.
- A `PYPI_API_TOKEN` repository secret.

Do not commit PyPI tokens or API keys.

No workflow publishes to PyPI by default in Phase 11.8.

## Docker Release Note

Phase 11.2 adds Docker packaging. Before tagging a release, verify:

```bash
docker build -t magicreview .
docker run --rm magicreview mgreview --help
docker run --rm magicreview mgreview --version
docker compose config
```

The Docker image defaults to offline operation. It should not include `.env`,
`.magicreview`, local databases, API keys, or GitHub private keys.

## Rollback

If a release has a critical issue:

1. Delete or mark the GitHub Release as pre-release.
2. Communicate the affected version in `CHANGELOG.md`.
3. Patch the issue.
4. Release a new patch version.

Avoid rewriting public tags unless the release was never consumed.

## Pre-Release Checklist

- `pytest --basetemp=.pytest_tmp`
- `mgreview --help`
- `mgreview --version`
- `mgreview project examples/multi_agent_project --agents --format json`
- `python -m build`
- `twine check dist/*`
- `docker build -t magicreview .`
- `docker compose config`
- `CHANGELOG.md` updated
- `pyproject.toml` version updated
- `magicreview/_version.py` version updated
- Git tag pushed




