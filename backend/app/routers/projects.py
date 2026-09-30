"""Registro de projetos de roadmap + criação/importação + resumo live."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.deps import require_user
from backend.app.github import humanize_error
from backend.app.models import PhaseRun, Project, ProjectVersion, User
from backend.app.routers.roadmap import RoadmapPayload
from backend.app.security import decrypt_pat
from backend.app.services.dashboards import collect_issues
from backend.app.services.github_read import project_v2_meta, repo_summary
from backend.app.services.roadmap import (
    apply_phase,
    build_roadmap,
    load_backlog_template,
    phase_status,
)

from backend.app.services.project_versions import (
    ensure_initial_version, project_config, save_version, snapshot_for,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


class ImportPayload(BaseModel):
    owner: str
    repo: str
    project_number: int | None = None


class PhaseApplyPayload(BaseModel):
    on_duplicate: str = "skip"  # "skip" | "error"
    apply: bool = True
    project_start_date: str | None = None

    @field_validator("project_start_date")
    @classmethod
    def valid_date(cls, value):
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Use uma data válida AAAA-MM-DD.")
        return value


def _pat(user: User) -> str:
    if user.pat_encrypted is None:
        raise HTTPException(
            status_code=400,
            detail="Configure seu PAT do GitHub no perfil antes de gerenciar projetos.",
        )
    try:
        return decrypt_pat(user.pat_encrypted)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _project_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "owner": p.owner,
        "repo": p.repo,
        "title": p.title,
        "project_number": p.project_number,
        "project_url": p.project_url,
        "source": p.source,
        "current_version": p.current_version,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _upsert_project(
    db: Session,
    user: User,
    *,
    owner: str,
    repo: str,
    title: str,
    source: str,
    project_number: int | None = None,
    project_url: str | None = None,
    config: dict | None = None,
    phase_keys: list[str] | None = None,
    base_version: int | None = None,
    change_note: str = "Configuração inicial",
) -> Project:
    p = db.scalar(select(Project).where(
        Project.created_by_user_id == user.id, Project.owner == owner, Project.repo == repo,
    ))
    if p is None:
        p = Project(created_by_user_id=user.id, owner=owner, repo=repo, source=source,
                    title=title, org_login=owner)
        db.add(p)
        db.flush()
        snapshot = snapshot_for(p, config if config is not None else load_backlog_template(), phase_keys)
    else:
        current = ensure_initial_version(db, user, p)
        snapshot = json.loads(current.snapshot_json)
        if config is not None:
            snapshot["config"] = config
            snapshot["phase_keys"] = phase_keys
    if title:
        snapshot["title"] = title
    if project_number is not None:
        if snapshot["project_number"] != project_number:
            snapshot["project_url"] = None
        snapshot["project_number"] = project_number
    if project_url is not None:
        snapshot["project_url"] = project_url
    save_version(
        db, user, p, base_version=p.current_version if base_version is None else base_version,
        snapshot=snapshot, change_note=change_note,
    )
    db.commit()
    db.refresh(p)
    return p


def _project_or_404(db: Session, user: User, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if p is None or p.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return p


def _project_cfg(p: Project) -> dict:
    return project_config(p)


@router.get("")
def list_projects(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(Project)
            .where(Project.created_by_user_id == user.id)
            .order_by(Project.created_at.desc())
        )
        .scalars()
        .all()
    )
    token = _pat(user) if rows else None
    out = []
    for p in rows:
        item = _project_dict(p)
        try:
            item["summary"] = repo_summary(token, p.owner, p.repo)
        except Exception as exc:  # noqa: BLE001 — best-effort por projeto
            item["summary"] = None
            item["summary_error"] = humanize_error(str(exc))
        out.append(item)
    return out


@router.get("/{project_id}")
def get_project(
    project_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    p = db.get(Project, project_id)
    if p is None or p.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    item = _project_dict(p)
    try:
        item["summary"] = repo_summary(_pat(user), p.owner, p.repo)
    except Exception as exc:  # noqa: BLE001
        item["summary"] = None
        item["summary_error"] = humanize_error(str(exc))
    return item


@router.post("")
def create_project_endpoint(
    payload: RoadmapPayload,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Project).where(
        Project.created_by_user_id == user.id,
        Project.owner == payload.owner, Project.repo == payload.repo,
    ))
    expected_version = 0
    if existing is not None:
        expected_version = ensure_initial_version(db, user, existing).version
    if payload.base_version is not None and payload.base_version != expected_version:
        raise HTTPException(409, "O projeto foi alterado. Recarregue antes de salvar.")
    config = deepcopy(payload.config)
    if payload.project_start_date and isinstance(config.get("schedule"), dict):
        config["schedule"]["project_start_date"] = payload.project_start_date
    token = _pat(user)
    result = build_roadmap(
        token=token,
        owner=payload.owner,
        repo=payload.repo,
        apply=payload.apply,
        create_project_flag=payload.create_project,
        project_title=payload.project_title,
        project_number=payload.project_number,
        project_start_date=payload.project_start_date,
        cfg=config,
        phase_keys=payload.phase_keys or None,
    )

    number = payload.project_number
    url = None
    node_id = result.get("project_node_id")
    if node_id:
        try:
            meta = project_v2_meta(token, node_id)
            number = meta.get("number") or number
            url = meta.get("url")
        except Exception:  # noqa: BLE001
            logger.warning("Não foi possível resolver metadados do ProjectV2.")

    project = _upsert_project(
        db,
        user,
        owner=payload.owner,
        repo=payload.repo,
        title=payload.project_title,
        source="created",
        project_number=number,
        project_url=url,
        config=config,
        phase_keys=payload.phase_keys or None,
        base_version=expected_version,
        change_note=payload.change_note,
    )
    return {**result, "project": _project_dict(project)}


@router.get("/{project_id}/issues")
def get_project_issues(
    project_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Issues live do repositório do projeto, no mesmo formato dos dashboards
    (para o Board por projeto)."""
    p = _project_or_404(db, user, project_id)
    issues, errors, status_order = collect_issues(
        _pat(user),
        [{"owner": p.owner, "repo": p.repo, "project_number": p.project_number}],
    )
    return {
        "issues": issues,
        "errors": errors,
        "repos": 1,
        "status_order": status_order,
    }


@router.get("/{project_id}/phases")
def get_phases(
    project_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    p = _project_or_404(db, user, project_id)
    runs = (
        db.execute(
            select(PhaseRun)
            .where(PhaseRun.project_id == p.id)
            .order_by(PhaseRun.applied_at.desc())
        )
        .scalars()
        .all()
    )
    history = [
        {
            "phase": r.phase_key,
            "project_version_id": r.project_version_id,
            "created": r.created_count,
            "updated": r.updated_count,
            "skipped": r.skipped_count,
            "applied_at": r.applied_at.isoformat() if r.applied_at else None,
        }
        for r in runs
    ]
    try:
        phases = phase_status(_pat(user), p.owner, p.repo, _project_cfg(p))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=humanize_error(str(exc)))
    return {"phases": phases, "history": history}


@router.post("/{project_id}/phases/{phase_key}/apply")
def apply_project_phase(
    project_id: int,
    phase_key: str,
    body: PhaseApplyPayload,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    p = _project_or_404(db, user, project_id)
    token = _pat(user)
    version = ensure_initial_version(db, user, p)
    snapshot = json.loads(version.snapshot_json)
    if body.project_start_date and body.project_start_date != snapshot["config"].get("schedule", {}).get("project_start_date"):
        snapshot["config"].setdefault("schedule", {})["project_start_date"] = body.project_start_date
        if body.apply:
            version = save_version(
                db, user, p, base_version=version.version, snapshot=snapshot,
                change_note=f"Data de início alterada ao aplicar a fase {phase_key}",
            )
            db.commit()
    result = apply_phase(
        token=token,
        owner=p.owner,
        repo=p.repo,
        cfg=snapshot["config"],
        phase_key=phase_key,
        on_duplicate=body.on_duplicate,
        apply=body.apply,
        project_number=snapshot["project_number"],
        project_start_date=body.project_start_date,
    )
    if result.get("status") == "applied":
        db.add(
            PhaseRun(
                project_id=p.id,
                user_id=user.id,
                phase_key=phase_key,
                project_version_id=version.id,
                created_count=result.get("created", 0),
                updated_count=result.get("updated", 0),
                skipped_count=result.get("skipped", 0),
            )
        )
        db.commit()
    return result


@router.post("/import")
def import_project(
    payload: ImportPayload,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    token = _pat(user)
    try:
        summary = repo_summary(token, payload.owner, payload.repo, use_cache=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=humanize_error(str(exc)))

    url = None
    if payload.project_number:
        try:
            from scripts.roadmap_builder import get_project_id

            node = get_project_id(payload.owner, token, payload.project_number)
            url = project_v2_meta(token, node).get("url")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=humanize_error(str(exc)))

    project = _upsert_project(
        db,
        user,
        owner=payload.owner,
        repo=payload.repo,
        title=f"{payload.owner}/{payload.repo}",
        source="imported",
        project_number=payload.project_number,
        project_url=url,
    )
    item = _project_dict(project)
    item["summary"] = summary
    return item


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    p = db.get(Project, project_id)
    if p is None or p.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    # Remover o registro local também remove seu histórico dependente.
    db.execute(delete(PhaseRun).where(PhaseRun.project_id == p.id))
    db.execute(delete(ProjectVersion).where(ProjectVersion.project_id == p.id))
    db.delete(p)
    db.commit()
    return {"ok": True}
