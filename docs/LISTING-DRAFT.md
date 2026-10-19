# Listing draft — not submitted

**Name:** Algen Release Guard

**Summary:** Read-only GitHub PR readiness checks with deterministic blockers and
evidence-linked OpenAI explanations.

**Version:** 0.2.0 (release candidate)

**Delivery:** Algen Runtime workflow `release-readiness` (`config/agent.yaml`) with a
workflow hook provider, runnable from the CLI entrypoint `algen_release_guard.cli:main`
or imported into Algen Studio (`workflow_hook_provider_v1`, hash-locked
`requirements.lock`). Requires Python 3.12+ and `algen-agent-runtime>=0.1.0a5,<0.2`;
tested on 0.1.0a5 and 0.1.0a7 (Studio's). Studio import, validation, and hook
execution are tested locally; hosted Studio execution is not certified.

**What the adopter gets:** Source, typed GitHub adapter, policy engine, Runtime/OpenAI
configuration, CLI, tests, CI workflow, operating guide, dependency snapshot, archive
builder, and manifest generator. JSON and Markdown reports reference actual GitHub
evidence and distinguish blockers from incomplete evidence.

**Permissions:** Read-only GitHub API access to an explicit repository allowlist;
local read/write for configuration and reports. No repository execution, shell
tools, comments, merges, tags, releases, or deployments.

**Data handling:** Repository/check/file metadata and reviewer handles stay in local
reports. OpenAI receives only deterministic generic findings and source labels.
Credentials are resolved from local environment variables. Reports remain until
the operator deletes them; CI deployments should configure retention. No telemetry
exporter or application training workflow is enabled. Third-party API processing
is subject to the operator's provider agreements.

**Costs:** Operator supplies GitHub/OpenAI access and pays applicable provider fees.
The package itself has no billing integration. Token counts are recorded; Runtime's
cost estimates are not billing records.

**Evidence:** 66 offline tests, a successful real GitHub/OpenAI blocked-path assessment,
wheel installation, configuration validation, lint/format, dependency audit and
secret scan. No AgentStripes rating, independent certification, live passing-path
acceptance, or production history is claimed.

**Limitations:** Timestamped snapshot under local policy. Does not completely evaluate
GitHub rulesets, CODEOWNERS, merge queues, code security, release compatibility, or
production health. GitHub protections and human release decisions remain required.

**Fields still needed:** Publisher ID/name/contact; distribution license; dedicated
public source repository and commit; immutable artifact download URL; support and
security reporting URLs; approved category; actual AgentStripes receipt. These must
be real values before publication. Review the completed manifest before submitting.
