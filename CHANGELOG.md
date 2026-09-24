# Changelog

All notable changes to the `bootstrap-iac` package are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Continuous integration hardening: the test suite runs across the full
  declared Python range (3.9 through 3.13); a built wheel is installed in
  isolation and smoke-tested so missing package data can no longer hide behind a
  source checkout; coverage is measured with a minimum threshold; dependency and
  secret scans run on pull requests; and all maintained Markdown is linted.
- `scripts/check_package_artifact.py` verifies a built wheel bundles every
  template listed in its manifest.
- `scripts/check_release.py` verifies the project version, the changelog entry,
  and the git tag agree.
- Release workflow: a tag push builds the distribution and runs the artifact and
  release checks before publishing artifacts.

## [0.1.0] - 2026-09-24

### Added

- Initial `bootstrap-iac` command-line tool: discovery, interview, generation,
  and validation of VS Code Copilot and Claude Code customisation files for
  Terraform infrastructure-as-code workspaces.
- Multi-cloud support (Azure, AWS, GCP) and multiple orchestration tools
  (Terragrunt, Terramate, Pulumi, or none).
- Bundled templates generated from the canonical `references/` source, with a
  manifest and an in-tree build backend that regenerates them at build time.
- Reproducible examples under `examples/generated/` with a drift check.
