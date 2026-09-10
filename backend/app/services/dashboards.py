"""Agregações live de issues para os dashboards (por dev / por fase / por org).

Consultas GraphQL ao GitHub com cache TTL curto (via github_read).
"""

from __future__ import annotations

import re
import time
from typing import Any

from backend.app.github import humanize_error
from scripts.roadmap_builder import graphql

_CACHE_TTL = 60.0
_MAX_PAGES = 3  # até 300 issues por repo
_cache: dict[str, tuple[float, Any]] = {}

_PHASE_RE = re.compile(r"^\s*(M\d+)\b", re.IGNORECASE)

_ISSUES_QUERY = """
query($owner: String!, $repo: String!, $after: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url state createdAt closedAt
        author { login }
        assignees(first: 5) { nodes { login } }
        milestone { title }
        labels(first: 20) { nodes { name } }
      }
    }
  }
}
"""


def phase_of(issue: dict) -> str:
    m = issue.get("milestone")
    if m:
        hit = _PHASE_RE.match(m)
        if hit:
            return hit.group(1).upper()
        return m
    for lbl in issue.get("labels", []):
        if lbl.lower().startswith("fase:"):
            return lbl
    return "sem fase"


def _repo_issues(token: str, owner: str, repo: str) -> list[dict]:
    key = f"{owner}/{repo}"
    hit = _cache.get(key)
    if hit and (time.monotonic() - hit[0]) < _CACHE_TTL:
        return hit[1]

    issues: list[dict] = []
    after = None
    for _ in range(_MAX_PAGES):
        data = graphql(token, _ISSUES_QUERY, {"owner": owner, "repo": repo, "after": after})
        repository = data.get("repository")
        if not repository:
            break
        conn = repository["issues"]
        for n in conn["nodes"]:
            issues.append(
                {
                    "repo": key,
                    "number": n["number"],
                    "title": n["title"],
                    "url": n["url"],
                    "state": n["state"],
                    "created_at": n["createdAt"],
                    "closed_at": n["closedAt"],
                    "author": (n.get("author") or {}).get("login"),
                    "assignees": [a["login"] for a in n["assignees"]["nodes"]],
                    "milestone": (n.get("milestone") or {}).get("title"),
                    "labels": [x["name"] for x in n["labels"]["nodes"]],
                }
            )
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]

    _cache[key] = (time.monotonic(), issues)
    return issues


def collect_issues(
    token: str, repos: list[tuple[str, str]]
) -> tuple[list[dict], list[str]]:
    seen: set[str] = set()
    out: list[dict] = []
    errors: list[str] = []
    for owner, repo in repos:
        try:
            for issue in _repo_issues(token, owner, repo):
                if issue["url"] in seen:
                    continue
                seen.add(issue["url"])
                issue = {**issue, "phase": phase_of(issue)}
                out.append(issue)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{owner}/{repo}: {humanize_error(str(exc))}")
    return out, errors


def filter_mine(issues: list[dict], login: str) -> list[dict]:
    return [
        i for i in issues if i["author"] == login or login in i["assignees"]
    ]


def aggregate(issues: list[dict]) -> dict:
    by_state = {"OPEN": 0, "CLOSED": 0}
    by_phase: dict[str, dict[str, int]] = {}
    by_dev: dict[str, dict[str, int]] = {}

    for i in issues:
        by_state[i["state"]] = by_state.get(i["state"], 0) + 1

        ph = by_phase.setdefault(i["phase"], {"open": 0, "closed": 0})
        ph["open" if i["state"] == "OPEN" else "closed"] += 1

        devs = set(i["assignees"]) or ({i["author"]} if i["author"] else set())
        for d in devs:
            row = by_dev.setdefault(d, {"open": 0, "closed": 0})
            row["open" if i["state"] == "OPEN" else "closed"] += 1

    return {
        "total": len(issues),
        "by_state": by_state,
        "by_phase": by_phase,
        "by_dev": by_dev,
    }
