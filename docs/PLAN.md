# Algen Release Guard — implementation and publication plan

Prepared 19 October 2026. User-selected use case: GitHub release readiness.
Requested home: `workspace/ai-agent/runtime-examples/algen-release-guard`.

## 1. Product and scope

Audience: maintainers and release engineers who repeatedly inspect pull requests
before merging a release candidate. Input: one allowlisted `owner/repo`, positive
PR number, and a reviewed JSON release policy. Output: timestamped `PASS`,
`BLOCKED`, or `INCOMPLETE` assessment, evidence, and actionable explanation.

Version one is a customer-run Python package for a local machine or CI worker.
It assesses PR readiness, not an entire release train. It does not perform source
code security review, infer production health, certify regulatory compliance,
interpret every GitHub ruleset, or make deployment decisions. These boundaries
must appear in the marketplace listing rather than be hidden in implementation.

## 2. Architecture and real integrations

1. Validate inputs and resolve `.env` references locally. Require an explicit
   repository allowlist and explicit check policy.
2. Execute the typed `github.release_evidence` tool through Algen's `ToolExecutor`.
   Fetch PR metadata, current-head check runs and commit statuses, review history,
   and changed-file counts. Do not fetch source blobs, patches, or review bodies
   for model use. Re-read PR state after collection.
3. Apply deterministic rules: open and non-draft PR, clean GitHub mergeability,
   stable head/base/state, complete and fresh evidence, required successful checks
   from the configured App, current-commit trusted approvals, no outstanding
   change requests, and bounded change size.
4. Call OpenAI through Algen's configured provider using
   `gpt-4.1-mini-2025-04-14`. Request structured explanation items keyed to known
   findings. Validate the schema, exact finding coverage, and evidence IDs again
   in application code. The model has no verdict field and no tools.
5. Recheck evidence age, then atomically save a JSON report and escaped Markdown
   rendering. Use unique IDs; preserve evidence on model failure; return CI-friendly
   exit codes. Include content hashes for later comparison, not as signatures.

The dependency is exactly `algen-agent-runtime==0.1.0a7`, verified on PyPI.
The published wheel SHA-256 observed during preparation is
`b8c7910d1a9d37abc46a5a356062d5bc81ec2256b1cf932114a3c985e2938f91`.
Runtime core and Studio source are not modified or vendored into this application.

## 3. Security and governance

- GitHub access is read-only and scoped to selected repositories. Required check
  names bind to a trusted App ID; legacy statuses have a documented weaker identity
  boundary. Do not trust arbitrary checks with a familiar name.
- GitHub host and URL paths are fixed/validated, redirects disabled, private networks
  denied, DNS sockets pinned through Runtime. No caller-supplied API URLs.
- GitHub data and model prose are untrusted. No execution or instruction following
  from repository content. Markdown escapes untrusted text. Citations are constructed
  from the validated repository/PR, not arbitrary returned URLs.
- Only generic deterministic assessment data is sent to OpenAI. GitHub credentials
  go only to GitHub and the OpenAI key only to OpenAI. No secrets in listings,
  archives, logs, test fixtures, or reports.
- Limits: 40 HTTP attempts, 10 pages per collection, 2 MB per HTTP response,
  512 KB normalized tool result, 10-second HTTP timeouts, 90-second tool deadline,
  and 180-second job deadline. Retry transient GET failure at most once. Rate
  limits and denied access fail closed rather than retry indefinitely.
- Model limits: 12,000 total token budget, 2,000 output tokens, 60-second agent
  latency budget, one provider attempt, no repair loop. The configured $0.10 runtime
  cost budget is an additional guard, not a guaranteed billing ceiling; token and
  call bounds are explicit. Set account/project spend controls independently.
- No hosted authentication surface exists in v1. OS/CI isolation protects the
  process and credentials. No cross-user state or persistent conversation memory.

## 4. Acceptance gates before production use

| Gate | Required evidence |
|---|---|
| Published-runtime compatibility | Installed wheel version exactly 0.1.0a7; YAML loads through its models |
| Deterministic correctness | Passing, blocked, unknown, stale, denied, moved-head, mismatched-App, stale-review, and pagination cases pass |
| Provider integration | Real OpenAI request succeeds with configured account; refusal, invalid JSON/citations, timeout, and unavailable-provider tests fail safely |
| GitHub integration | Real selected PR evidence matches GitHub UI/API at the recorded head/base commits |
| No false pass | Missing/truncated evidence, pending required checks, revoked/stale approvals, unknown mergeability cannot yield PASS |
| Reproducible delivery | Build/install wheel in a clean environment; archive contains no secrets; dependencies and hashes recorded |
| Deployment acceptance | Run on intended CI OS/Python, verify outbound access, token permissions, report retention, exit-code gating and interruption recovery |
| Security | Secret scan and dependency audit of final locked release; fix or explicitly resolve findings before release |
| Marketplace | Final source commit, artifact digest, identity/support/security links, actual assessment receipt, reviewable listing |

Passing local tests is necessary but does not establish operational production
readiness. Runtime's own production roadmap still records hardening gaps. This
application limits the deployment scope to a single-user, read-only process and
must not inherit claims of hardened multitenant hosting or exactly-once side effects.

## 5. Marketplace delivery and publication sequence

1. Review the application behavior, live acceptance report, known limitations,
   support ownership, distribution license, and operating instructions with the user.
2. Select a dedicated public GitHub repository and publisher identity. Prepare a
   secret-free initial source release; use DCO-signed commits. No current private
   Runtime history is copied. Public source creation/push remains a separate action.
3. Run CI on the final source commit, build the package, pin/review the dependency
   resolution for supported platforms, scan dependencies/secrets, produce checksums
   and provenance, and host the immutable artifact at an actual HTTPS download URL.
4. Run AgentStripes on that exact public repository/commit. The live Agent Hub
   advertises at least two stripes for listing. Do not invent a score, receipt,
   verified badge, or production history. If the assessment fails, resolve it first.
5. Complete the `algen-marketplace-manifest/v1` and publish form with real package ID,
   version, maintainer/contact, chosen license, category, runtime, source repository,
   security reporting URL, artifact URL/digest/size, and `algen_release_guard.cli:main`
   entrypoint. Disclose GitHub/OpenAI dependencies, model charges, credentials, data
   handling, execution boundary, and unverified Studio compatibility.
6. Present the exact listing, artifact hash, public-source commit, live-test evidence,
   assessment receipt, and remaining limitations to the user before publication.
7. Publish only after the user's final publication instruction. Verify the visible
   listing and download hash afterward. A rejected submission stays unpublished.

The local marketplace schema requires ownership/security/delivery fields that
cannot honestly be completed with invented URLs or identity. Draft metadata is
deliberately incomplete until those publication facts exist.

## 6. Operations, support, and later versions

Operate one assessment per process. On interruption or GitHub changes, collect
again; never resume a stale passing snapshot. Keep JSON reports with the same
retention as private CI logs (recommended starting point: seven days). Revoke
compromised credentials and rerun affected assessments. Pin previous known-good
agent/runtime versions to roll back; never reuse a release version for changed bytes.

Future versions can add a GitHub App token broker, branch-rules/CODEOWNERS resolution,
merge-queue awareness, signed attestations, and an authenticated hosted service.
Each expands scope and needs dedicated tests and operating evidence. Automatic
merge/release/deploy is outside this version and requires a new approval model.

## 7. Sources used

- [Published Runtime 0.1.0a7](https://pypi.org/project/algen-agent-runtime/0.1.0a7/)
- [Agent Hub](https://agents.algen.ai/) — live listing and AgentStripes requirements
- [OpenAI model](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GitHub check runs](https://docs.github.com/en/rest/checks/runs)
- Runtime local agent-builder/connector skills and production-readiness documentation
- Local Agent Hub v1 manifest schema and publish form, inspected read-only
