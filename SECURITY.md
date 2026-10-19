# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| Earlier | No |

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub:
[Report a vulnerability](https://github.com/saurav-samantray/algen-release-guard/security/advisories/new)
(the **Security** tab of this repository, then **Report a vulnerability**).

Do not open a public issue, pull request or discussion for a suspected vulnerability. Include
the version or commit, how to reproduce the problem, and what an attacker gains. Never include
real credentials, tokens or private repository data in a report.

Replies and the fix are coordinated in the private advisory, and the advisory is published once
a fixed release is available.

## Scope

In scope:

- Bypassing the repository allowlist (`RELEASE_GUARD_REPOSITORIES`) or reading repositories,
  pull requests or data outside it.
- Leaking `GITHUB_TOKEN`, `OPENAI_API_KEY` or other environment values into reports, logs or
  model prompts.
- Pull request content (titles, bodies, check output, review comments) changing a verdict, the
  policy, or the explanation's evidence references, including prompt injection into the
  explanation step.
- Any write to GitHub or another external system; the agent is designed to be read-only.
- Report files written with broader permissions than owner-only.

Out of scope: findings that need an already-compromised host or operator environment, and the
behaviour of GitHub, OpenAI, Algen Agent Runtime or Algen Studio themselves (report those to
their maintainers).
