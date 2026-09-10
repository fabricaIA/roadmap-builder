"""Testes do PR1: auth, perfil (PAT cifrado), guarda do build-roadmap."""

from __future__ import annotations

import pytest

from backend.app import github
from backend.app.security import decrypt_pat, encrypt_pat


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_me_anonymous(client):
    assert client.get("/api/auth/me").json() == {"authenticated": False}


def test_profile_requires_auth(client):
    assert client.get("/api/profile").status_code == 401


def test_build_roadmap_requires_auth(client):
    r = client.post("/api/build-roadmap", json={"owner": "x", "repo": "y", "config": {}})
    assert r.status_code == 401


def test_pat_roundtrip():
    enc = encrypt_pat("ghp_secret_value")
    assert enc != "ghp_secret_value"
    assert decrypt_pat(enc) == "ghp_secret_value"


def test_humanize_error_scopes():
    msg = github.humanize_error("GraphQL erro: [{'type': 'INSUFFICIENT_SCOPES'}]")
    assert "escopo" in msg.lower()
    assert github.humanize_error("HTTP 401: Bad credentials").startswith("Token do GitHub")


def test_profile_get_default(auth_client):
    assert auth_client.get("/api/profile").json() == {"config": {}, "has_pat": False}


def test_profile_set_pat(monkeypatch, auth_client, db, user):
    monkeypatch.setattr(
        "backend.app.routers.profile.token_identity",
        lambda tok: github.TokenIdentity(login="octocat", scopes=["repo", "project"]),
    )
    r = auth_client.put("/api/profile", json={"pat": "ghp_abc123"})
    body = r.json()
    assert body["has_pat"] is True
    assert body["pat_login"] == "octocat"
    assert body["pat_scopes"] == ["repo", "project"]

    db.refresh(user)
    assert user.pat_encrypted is not None
    assert decrypt_pat(user.pat_encrypted) == "ghp_abc123"


def test_profile_set_config_filters_keys(auth_client):
    r = auth_client.put(
        "/api/profile",
        json={"config": {"project_title_pattern": "{repo} - RM", "malicioso": "x"}},
    )
    cfg = r.json()["config"]
    assert cfg == {"project_title_pattern": "{repo} - RM"}


def test_profile_invalid_pat_rejected(monkeypatch, auth_client):
    def _boom(_tok):
        raise ValueError("Token do GitHub inválido ou expirado.")

    monkeypatch.setattr("backend.app.routers.profile.token_identity", _boom)
    r = auth_client.put("/api/profile", json={"pat": "bad"})
    assert r.status_code == 400
    assert "inválido" in r.json()["detail"]


def test_build_roadmap_without_pat_returns_400(auth_client):
    r = auth_client.post(
        "/api/build-roadmap",
        json={"owner": "octocat", "repo": "hello", "apply": False, "config": {}},
    )
    assert r.status_code == 400
    assert "PAT" in r.json()["detail"]


def test_build_roadmap_dry_run_with_pat(monkeypatch, auth_client, db, user):
    from backend.app.security import encrypt_pat as _enc

    user.pat_encrypted = _enc("ghp_dry")
    db.commit()

    captured = {}

    def fake_build(**kwargs):
        captured.update(kwargs)
        return {"status": "success", "message": "ok", "issues_created": ["T1"]}

    monkeypatch.setattr("backend.app.routers.roadmap.build_roadmap", fake_build)
    r = auth_client.post(
        "/api/build-roadmap",
        json={
            "owner": "octocat",
            "repo": "hello",
            "apply": False,
            "config": {"issues": []},
        },
    )
    assert r.status_code == 200
    assert r.json()["issues_created"] == ["T1"]
    assert captured["token"] == "ghp_dry"  # veio do PAT do perfil, decifrado
    assert captured["owner"] == "octocat"
