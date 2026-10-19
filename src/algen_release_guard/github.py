from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
from algen_agent_runtime.exceptions.errors import PolicyDeniedError, ToolExecutionError
from algen_agent_runtime.security.network import create_safe_http_client
from algen_agent_runtime.tools.contracts import (
    Idempotency,
    SideEffect,
    Tool,
    ToolContext,
    ToolDefinition,
)
from algen_agent_runtime.types.contracts import RetryPolicy

from .contracts import Check, Evidence, FileChange, Review, Target, timestamp


class GitHubError(Exception):
    """Safe diagnostic code; never contains response bodies or credentials."""


class GitHubReader:
    def __init__(self, token: str | None, *, transport: httpx.AsyncBaseTransport | None = None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = create_safe_http_client(
            allowed_hosts=("api.github.com",),
            timeout=10,
            follow_redirects=False,
            trust_env=False,
            headers=headers,
            transport=transport,
        )
        self.requests = 0

    async def aclose(self) -> None:
        await self.client.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, bool]:
        if not re.fullmatch(r"/repos/[A-Za-z0-9_.\-/]+", path) or ".." in path:
            raise GitHubError("invalid_api_path")
        for attempt in range(2):
            self.requests += 1
            if self.requests > 40:
                raise GitHubError("request_limit")
            try:
                async with self.client.stream(
                    "GET", "https://api.github.com" + path, params=params
                ) as response:
                    if response.status_code in {429, 403}:
                        raise GitHubError("rate_limited_or_forbidden")
                    if response.status_code >= 500 and attempt == 0:
                        await asyncio.sleep(0.25)
                        continue
                    if response.status_code != 200:
                        raise GitHubError(f"http_{response.status_code}")
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > 2_000_000:
                            raise GitHubError("response_too_large")
                    return json.loads(payload), 'rel="next"' in response.headers.get("link", "")
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 0:
                    await asyncio.sleep(0.25)
                    continue
                raise GitHubError("network_unavailable") from None
            except (ValueError, UnicodeError):
                raise GitHubError("invalid_json") from None
        raise GitHubError("unavailable")

    async def pages(self, path: str, key: str | None = None, **params: Any) -> list[dict[str, Any]]:
        rows = []
        for page in range(1, 11):
            payload, more = await self.get(path, {**params, "per_page": 100, "page": page})
            batch = payload.get(key) if key and isinstance(payload, dict) else payload
            if not isinstance(batch, list) or any(not isinstance(x, dict) for x in batch):
                raise GitHubError("invalid_collection")
            rows.extend(batch)
            if not more:
                if (
                    key
                    and isinstance(payload, dict)
                    and payload.get("total_count", len(rows)) > len(rows)
                ):
                    raise GitHubError("incomplete_collection")
                return rows
        raise GitHubError("pagination_limit")

    async def collect(self, target: Target) -> Evidence:
        root = f"/repos/{target.repository}"
        pr_path = f"{root}/pulls/{target.pull_request}"
        initial, _ = await self.get(pr_path)
        try:
            sha = initial["head"]["sha"]
            base = initial["base"]["sha"]
            if not all(re.fullmatch(r"[a-f0-9]{40,64}", s) for s in (sha, base)):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise GitHubError("invalid_pull_request") from None
        checks, reviews, files, errors = [], [], [], []
        web = f"https://github.com/{target.repository}/pull/{target.pull_request}"
        sources = {
            "pr": web,
            "checks": web + "/checks",
            "reviews": web + "#pullrequestreview",
            "files": web + "/files",
        }
        try:
            rows = await self.pages(
                f"{root}/commits/{sha}/check-runs", "check_runs", filter="latest"
            )
            checks.extend(
                Check(
                    id=r["id"],
                    name=r["name"],
                    kind="check",
                    app_id=r["app"]["id"],
                    state=r["status"],
                    conclusion=r["conclusion"],
                    sha=r["head_sha"],
                )
                for r in rows
            )
        except (GitHubError, KeyError, TypeError, ValueError):
            errors.append("check_runs_unavailable_or_invalid")
        try:
            rows = await self.pages(f"{root}/commits/{sha}/statuses")
            # GitHub returns statuses newest first; preserve only newest per context.
            seen = set()
            for r in rows:
                if r["context"] not in seen:
                    seen.add(r["context"])
                    checks.append(
                        Check(
                            id=r["id"],
                            name=r["context"],
                            kind="status",
                            app_id=None,
                            state="completed" if r["state"] != "pending" else "pending",
                            conclusion=r["state"],
                            sha=sha,
                        )
                    )
        except (GitHubError, KeyError, TypeError, ValueError):
            errors.append("commit_statuses_unavailable_or_invalid")
        try:
            rows = await self.pages(pr_path + "/reviews")
            reviews = [
                Review(
                    id=r["id"],
                    user=r["user"]["login"],
                    state=r["state"],
                    commit_id=r["commit_id"],
                    association=r["author_association"],
                )
                for r in rows
            ]
        except (GitHubError, KeyError, TypeError, ValueError):
            errors.append("reviews_unavailable_or_invalid")
        try:
            rows = await self.pages(pr_path + "/files")
            files = [FileChange(filename=r["filename"], changes=r["changes"]) for r in rows]
            if len(files) != initial["changed_files"]:
                errors.append("changed_file_count_mismatch")
        except (GitHubError, KeyError, TypeError, ValueError):
            errors.append("files_unavailable_or_invalid")
        final, _ = await self.get(pr_path)
        try:
            stable = all(
                initial[k] == final[k]
                for k in ("head", "base", "state", "draft", "merged", "updated_at", "changed_files")
            )
            return Evidence(
                target=target,
                collected_at=timestamp(),
                head_sha=sha,
                base_sha=base,
                pr_state=final["state"],
                draft=final["draft"],
                merged=final["merged"],
                mergeable=final["mergeable"],
                mergeable_state=final["mergeable_state"],
                author=initial["user"]["login"],
                stable=stable,
                checks=checks,
                reviews=reviews,
                files=files,
                errors=errors,
                sources=sources,
            )
        except (KeyError, TypeError, ValueError):
            raise GitHubError("invalid_pull_request") from None


def evidence_tool(reader: GitHubReader, allowed_repositories: frozenset[str]) -> Tool:
    async def handler(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        target = Target.model_validate(arguments)
        if target.repository.lower() not in {r.lower() for r in allowed_repositories}:
            raise PolicyDeniedError("repository is not in the operator allowlist")
        try:
            return (await reader.collect(target)).model_dump(mode="json")
        except GitHubError as exc:
            raise ToolExecutionError(str(exc)) from None

    return Tool(
        ToolDefinition(
            name="github.release_evidence",
            version="0.1.0",
            description="Read bounded PR evidence from an allowlisted GitHub repository",
            input_schema=Target.model_json_schema(),
            output_schema=Evidence.model_json_schema(),
            required_permissions=frozenset({"github:read"}),
            side_effect=SideEffect.READ,
            idempotency=Idempotency.IDEMPOTENT,
            timeout_seconds=90,
            retry_policy=RetryPolicy(max_attempts=1),
            max_concurrency=1,
            max_result_bytes=512000,
        ),
        handler,
    )
