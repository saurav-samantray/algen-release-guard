# Algen Release Guard

A real, read-only GitHub pull-request readiness agent, packaged as a standard Algen
Runtime workflow (`release-readiness` in `config/agent.yaml`). It reads GitHub REST
APIs, applies explicit policy, and uses OpenAI to explain findings. The same workflow
runs from the CLI and in Algen Studio. There is no mock mode in the shipped CLI.
Mocks exist only in tests.

**Status: release candidate; publication and production acceptance are pending.**
See [the detailed plan](docs/PLAN.md) and [operating guide](docs/OPERATIONS.md).

## What it does

Given a repository, PR number, and operator-owned policy, it checks current-head CI,
trusted review approvals, mergeability, PR stability, evidence freshness, and change
size. It produces JSON evidence and an escaped Markdown assessment with canonical
GitHub links, policy/evidence hashes, timestamps, model usage, and limitations.

`PASS` means this snapshot met the supplied local policy. It does not authorize a
merge or certify a release. GitHub branch protection and human release decisions
remain authoritative. `BLOCKED` means a rule failed; `INCOMPLETE` means evidence
could not establish readiness. Missing checks never count as success.

The agent cannot merge, comment, create tags/releases, change settings, deploy,
run repository code, read patches, or execute shell commands.

## Install

Requires Python 3.12 or 3.13. From this folder:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

Skip the copy if `.env` already exists. Fill `OPENAI_API_KEY`, `GITHUB_TOKEN`, and
`RELEASE_GUARD_REPOSITORIES` locally. Environment variables take precedence over
`.env`; no ancestor-directory search is performed. Never commit `.env`.

Use a fine-grained token or GitHub App installation token scoped to selected
repositories with Metadata, Pull requests, Checks, Contents, and Commit statuses
read access as required by your token type. No write permission is needed.
Public repositories can run without a GitHub token but have lower rate limits.
Tokens must be renewed by the operator; the agent does not mint credentials.

Copy `policy.example.json` to `policy.json` and replace the check name with the
actual GitHub check-run name. `app_id: 15368` is the usual GitHub Actions app;
verify the ID from your repository's API response. Different CI publishers need
their own app ID. Every required check must be successful (not skipped/neutral).
Legacy commit statuses use `kind: "status", app_id: null`; GitHub write permission,
not an App ID binding, determines who can publish those statuses.

```sh
.venv/bin/algen-release-guard --validate-config
.venv/bin/algen-release-guard --repository OWNER/REPO --pr 123 --policy policy.json
```

An evidence-only run still reads real GitHub APIs but makes no OpenAI call:

```sh
.venv/bin/algen-release-guard --repository OWNER/REPO --pr 123 --policy policy.json --evidence-only
```

Reports use random run IDs under `reports/`, with owner-only file permissions.
`policy.algen-runtime.json` is the concrete policy used for the live Runtime PR
acceptance test. For that allowlisted repository, use it instead of the template.
Exit codes: `0` policy pass, `2` policy blocked, `3` incomplete/configuration/provider
failure, `130` interrupted. A model failure preserves evidence but exits `3`, even
if the deterministic assessment is `PASS`. Do not gate CI by grepping prose.

## Runtime and data boundary

`config/agent.yaml` is the authoritative model/governance contract and defines the
`release-readiness` workflow. Its nodes run in order:

| Node | Kind | What it does |
|---|---|---|
| `collect` | handler | Runs the typed `github.release_evidence` tool through Runtime's `ToolExecutor` (permission checks, schemas, limits, DNS-pinned safe HTTP) |
| `assess` | handler | Applies the operator policy deterministically |
| `explain` | agent | `release-explainer` explains findings with schema-checked JSON; skipped for evidence-only runs; a failure keeps the evidence report |
| `explained` | join | Continues whether the explanation ran, was skipped, or failed |
| `report` | handler | Re-checks evidence freshness, then builds the JSON report and escaped Markdown |

`algen_release_guard.workflow:create_workflow_hooks` is the hook provider. The CLI
runs the workflow through Runtime's `MultiAgentWorkflowExecutor`, exactly as Studio
does. The LLM has no tools and cannot set the verdict. Model calls use the provider's
default temperature, because Runtime workflow nodes do not set one; the schema and
evidence-ID validator reject any explanation that does not match the findings.

OpenAI receives only deterministic finding messages, IDs, and generic source
labels. It does not receive repository names, PR titles/bodies, code, filenames,
reviewer identities, credentials, or raw GitHub payloads. Evidence reports remain
local and include repository/file/check metadata and reviewer handles; restrict
access accordingly. No telemetry exporter is enabled by default.

This is a single-user local/CI application using ephemeral Runtime stores. It is
not a hosted multitenant API. Interrupted read-only jobs restart from fresh evidence;
there are no pending external writes to recover. Retain reports as CI artifacts
according to your organization's retention policy. Do not expose the CLI as an
unauthenticated web service.

## Import into Algen Studio

Choose this folder (the one containing `config/agent.yaml`) in **Import a project**.
Studio imports the `release-explainer` agent and the `release-readiness` workflow and
classifies the project as custom code, because the workflow runs Python hooks.

- `pyproject.toml` declares `[tool.algen-studio.import] runtime-contract =
  "workflow_hook_provider_v1"`. Managed builds install `requirements.lock` (hash-pinned,
  `algen-agent-runtime==0.1.0a7`, the version Studio runs) and put `src/` on
  `PYTHONPATH`. If Studio moves to a newer Runtime, regenerate the lock with the
  command at its top and the new version.
- Studio loads hooks only from authorized modules. Either set
  `ALGEN_AGENT_STUDIO_WORKFLOW_HOOK_ALLOWED_MODULES=algen_release_guard` on the Studio
  host, or approve the hook provider for the project revision in Studio. For local
  in-process runs, also install this package into Studio's Python environment
  (`pip install -e /path/to/algen-release-guard`).
- Set these project environment values in Studio (it asks for each `env://` reference):

  | Name | Value |
  |---|---|
  | `OPENAI_API_KEY` | OpenAI key for the explanation |
  | `GITHUB_TOKEN` | Read-only token, as described above |
  | `RELEASE_GUARD_REPOSITORIES` | Comma-separated `owner/repo` allowlist |
  | `RELEASE_GUARD_POLICY` | The policy JSON itself (for example the contents of `policy.json`) |

- Run the workflow with structured inputs, for example
  `{"repository": "owner/repo", "pull_request": 123}`. Add `"evidence_only": true` to
  skip the model. The policy comes only from the operator's environment, never from
  run inputs. The workflow output is the report, including a `markdown` rendering.

Studio's import discovery, validation (`valid`, `executable`, no issues), dependency
contract (`candidate_valid`), and Studio's hook loader with live GitHub and OpenAI
calls were checked locally against Studio's Runtime 0.1.0a7. Hosted Studio execution
is not certified.

## Test and package

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m build
.venv/bin/python scripts/package.py
```

The marketplace archive contains explicitly allowed source, tests, docs, and
configuration files. It excludes `.env`, reports, virtual environments, Git data,
and caches. Review `dist/package-info.json` for SHA-256 and byte size. The publication
plan explains the remaining identity, public source, artifact URL, and AgentStripes
requirements. Nothing in these commands uploads or publishes the agent.

`scripts/prepare_listing.py --help` lists the real publisher/source/artifact details
needed to create a schema-validated manifest. It deliberately creates no placeholder
listing by default. Review the target marketplace category before submission.
Local reports have no automatic expiry and remain until you delete them; configure
CI artifact retention yourself. `requirements.lock` is a hash-pinned resolution made
on macOS with Python 3.12; CI installs it on Linux for Python 3.12 and 3.13.
