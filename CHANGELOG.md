# Changelog

All notable changes to MagicReview will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning while it is prepared for public release.

## [Unreleased]

## [0.1.3] - 2026-06-14

### Fixed

- Excluded virtual environments, site-packages, dependency folders, build outputs, and local MagicReview data directories from project scanning.
- Fixed project review recursion failures when running `mgreview project .` from directories containing `.venv_testpypi` or other virtual environments.

## [0.1.2] - 2026-06-14

### Fixed

- Added missing runtime dependency `httpx` so installed `mgreview file/project` commands work from TestPyPI/PyPI installations.

## [0.1.1] - 2026-06-11

### Changed

- Renamed the project from ReviewAgent to MagicReview.
- Replaced old CLI/package naming with `magicreview` and `mgreview`.
- Added the new primary CLI command `mgreview`.
- Updated environment variable prefix to `MGREVIEW_`.
- Updated default data directory to `.magicreview`.

## [0.1.0] - 2026-06-09

### Added

- Local CLI review commands.
- Diff, file, and project review.
- Enterprise YAML/JSON rule center.
- Optional LLM architecture review.
- MCP stdio server.
- Multi-agent review platform.
- GitHub App integration.
- Local Dashboard and SQLite persistence.
- Connected services network policy.

### Security

- Local-first default.
- LLM disabled by default.
- Explicit network authorization policy.



