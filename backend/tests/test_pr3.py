"""Testes do PR3: criação por fase + idempotência + paginação."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.models import PhaseRun, Project
from backend.app.security import encrypt_pat
from backend.app.services import roadmap as svc
from scripts import roadmap_builder as rb

CFG = {
    "schedule": {"milestone_durations": {"M1": {"value": 5, "unit": "days"},
                                         "M2": {"value": 1, "unit": "months"}}},
    "labels": [{"name": "fase:i", "color": "1D76DB", "description": "x"}],
    "milestones": [
        {"key": "M1", "title": "M1 - Exploração", "description": "d1"},
        {"key": "M2", "title": "M2 - Viabilidade", "description": "d2"},
    ],
    "issues": [
        {"title": "M1-a", "milestone": "M1", "labels": ["fase:i"]},
        {"title": "M1-b", "milestone": "M1", "labels": ["fase:i"]},
        {"title": "M2-a", "milestone": "M2", "labels": ["fase:i"]},
    ],
}


# --- roadmap_builder ---

def test_select_issues_filters_by_phase():
    assert [i["title"] for i in rb.select_issues(CFG, ["M1"])] == ["M1-a", "M1-b"]
    assert [i["title"] for i in rb.select_issues(CFG, None)] == ["M1-a", "M1-b", "M2-a"]


def test_paginate_get_walks_pages(monkeypatch):
    pages = {1: [{"n": i} for i in range(100)], 2: [{"n": i} for i in range(30)]}
    monkeypatch.setattr(
        rb, "request_json", lambda m, url, tok: pages[int(url.rsplit("page=", 1)[1])]
    )
    assert len(rb.paginate_get("http://x?per_page=100", "t")) == 130


def test_ensure_issues_dryrun_phase_only():
    res = rb.ensure_issues("o", "r", "t", CFG, {}, False, {}, ["M2"])
    assert [(x["title"], x["outcome"]) for x in res] == [("M2-a", "would_create")]


# --- apply_phase ---

def _stub_github(monkeypatch, *, existing):
    monkeypatch.setattr(svc, "validate_config", lambda cfg: [])
    monkeypatch.setattr(svc, "validate_remote_access", lambda args, tok: [])
    monkeypatch.setattr(svc, "_existing_issue_titles", lambda tok, o, r: set(existing))
    monkeypatch.setattr(svc, "ensure_milestones", lambda *a, **k: {"M1": 1, "M2": 2})
    monkeypatch.setattr(svc, "ensure_labels", lambda *a, **k: None)

    def fake_ensure_issues(o, r, tok, cfg, ms, apply, sched, phases=None):
        return [
            {"title": i["title"], "milestone": i["milestone"], "outcome": "created"}
            for i in rb.select_issues(cfg, phases)
            if i["title"] not in existing
        ] + [
            {"title": i["title"], "milestone": i["milestone"], "outcome": "updated"}
            for i in rb.select_issues(cfg, phases)
            if i["title"] in existing
        ]

    monkeypatch.setattr(svc, "ensure_issues", fake_ensure_issues)


def test_apply_phase_creates_missing(monkeypatch):
    _stub_github(monkeypatch, existing=[])
    out = svc.apply_phase(token="t", owner="o", repo="r", cfg=CFG, phase_key="M1")
    assert out["status"] == "applied"
    assert out["created"] == 2 and out["updated"] == 0


def test_apply_phase_already_done_skip(monkeypatch):
    _stub_github(monkeypatch, existing=["M1-a", "M1-b"])
    out = svc.apply_phase(token="t", owner="o", repo="r", cfg=CFG, phase_key="M1")
    assert out["status"] == "already_done"
    assert out["skipped"] == 2 and out["created"] == 0


def test_apply_phase_already_done_error(monkeypatch):
    _stub_github(monkeypatch, existing=["M1-a", "M1-b"])
    with pytest.raises(HTTPException) as ei:
        svc.apply_phase(
            token="t", owner="o", repo="r", cfg=CFG, phase_key="M1",
            on_duplicate="error",
        )
    assert ei.value.status_code == 409


def test_apply_phase_partial_creates_only_missing(monkeypatch):
    _stub_github(monkeypatch, existing=["M1-a"])
    out = svc.apply_phase(token="t", owner="o", repo="r", cfg=CFG, phase_key="M1")
    assert out["status"] == "applied"
    assert out["created"] == 1 and out["updated"] == 1


def test_phase_status(monkeypatch):
    monkeypatch.setattr(svc, "_existing_issue_titles", lambda *a: {"M1-a"})
    st = {s["phase"]: s["status"] for s in svc.phase_status("t", "o", "r", CFG)}
    assert st == {"M1": "partial", "M2": "not_created"}


# --- router ---

@pytest.fixture
def project(db, user):
    user.pat_encrypted = encrypt_pat("ghp_x")
    p = Project(created_by_user_id=user.id, owner="o", repo="r", title="P",
                config_json="{}")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_apply_phase_endpoint_records_run(monkeypatch, auth_client, db, project):
    monkeypatch.setattr(
        "backend.app.routers.projects.apply_phase",
        lambda **k: {"status": "applied", "phase": "M1", "created": 3,
                     "updated": 0, "skipped": 0, "issues": []},
    )
    r = auth_client.post(f"/api/projects/{project.id}/phases/M1/apply", json={})
    assert r.status_code == 200
    assert r.json()["created"] == 3
    runs = db.query(PhaseRun).filter_by(project_id=project.id).all()
    assert len(runs) == 1 and runs[0].phase_key == "M1"


def test_apply_phase_endpoint_no_run_when_already_done(monkeypatch, auth_client, db, project):
    monkeypatch.setattr(
        "backend.app.routers.projects.apply_phase",
        lambda **k: {"status": "already_done", "phase": "M1", "created": 0,
                     "updated": 0, "skipped": 2, "issues": []},
    )
    auth_client.post(f"/api/projects/{project.id}/phases/M1/apply", json={})
    assert db.query(PhaseRun).count() == 0
