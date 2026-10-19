# Operating Algen Release Guard

## Before enabling CI gating

Review required check names/App IDs against the real repository. Protect the policy
and CI workflow on the trusted base branch. Never load a PR-authored `.env`, policy,
workflow, or agent package with production secrets. Install the pinned agent from a
trusted release and do not check out or execute candidate PR code.

Run in a disposable process with a dedicated OpenAI project and least-privilege
GitHub token. Permit outbound TLS to api.github.com and api.openai.com. The GitHub
adapter pins DNS sockets; the bundled Runtime OpenAI adapter uses a fixed HTTPS
endpoint and normal TLS validation, not the custom GitHub transport. Apply an
infrastructure egress policy if that boundary must be enforced outside the process.

Reports contain repository metadata and reviewer handles. Keep `reports/` private,
apply an explicit retention policy, and never include it in marketplace archives.
Model text is advisory. Automated gating must use the exit code and report schema;
do not parse Markdown or treat `PASS` as permission to deploy.

## Failure handling

| Symptom | Action |
|---|---|
| Exit 2 | Resolve deterministic blockers, then collect a new snapshot |
| Exit 3, INCOMPLETE | Check token scopes, GitHub rate limit, network, evidence truncation, and PR stability |
| Exit 3, model failed | Check OpenAI key/access/quota; evidence remains usable for manual review |
| Required check missing | Verify exact check name, App ID, event trigger, and head commit |
| Approvals insufficient | Current head needs a trusted non-author approval; stale approvals do not count |
| Mergeability unknown | Allow GitHub to compute it, then rerun; do not infer a pass |
| Interrupted | Discard incomplete outputs and rerun; the agent has no external write side effects |

All evidence has a freshness limit. After any new commit, review, CI rerun, or branch
rule change, rerun the assessment. GitHub does not expose a transactional snapshot
of all these endpoints; even a stable PR read cannot guarantee nothing changes
immediately after collection. GitHub's own merge protections remain required.

## Release and rollback

Run tests, lint, clean installation, dependency/secret scans and the live acceptance
matrix on each release. Record Python/OS, runtime version, source commit, package
digest, policy digest and live report IDs. The project is licensed under Apache-2.0
(`LICENSE`); report vulnerabilities as described in `SECURITY.md`.

Rollback by pinning an earlier reviewed package version and rerunning from fresh
evidence. Revoke exposed tokens through the relevant provider. Do not rewrite an
existing artifact under the same version. Report security issues through the final
publisher-owned security contact once selected; no contact has been invented here.
