"""Registro de projetos de roadmap + criação/importação + resumo live."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.deps import require_user
from backend.app.github import humanize_error
from backend.app.models import Project, User
from backend.app.routers.roadmap import RoadmapPayload
from backend.app.security import decrypt_pat
from backend.app.services.github_read import project_v2_meta, repo_summary
from backend.app.services.roadmap import build_roadmap

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


class ImportPayload(BaseModel):
    owner: str
    repo: str
    project_number: int | None = None


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
) -> Project:
    p = db.execute(
        select(Project).where(
            Project.created_by_user_id == user.id,
            Project.owner == owner,
            Project.repo == repo,
        )
    ).scalar_one_or_none()
    if p is None:
        p = Project(created_by_user_id=user.id, owner=owner, repo=repo, source=source)
        db.add(p)
    if title:
        p.title = title
    if project_number is not None:
        p.project_number = project_number
    if project_url is not None:
        p.project_url = project_url
    db.commit()
    db.refresh(p)
    return p


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
        cfg=payload.config,
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
    )
    return {**result, "project": _project_dict(project)}


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
    db.delete(p)
    db.commit()
    return {"ok": True}
