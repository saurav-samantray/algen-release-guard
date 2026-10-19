# Validation evidence — 19 October 2026

Tested on macOS arm64, CPython 3.12, in an isolated virtual environment installed
from PyPI. Runtime version: `0.1.0a7`. No editable Runtime checkout was used.

## Completed

- Runtime YAML validated through the published `AppSettings` model.
- 66 offline tests passed, including an actual Runtime OpenAI provider
  invocation against a controlled HTTP transport, cancellation, provider failure,
  evidence preservation, output escaping, and private atomic report writes.
- Wheel and source distribution built; wheel installed and CLI configuration
  validation executed successfully.
- Ruff lint and formatting passed.
- Gitleaks 8.30.1 `detect --no-git --verbose --redact` found no leaks in the staged
  project. The official downloaded binary was verified against its release checksum.
- Marketplace manifest generation passed the local v1 JSON schema using test-only
  identity/URLs. That test manifest is not shipped as a real listing.
- `pip-audit` found no known vulnerabilities in 43 exact runtime dependencies.
  This is a point-in-time database result, not a security guarantee. The dependency
  snapshot is macOS/Python 3.12-specific; it is not a cross-platform hash lock.
- Real GitHub and OpenAI acceptance run completed for `AlgenAI/algen-agent-runtime`
  PR #24 at head `f5f974b8039c880764c9eb51fd230ad924e6f8b7`.
  Agent report ID: `2fb5c9f9-9d34-4bac-a5bd-a8356f3dbdf8`.
  Result: `BLOCKED`; model explanation completed. Six GitHub requests, one model
  call, 393 input tokens, 256 output tokens, zero retries. Runtime's reported zero
  estimated cost is **not** evidence that the API call was free.
- Live findings: GitHub did not report clean mergeability; the required container
  check failed; observed checks were not all successful; trusted current-head
  approvals were insufficient. This is a validated blocked-path result, not a live
  passing-path acceptance or a statement about the PR's later state.

The raw live report is private local operational data under `reports/` and is
excluded from the distributable archive. The recorded PR/commit above is a
validation reference, not the agent's source provenance.

## Still required for publication/production acceptance

- Live positive-path and operational failure drills on the intended CI deployment.
- Linux/Python 3.13 CI execution (workflow supplied, not executed in this session).
- Review of trusted policy and exact release dependency resolution for the target OS.
- Final publisher identity, license, dedicated source repository, support/security
  contact, immutable artifact URL, and source release provenance.
- AgentStripes assessment of that final public source commit and actual receipt.
- User review of the final listing and publication instruction.

No public listing, source push, or deployment has been performed. No production
history or independent certification is claimed.
