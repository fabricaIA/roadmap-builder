"""Consultas de leitura ao GitHub (GraphQL) com cache TTL em memória.

Usa `scripts.roadmap_builder.graphql` (reaproveita o retry/backoff).
O cache é por processo — suficiente para dev; em produção com múltiplos
workers cada um terá o seu (aceitável para TTL curto).
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from scripts.roadmap_builder import graphql

_CACHE_TTL = 60.0
_cache: dict[str, tuple[float, Any]] = {}


def _key(token: str, *parts: str) -> str:
    h = hashlib.sha256(token.encode()).hexdigest()[:12]
    return ":".join([h, *parts])


def _cached(key: str):
    hit = _cache.get(key)
    if hit and (time.monotonic() - hit[0]) < _CACHE_TTL:
        return hit[1]
    return None


def _store(key: str, value: Any) -> Any:
    _cache[key] = (time.monotonic(), value)
    return value


_REPO_SUMMARY_QUERY = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    url
    openIssues: issues(states: [OPEN]) { totalCount }
    closedIssues: issues(states: [CLOSED]) { totalCount }
    milestones(first: 50, orderBy: {field: NUMBER, direction: ASC}) {
      nodes {
        title
        state
        dueOn
        open: issues(states: [OPEN]) { totalCount }
        closed: issues(states: [CLOSED]) { totalCount }
      }
    }
  }
}
"""


def repo_summary(token: str, owner: str, repo: str, *, use_cache: bool = True) -> dict:
    """Resumo live do repo: contagem de issues e progresso por milestone/fase."""
    key = _key(token, "repo_summary", owner, repo)
    if use_cache:
        cached = _cached(key)
        if cached is not None:
            return cached

    data = graphql(token, _REPO_SUMMARY_QUERY, {"owner": owner, "repo": repo})
    repository = data.get("repository")
    if repository is None:
        raise RuntimeError(f"Repositório {owner}/{repo} não encontrado ou sem acesso.")

    open_i = repository["openIssues"]["totalCount"]
    closed_i = repository["closedIssues"]["totalCount"]
    milestones = [
        {
            "title": m["title"],
            "state": m["state"],
            "due_on": m.get("dueOn"),
            "open": m["open"]["totalCount"],
            "closed": m["closed"]["totalCount"],
            "total": m["open"]["totalCount"] + m["closed"]["totalCount"],
        }
        for m in repository["milestones"]["nodes"]
    ]
    result = {
        "repo_url": repository["url"],
        "issues": {"open": open_i, "closed": closed_i, "total": open_i + closed_i},
        "milestones": milestones,
    }
    return _store(key, result)


_PROJECT_NODE_QUERY = """
query($id: ID!) {
  node(id: $id) {
    ... on ProjectV2 { number url title }
  }
}
"""


def project_v2_meta(token: str, node_id: str) -> dict:
    """Número/URL/título de um ProjectV2 a partir do node id."""
    data = graphql(token, _PROJECT_NODE_QUERY, {"id": node_id})
    node = data.get("node") or {}
    return {
        "number": node.get("number"),
        "url": node.get("url"),
        "title": node.get("title"),
    }
