"""Testes do PR4: multi-tenant (org + papéis) e dashboards."""

from __future__ import annotations

import pytest

from backend.app.models import OrgMembership, Organization, Project, User
from backend.app.security import encrypt_pat
from backend.app.services import dashboards as dash
from backend.app.services.orgs import membership, user_orgs

ISSUES = [
    {"state": "OPEN", "author": "alice", "assignees": ["bob"],
     "milestone": "M1 - Exploração", "labels": ["fase:i"], "url": "u1"},
    {"state": "CLOSED", "author": "bob", "assignees": [],
     "milestone": "M2 - Viabilidade", "labels": [], "url": "u2"},
    {"state": "OPEN", "author": "carol", "assignees": ["alice"],
     "milestone": None, "labels": ["fase:iii"], "url": "u3"},
]


# --- services/dashboards ---

def test_phase_of():
    assert dash.phase_of({"milestone": "M1 - Exploração", "labels": []}) == "M1"
    assert dash.phase_of({"milestone": None, "labels": ["fase:ii"]}) == "fase:ii"
    assert dash.phase_of({"milestone": None, "labels": []}) == "sem fase"
    assert dash.phase_of({"milestone": "Backlog", "labels": []}) == "Backlog"


def test_aggregate():
    issues = [{**i, "phase": dash.phase_of(i)} for i in ISSUES]
    agg = dash.aggregate(issues)
    assert agg["total"] == 3
    assert agg["by_state"] == {"OPEN": 2, "CLOSED": 1}
    assert agg["by_phase"]["M1"] == {"open": 1, "closed": 0}
    # atribuição por assignee, com fallback para autor quando não há assignee:
    # u1->bob (assignee), u2->bob (autor, sem assignee), u3->alice (assignee).
    assert set(agg["by_dev"]) == {"bob", "alice"}
    assert agg["by_dev"]["bob"] == {"open": 1, "closed": 1}


def test_filter_mine():
    mine = dash.filter_mine(ISSUES, "alice")
    assert {i["url"] for i in mine} == {"u1", "u3"}  # autora de u1, assignee de u3


# --- multi-tenant fixtures ---

@pytest.fixture
def org(db):
    o = Organization(github_org_id=42, login="acme", name="ACME")
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


@pytest.fixture
def member(db, user, org):
    user.pat_encrypted = encrypt_pat("ghp_x")
    m = OrgMembership(user_id=user.id, org_id=org.id, role="member")
    db.add(m)
    db.commit()
    return m


@pytest.fixture
def admin(db, user, org):
    user.pat_encrypted = encrypt_pat("ghp_x")
    m = OrgMembership(user_id=user.id, org_id=org.id, role="admin")
    db.add(m)
    db.commit()
    return m


# --- services/orgs ---

def test_user_orgs_and_membership(db, user, org, member):
    orgs = user_orgs(db, user)
    assert orgs == [
        {
            "login": "acme",
            "name": "ACME",
            "avatar_url": None,
            "role": "member",
            "is_coordinator": False,
        }
    ]
    assert membership(db, user, "acme").role == "member"
    assert membership(db, user, "outra") is None


# --- routers ---

def test_list_orgs(auth_client, member):
    body = auth_client.get("/api/orgs").json()
    assert body[0]["login"] == "acme" and body[0]["role"] == "member"


def test_dashboard_requires_membership(auth_client, org):
    # sem OrgMembership
    r = auth_client.get("/api/dashboards/my-issues?org=acme")
    assert r.status_code == 403


def test_my_issues_for_member(monkeypatch, auth_client, db, user, org, member):
    db.add(Project(created_by_user_id=user.id, owner="acme", repo="r1", title="P"))
    db.commit()
    monkeypatch.setattr(
        "backend.app.routers.dashboards.collect_issues",
        lambda tok, repos: (
            [{**i, "phase": dash.phase_of(i)} for i in ISSUES],
            [],
        ),
    )
    body = auth_client.get("/api/dashboards/my-issues?org=acme").json()
    # user.login == "octocat" (fixture) -> não é autor/assignee de nenhuma
    assert body["agg"]["total"] == 0
    assert body["repos"] == 1


def test_devs_requires_coordinator(monkeypatch, auth_client, member):
    r = auth_client.get("/api/dashboards/devs?org=acme")
    assert r.status_code == 403


def test_devs_for_coordinator(monkeypatch, auth_client, admin):
    monkeypatch.setattr(
        "backend.app.routers.dashboards.collect_issues",
        lambda tok, repos: (
            [{**i, "phase": dash.phase_of(i)} for i in ISSUES],
            [],
        ),
    )
    body = auth_client.get("/api/dashboards/devs?org=acme").json()
    devs = {d["dev"]: d for d in body["devs"]}
    assert devs["bob"]["open"] == 1  # assignee de u1
    assert devs["alice"]["open"] == 1  # assignee de u3


def test_project_issues_endpoint(monkeypatch, auth_client, db, user):
    user.pat_encrypted = encrypt_pat("ghp_x")
    p = Project(created_by_user_id=user.id, owner="acme", repo="r1", title="P")
    db.add(p)
    db.commit()
    db.refresh(p)
    monkeypatch.setattr(
        "backend.app.routers.projects.collect_issues",
        lambda tok, repos: (
            [{**i, "phase": dash.phase_of(i), "repo": "acme/r1"} for i in ISSUES],
            [],
        ),
    )
    body = auth_client.get(f"/api/projects/{p.id}/issues").json()
    assert body["repos"] == 1
    assert len(body["issues"]) == 3


def test_project_issues_other_user_404(auth_client, db, user):
    user.pat_encrypted = encrypt_pat("ghp_x")
    other = User(github_id=77, login="x")
    db.add(other)
    db.flush()
    p = Project(created_by_user_id=other.id, owner="o", repo="r", title="P")
    db.add(p)
    db.commit()
    assert auth_client.get(f"/api/projects/{p.id}/issues").status_code == 404
