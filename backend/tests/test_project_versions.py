"""Snapshots completos, autorização, conflitos e integração com rotas legadas."""

from copy import deepcopy
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import PhaseRun, Project, ProjectVersion, User
from backend.app.project_schemas import ProjectConfig
from backend.app.security import encrypt_pat
from backend.app.services.project_versions import save_version


@pytest.fixture
def config():
    return ProjectConfig.model_validate({
        "schedule": {"project_start_date": "2026-09-29", "milestone_durations": {
            "M1": {"value": 5, "unit": "days"}, "M2": {"value": 1, "unit": "months"},
        }},
        "milestones": [{"key": "M1", "title": "Exploração"}, {"key": "M2", "title": "MVP"}],
        "labels": [{"name": "fase:i", "color": "123456"}],
        "issues": [{"title": "Pesquisar", "milestone": "M1", "labels": ["fase:i"],
                    "description": "Descrição inicial", "entregaveis": ["Relatório"],
                    "criterios_aceite": ["Revisado"]}],
    }).model_dump()


@pytest.fixture
def project(db, user, config):
    project = Project(created_by_user_id=user.id, owner="octocat", repo="repo", title="Projeto",
                      config_json=json.dumps(config), project_number=7, project_url="https://github.com/users/octocat/projects/7")
    db.add(project)
    db.commit()
    return project


def initial(auth_client, project):
    response = auth_client.get(f"/api/projects/{project.id}/config")
    assert response.status_code == 200
    return response.json()


def save(auth_client, project, config, base=1, **extra):
    return auth_client.put(f"/api/projects/{project.id}/config", json={
        "base_version": base, "change_note": "Alteração revisada", "config": config, **extra,
    })


def test_initial_version_without_pat(auth_client, project, config, db):
    body = initial(auth_client, project)
    assert body["version"] == 1 and body["author_login"] == "octocat"
    assert body["snapshot"]["config"] == config
    assert body["snapshot"]["owner"] == "octocat"
    assert body["created_at"] and "pat" not in body["snapshot"]
    assert initial(auth_client, project) == body
    assert db.query(ProjectVersion).count() == 1


def test_every_configuration_field_is_preserved(auth_client, project, config, db):
    old = initial(auth_client, project)
    edited = deepcopy(config)
    edited["schedule"]["project_start_date"] = "2026-10-01"
    edited["schedule"]["milestone_durations"]["M1"]["value"] = 10
    edited["schedule"]["project_date_fields"]["start"] = "Começo"
    edited["milestones"][0]["description"] = "Novo objetivo"
    edited["milestones"][0]["title"] = "Nova fase"
    edited["labels"][0].update(color="abcdef", description="Nova etiqueta")
    edited["issues"][0].update(title="Novo título", description="Novo texto",
        entregaveis=["Documento", "Protótipo"], criterios_aceite=["Aprovado"], milestone="M2")
    edited["issues"].append({**edited["issues"][0], "title": "Outra issue", "labels": []})
    response = save(auth_client, project, edited, title="Novo projeto", project_number=8, phase_keys=["M2"])
    assert response.status_code == 201
    new = response.json()
    assert new["version"] == 2
    assert new["snapshot"] == {**old["snapshot"], "config": edited, "title": "Novo projeto",
                              "project_number": 8, "project_url": None, "phase_keys": ["M2"]}
    assert auth_client.get(f"/api/projects/{project.id}/versions/1").json() == old
    db.refresh(project)
    assert json.loads(project.config_json) == edited and project.current_version == 2
    assert initial(auth_client, project)["snapshot"] == new["snapshot"]


def test_every_explicit_save_creates_a_version_even_if_identical(auth_client, project, config, db):
    old = initial(auth_client, project)
    for base in range(1, 4):
        response = save(auth_client, project, config, base=base)
        assert response.status_code == 201
        assert response.json()["version"] == base + 1
        assert response.json()["snapshot"] == old["snapshot"]
    assert db.query(ProjectVersion).count() == 4
    assert auth_client.get(f"/api/projects/{project.id}/versions/1").json() == old


def test_restore_creates_new_snapshot_without_erasing_history(auth_client, project, config, db):
    old = initial(auth_client, project)
    changed = save(auth_client, project, config, title="Alterado", project_number=None).json()
    response = auth_client.post(f"/api/projects/{project.id}/versions/1/restore", json={
        "base_version": 2, "change_note": "Voltar ao conteúdo inicial",
    })
    assert response.status_code == 201
    restored = response.json()
    assert restored["version"] == 3 and restored["restored_from_version"] == 1
    assert restored["snapshot"] == old["snapshot"]
    assert auth_client.get(f"/api/projects/{project.id}/versions/2").json()["snapshot"] == changed["snapshot"]
    assert db.query(ProjectVersion).count() == 3
    db.refresh(project)
    assert project.title == "Projeto" and project.project_number == 7


def test_history_pagination_and_missing_version(auth_client, project, config):
    initial(auth_client, project)
    save(auth_client, project, config, title="v2")
    rows = auth_client.get(f"/api/projects/{project.id}/versions").json()
    assert [r["version"] for r in rows] == [2, 1]
    assert "snapshot" not in rows[0]
    rows = auth_client.get(f"/api/projects/{project.id}/versions?limit=1&offset=1").json()
    assert [r["version"] for r in rows] == [1]
    assert auth_client.get(f"/api/projects/{project.id}/versions/99").status_code == 404
    assert auth_client.get(f"/api/projects/{project.id}/versions?limit=1000").status_code == 422


def test_stale_save_and_restore_do_not_mutate_project(auth_client, project, config, db):
    initial(auth_client, project)
    save(auth_client, project, config, title="Vencedor")
    assert save(auth_client, project, config, title="Perdedor").status_code == 409
    response = auth_client.post(f"/api/projects/{project.id}/versions/1/restore", json={
        "base_version": 1, "change_note": "Antigo",
    })
    assert response.status_code == 409
    db.refresh(project)
    assert project.title == "Vencedor" and project.current_version == 2
    assert db.query(ProjectVersion).count() == 2


@pytest.mark.parametrize("method,path,body", [
    ("get", "config", None), ("get", "versions", None), ("get", "versions/1", None),
    ("put", "config", "save"), ("post", "versions/1/restore", "restore"),
])
def test_auth_and_project_ownership(client, db, user, project, config, method, path, body):
    from backend.app.deps import get_current_user
    from backend.app.main import app
    kwargs = {}
    if body == "save":
        kwargs["json"] = {"base_version": 1, "config": config, "change_note": "x"}
    if body == "restore":
        kwargs["json"] = {"base_version": 1, "change_note": "x"}
    url = f"/api/projects/{project.id}/{path}"
    assert getattr(client, method)(url, **kwargs).status_code == 401
    other = User(github_id=99, login="other")
    db.add(other)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: other
    assert getattr(client, method)(url, **kwargs).status_code == 404
    assert db.query(ProjectVersion).count() == 0


@pytest.mark.parametrize("invalid", [
    "milestone_type", "label_type", "unknown_label", "unknown_milestone", "duration_bool",
    "color", "date", "duplicate_issue", "empty_deliverables", "unknown_field",
])
def test_invalid_snapshot_is_rejected_without_history(auth_client, project, config, db, invalid):
    initial(auth_client, project)
    bad = deepcopy(config)
    if invalid == "milestone_type": bad["issues"][0]["milestone"] = []
    if invalid == "label_type": bad["issues"][0]["labels"] = [[]]
    if invalid == "unknown_label": bad["issues"][0]["labels"] = ["unknown"]
    if invalid == "unknown_milestone": bad["issues"][0]["milestone"] = "M9"
    if invalid == "duration_bool": bad["schedule"]["milestone_durations"]["M1"]["value"] = True
    if invalid == "color": bad["labels"][0]["color"] = "zzzzzz"
    if invalid == "date": bad["schedule"]["project_start_date"] = "2026-02-30"
    if invalid == "duplicate_issue": bad["issues"].append(deepcopy(bad["issues"][0]))
    if invalid == "empty_deliverables": bad["issues"][0]["entregaveis"] = []
    if invalid == "unknown_field": bad["secret"] = "must-not-be-stored"
    assert save(auth_client, project, bad).status_code == 422
    assert db.query(ProjectVersion).count() == 1
    db.refresh(project)
    assert json.loads(project.config_json) == config


def test_invalid_target_and_secret_are_rejected(auth_client, project, config):
    initial(auth_client, project)
    assert save(auth_client, project, config, owner="invalid/owner").status_code == 422
    assert save(auth_client, project, config, pat="secret").status_code == 422
    assert save(auth_client, project, config, phase_keys=["M9"]).status_code == 422


def test_empty_issue_list_is_preserved_not_replaced_by_default(auth_client, project, config, monkeypatch):
    from backend.app.services.project_versions import project_config
    initial(auth_client, project)
    config["issues"] = []
    assert save(auth_client, project, config).status_code == 201
    monkeypatch.setattr("backend.app.services.project_versions.load_backlog_template", lambda: pytest.fail("fallback"))
    assert project_config(project)["issues"] == []


def test_legacy_create_records_all_edits_and_actual_start_date(auth_client, user, db, config, monkeypatch):
    user.pat_encrypted = encrypt_pat("fake")
    db.commit()
    captured = []
    monkeypatch.setattr("backend.app.routers.projects.build_roadmap", lambda **kw: captured.append(kw) or {"status": "success"})
    payload = {"owner": "octocat", "repo": "new", "config": config, "apply": False,
               "project_start_date": "2026-10-02", "phase_keys": ["M1"], "project_title": "Teste"}
    first = auth_client.post("/api/projects", json=payload)
    assert first.status_code == 200
    pid = first.json()["project"]["id"]
    assert first.json()["project"]["current_version"] == 1
    assert captured[0]["cfg"]["schedule"]["project_start_date"] == "2026-10-02"
    second = auth_client.post("/api/projects", json={**payload, "project_title": "Alterado", "base_version": 1})
    assert second.json()["project"]["current_version"] == 2
    stale = auth_client.post("/api/projects", json={**payload, "base_version": 1})
    assert stale.status_code == 409 and len(captured) == 2
    version = auth_client.get(f"/api/projects/{pid}/versions/1").json()
    assert version["snapshot"]["config"]["schedule"]["project_start_date"] == "2026-10-02"
    assert version["snapshot"]["phase_keys"] == ["M1"]
    assert version["snapshot"]["title"] == "Teste"


def test_import_freezes_default_and_creates_initial_version(auth_client, user, db, config, monkeypatch):
    user.pat_encrypted = encrypt_pat("fake")
    db.commit()
    monkeypatch.setattr("backend.app.routers.projects.repo_summary", lambda *a, **kw: {})
    monkeypatch.setattr("backend.app.routers.projects.load_backlog_template", lambda: deepcopy(config))
    response = auth_client.post("/api/projects/import", json={"owner": "octocat", "repo": "imported"})
    assert response.status_code == 200
    project = db.get(Project, response.json()["id"])
    assert project.current_version == 1 and json.loads(project.config_json) == config
    config["issues"][0]["title"] = "Arquivo alterado"
    assert initial(auth_client, project)["snapshot"]["config"]["issues"][0]["title"] == "Pesquisar"


def test_phase_run_records_exact_configuration_version(auth_client, user, db, project, config, monkeypatch):
    initial(auth_client, project)
    saved = save(auth_client, project, config, title="v2").json()
    user.pat_encrypted = encrypt_pat("fake")
    db.commit()
    captured = {}
    monkeypatch.setattr("backend.app.routers.projects.apply_phase", lambda **kw: captured.update(kw) or {
        "status": "applied", "created": 1, "updated": 0, "skipped": 0,
    })
    response = auth_client.post(f"/api/projects/{project.id}/phases/M1/apply", json={})
    assert response.status_code == 200
    run = db.scalar(select(PhaseRun))
    assert run.project_version_id == saved["id"]
    assert captured["cfg"] == saved["snapshot"]["config"]
    assert save(auth_client, project, config, base=2, title="v3").status_code == 201
    db.refresh(run)
    assert run.project_version_id == saved["id"]


def test_delete_cleans_dependent_history(auth_client, user, db, project):
    version = initial(auth_client, project)
    db.add(PhaseRun(project_id=project.id, user_id=user.id, phase_key="M1", project_version_id=version["id"]))
    db.commit()
    assert auth_client.delete(f"/api/projects/{project.id}").status_code == 200
    assert db.query(ProjectVersion).count() == 0 and db.query(PhaseRun).count() == 0


def test_separate_sessions_reject_stale_snapshot(tmp_path, config):
    from sqlalchemy import create_engine
    from backend.app.db import Base
    from backend.app.services.project_versions import ensure_initial_version
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrency.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as first, Session(engine) as second:
        user = User(github_id=1, login="one")
        first.add(user)
        first.flush()
        project = Project(created_by_user_id=user.id, owner="one", repo="r", title="v1", config_json=json.dumps(config))
        first.add(project)
        first.commit()
        initial_version = ensure_initial_version(first, user, project)
        stale_project = second.get(Project, project.id)
        stale_user = second.get(User, user.id)
        snapshot = json.loads(initial_version.snapshot_json)
        save_version(first, user, project, base_version=1, snapshot={**snapshot, "title": "v2"}, change_note="a")
        first.commit()
        with pytest.raises(HTTPException) as error:
            save_version(second, stale_user, stale_project, base_version=1,
                         snapshot={**snapshot, "title": "perdedor"}, change_note="b")
        assert error.value.status_code == 409
        second.rollback()
    with Session(engine) as check:
        assert check.scalar(select(Project)).title == "v2"
        assert [v.version for v in check.scalars(select(ProjectVersion).order_by(ProjectVersion.version))] == [1, 2]
    engine.dispose()


def test_failed_snapshot_insert_rolls_back_project(db, user, project, auth_client):
    from sqlalchemy import event
    initial(auth_client, project)
    snapshot = initial(auth_client, project)["snapshot"]
    def fail(mapper, connection, target):
        raise RuntimeError("simulated storage failure")
    event.listen(ProjectVersion, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            save_version(db, user, project, base_version=1,
                         snapshot={**snapshot, "title": "não confirmar"}, change_note="test")
        db.rollback()
    finally:
        event.remove(ProjectVersion, "before_insert", fail)
    db.refresh(project)
    assert project.current_version == 1 and project.title == "Projeto"
    assert db.query(ProjectVersion).count() == 1


@pytest.mark.parametrize("apply", [True, False])
def test_phase_date_override_is_versioned_only_when_applied(auth_client, project, user, db, config, monkeypatch, apply):
    initial(auth_client, project)
    user.pat_encrypted = encrypt_pat("fake")
    db.commit()
    captured = {}
    monkeypatch.setattr("backend.app.routers.projects.apply_phase", lambda **kw: captured.update(kw) or {
        "status": "applied" if apply else "dry_run", "created": 1,
    })
    response = auth_client.post(f"/api/projects/{project.id}/phases/M1/apply", json={
        "apply": apply, "project_start_date": "2026-11-01",
    })
    assert response.status_code == 200
    assert captured["cfg"]["schedule"]["project_start_date"] == "2026-11-01"
    db.refresh(project)
    assert project.current_version == (2 if apply else 1)
    assert auth_client.get(f"/api/projects/{project.id}/versions/1").json()["snapshot"]["config"] == config
    if apply:
        run = db.scalar(select(PhaseRun))
        version = db.get(ProjectVersion, run.project_version_id)
        assert version.version == 2


def test_restore_recovers_deleted_stages_cards_fields_and_order(auth_client, project, config, db):
    original = deepcopy(config)
    original["issues"].extend([
        {**original["issues"][0], "title": "Segundo card", "milestone": "M2", "labels": []},
        {**original["issues"][0], "title": "Terceiro card", "entregaveis": ["Primeiro", "Segundo"]},
    ])
    original["labels"].append({"name": "tipo:card", "color": "abcdef", "description": "Tipo"})
    project.config_json = json.dumps(original)
    db.commit()
    v1 = initial(auth_client, project)
    reordered = deepcopy(original)
    reordered["milestones"].reverse()
    reordered["issues"].reverse()
    reordered["labels"].reverse()
    reordered["issues"][0]["entregaveis"].reverse()
    v2 = save(auth_client, project, reordered).json()
    assert v2["snapshot"]["config"] == reordered
    deleted = deepcopy(reordered)
    deleted["milestones"] = [m for m in deleted["milestones"] if m["key"] != "M2"]
    del deleted["schedule"]["milestone_durations"]["M2"]
    deleted["issues"] = [card for card in deleted["issues"] if card["milestone"] != "M2"]
    deleted["issues"][0]["entregaveis"] = ["Substituto"]
    deleted["labels"] = [label for label in deleted["labels"] if label["name"] != "tipo:card"]
    v3 = save(auth_client, project, deleted, base=2).json()
    assert v3["snapshot"]["config"] == deleted
    response = auth_client.post(f"/api/projects/{project.id}/versions/1/restore", json={
        "base_version": 3, "change_note": "Recuperar tudo, incluindo ordem e itens excluídos",
    })
    assert response.status_code == 201
    v4 = response.json()
    assert v4["version"] == 4 and v4["snapshot"] == v1["snapshot"]
    assert v4["restored_from_version"] == 1
    assert auth_client.get(f"/api/projects/{project.id}/versions/2").json()["snapshot"] == v2["snapshot"]
    assert auth_client.get(f"/api/projects/{project.id}/versions/3").json()["snapshot"] == v3["snapshot"]
    assert db.query(ProjectVersion).count() == 4


def test_restore_current_version_also_creates_new_version(auth_client, project, db):
    old = initial(auth_client, project)
    response = auth_client.post(f"/api/projects/{project.id}/versions/1/restore", json={
        "base_version": 1, "change_note": "Restaurar conteúdo atual",
    })
    assert response.status_code == 201
    assert response.json()["version"] == 2
    assert response.json()["snapshot"] == old["snapshot"]
    assert db.query(ProjectVersion).count() == 2


def test_delete_all_template_items_then_restore(auth_client, project, config):
    old = initial(auth_client, project)
    empty = deepcopy(config)
    empty["milestones"] = []
    empty["issues"] = []
    empty["labels"] = []
    empty["schedule"]["milestone_durations"] = {}
    response = save(auth_client, project, empty)
    assert response.status_code == 201
    assert initial(auth_client, project)["snapshot"]["config"] == empty
    restored = auth_client.post(f"/api/projects/{project.id}/versions/1/restore", json={
        "base_version": 2, "change_note": "Recuperar template completo",
    })
    assert restored.json()["snapshot"] == old["snapshot"]


def test_edit_and_restore_owner_preserves_history(auth_client, project, config, db):
    original = initial(auth_client, project)
    response = save(auth_client, project, config, owner="new-owner", repo="new-repo")
    assert response.status_code == 201
    updated = response.json()
    assert updated["snapshot"]["owner"] == "new-owner"
    assert updated["snapshot"]["repo"] == "new-repo"
    assert updated["snapshot"]["project_number"] is None
    assert updated["snapshot"]["project_url"] is None
    db.refresh(project)
    assert (project.owner, project.repo, project.org_login) == ("new-owner", "new-repo", "new-owner")
    assert auth_client.get(f"/api/projects/{project.id}/versions/1").json() == original
    response = auth_client.post(f"/api/projects/{project.id}/versions/1/restore", json={
        "base_version": 2, "change_note": "Restaurar destino original",
    })
    assert response.status_code == 201
    assert response.json()["snapshot"] == original["snapshot"]
    db.refresh(project)
    assert project.owner == project.org_login == "octocat"
    assert project.project_number == 7 and project.current_version == 3


def test_owner_change_and_restore_cannot_collide_with_another_project(auth_client, project, config, db, user):
    initial(auth_client, project)
    other = Project(created_by_user_id=user.id, owner="taken", repo="repo", title="Outro", config_json=json.dumps(config))
    db.add(other)
    db.commit()
    assert save(auth_client, project, config, owner="TAKEN").status_code == 409
    db.refresh(project)
    assert project.owner == "octocat" and project.current_version == 1
    assert save(auth_client, project, config, owner="free").status_code == 201
    other.owner = "octocat"
    db.commit()
    response = auth_client.post(f"/api/projects/{project.id}/versions/1/restore", json={
        "base_version": 2, "change_note": "Destino agora ocupado",
    })
    assert response.status_code == 409
    db.refresh(project)
    assert project.owner == "free" and project.current_version == 2
    assert db.query(ProjectVersion).filter_by(project_id=project.id).count() == 2
