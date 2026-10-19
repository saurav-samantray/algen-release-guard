# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Apache-2.0 licence, security policy and this changelog.
- Run tracing with Traccia (spans tied to run IDs, PII redacted, no content), exported to
  `api.traccia.ai`; `TRACCIA_API_KEY` is optional.

## [0.2.0]

### Added

- `release-readiness` workflow on Algen Agent Runtime: collects allowlisted GitHub pull request
  evidence, applies the operator's release policy deterministically, and has the
  `release-explainer` agent explain each finding with evidence IDs.
- Explicit owner/repo allowlist and a release policy that comes only from the operator's
  environment (`RELEASE_GUARD_POLICY`), never from run inputs.
- Evidence-only runs that skip the model, and reports that keep the evidence when the
  explanation fails.
- JSON and escaped Markdown reports with owner-only file permissions.
- Algen Studio import and marketplace export: the hook provider's sources are declared under
  `extensions.studio.export_assets`.
- Locked dependencies (`requirements.lock`) and CI.

[Unreleased]: https://github.com/saurav-samantray/algen-release-guard/compare/f91f6a5...HEAD
[0.2.0]: https://github.com/saurav-samantray/algen-release-guard/tree/f91f6a5
