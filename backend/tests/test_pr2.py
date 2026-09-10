"""Testes do PR2: registro de projetos, criação/importação, resumo live."""

from __future__ import annotations

import pytest

from backend.app.models import Project, User
from backend.app.security import encrypt_pat

_FAKE_SUMMARY = {
    "repo_url": "https://github.com/octocat/hello",
    "issues": {"open": 3, "closed": 4, "total": 7},
    "milestones": [
        {"title": "M1 - Exploração", "state": "OPEN", "due_on": None,
         "open": 3, "closed": 4, "total": 7},
    ],
}


@pytest.fixture
def user_with_pat(db, user):
    user.pat_encrypted = encrypt_pat("ghp_test")
    db.commit()
    db.refresh(user)
    return user


def test_list_projects_empty(auth_client):
    assert auth_client.get("/api/projects").json() == []


def test_list_projects_needs_pat_when_rows_exist(auth_client, db, user):
    db.add(Project(created_by_user_id=user.id, owner="o", repo="r", title="x"))
    db.commit()
    r = auth_client.get("/api/projects")
    assert r.status_code == 400
    assert "PAT" in r.json()["detail"]


def test_list_projects_enriches(monkeypatch, auth_client, db, user_with_pat):
    db.add(Project(created_by_user_id=user_with_pat.id, owner="octocat", repo="hello", title="H"))
    db.commit()
    monkeypatch.setattr(
        "backend.app.routers.projects.repo_summary", lambda *a, **k: _FAKE_SUMMARY
    )
    body = auth_client.get("/api/projects").json()
    assert len(body) == 1
    assert body[0]["repo"] == "hello"
    assert body[0]["summary"]["issues"]["total"] == 7


def test_list_projects_summary_error_is_soft(monkeypatch, auth_client, db, user_with_pat):
    db.add(Project(created_by_user_id=user_with_pat.id, owner="o", repo="r", title="x"))
    db.commit()

    def boom(*a, **k):
        raise RuntimeError("Repositório o/r não encontrado ou sem acesso.")

    monkeypatch.setattr("backend.app.routers.projects.repo_summary", boom)
    body = auth_client.get("/api/projects").json()
    assert body[0]["summary"] is None
    assert "não encontrado" in body[0]["summary_error"]


def test_create_project_registers_row(monkeypatch, auth_client, db, user_with_pat):
    monkeypatch.setattr(
        "backend.app.routers.projects.build_roadmap",
        lambda **k: {
            "status": "success",
            "message": "ok",
            "issues_created": ["a", "b"],
            "project_node_id": "PVT_node",
        },
    )
    monkeypatch.setattr(
        "backend.app.routers.projects.project_v2_meta",
        lambda tok, nid: {"number": 12, "url": "https://github.com/orgs/x/projects/12"},
    )
    r = auth_client.post(
        "/api/projects",
        json={
            "owner": "octocat",
            "repo": "hello",
            "apply": True,
            "create_project": True,
            "project_title": "octocat/hello - Roadmap",
            "config": {"issues": []},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["issues_created"] == ["a", "b"]
    assert body["project"]["project_number"] == 12
    rows = db.query(Project).filter_by(created_by_user_id=user_with_pat.id).all()
    assert len(rows) == 1
    assert rows[0].repo == "hello"


def test_create_project_is_idempotent_on_repo(monkeypatch, auth_client, db, user_with_pat):
    monkeypatch.setattr(
        "backend.app.routers.projects.build_roadmap",
        lambda **k: {"status": "success", "message": "ok", "issues_created": [], "project_node_id": None},
    )
    payload = {
        "owner": "octocat",
        "repo": "hello",
        "apply": False,
        "create_project": False,
        "project_title": "T",
        "config": {"issues": []},
    }
    auth_client.post("/api/projects", json=payload)
    auth_client.post("/api/projects", json={**payload, "project_title": "T2"})
    rows = db.query(Project).filter_by(created_by_user_id=user_with_pat.id).all()
    assert len(rows) == 1
    assert rows[0].title == "T2"  # atualizado, não duplicado


def test_import_project(monkeypatch, auth_client, db, user_with_pat):
    monkeypatch.setattr(
        "backend.app.routers.projects.repo_summary", lambda *a, **k: _FAKE_SUMMARY
    )
    r = auth_client.post(
        "/api/projects/import", json={"owner": "octocat", "repo": "legacy"}
    )
    assert r.status_code == 200
    assert r.json()["source"] == "imported"
    assert db.query(Project).filter_by(repo="legacy").count() == 1


def test_get_other_users_project_404(auth_client, db, user_with_pat):
    other = User(github_id=2, login="other")
    db.add(other)
    db.flush()
    p = Project(created_by_user_id=other.id, owner="o", repo="r", title="x")
    db.add(p)
    db.commit()
    assert auth_client.get(f"/api/projects/{p.id}").status_code == 404


def test_delete_project(auth_client, db, user_with_pat):
    p = Project(created_by_user_id=user_with_pat.id, owner="o", repo="r", title="x")
    db.add(p)
    db.commit()
    db.refresh(p)
    assert auth_client.delete(f"/api/projects/{p.id}").json() == {"ok": True}
    assert db.get(Project, p.id) is None
