"""Consultar, salvar e restaurar configurações sem escrever no GitHub."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.deps import require_user
from backend.app.models import ProjectVersion, User
from backend.app.project_schemas import ConfigUpdate, VersionRestore
from backend.app.services.project_versions import (
    ensure_initial_version, get_version, require_project, save_version, version_dict,
)

router = APIRouter(prefix="/api/projects", tags=["project-versions"])


@router.get("/{project_id}/config")
def get_config(project_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    project = require_project(db, user, project_id)
    return version_dict(ensure_initial_version(db, user, project))


@router.put("/{project_id}/config", status_code=201)
def update_config(
    project_id: int, body: ConfigUpdate,
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    project = require_project(db, user, project_id)
    current = ensure_initial_version(db, user, project)
    snapshot = json.loads(current.snapshot_json)
    snapshot["config"] = body.config.model_dump()
    target_changed = False
    for field in ("owner", "repo"):
        value = getattr(body, field)
        if value is not None and value != snapshot[field]:
            snapshot[field] = value
            target_changed = True
    if target_changed:
        snapshot["project_number"] = None
        snapshot["project_url"] = None
    if body.title is not None:
        snapshot["title"] = body.title
    if "project_number" in body.model_fields_set:
        if snapshot["project_number"] != body.project_number:
            # A URL anterior pertence a outro Project V2; não reutilizá-la.
            snapshot["project_url"] = None
        snapshot["project_number"] = body.project_number
    if "phase_keys" in body.model_fields_set:
        snapshot["phase_keys"] = body.phase_keys
    phases = snapshot.get("phase_keys")
    if phases and not set(phases) <= {m.key for m in body.config.milestones}:
        raise HTTPException(422, "Atualize phase_keys ao remover ou renomear uma fase selecionada.")
    version = save_version(
        db, user, project, base_version=body.base_version, snapshot=snapshot,
        change_note=body.change_note,
    )
    db.commit()
    return version_dict(version)


@router.get("/{project_id}/versions")
def list_versions(
    project_id: int, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    project = require_project(db, user, project_id)
    ensure_initial_version(db, user, project)
    rows = db.scalars(select(ProjectVersion).where(
        ProjectVersion.project_id == project_id
    ).order_by(ProjectVersion.version.desc()).offset(offset).limit(limit)).all()
    return [version_dict(row, include_snapshot=False) for row in rows]


@router.get("/{project_id}/versions/{number}")
def read_version(
    project_id: int, number: int, user: User = Depends(require_user), db: Session = Depends(get_db),
):
    project = require_project(db, user, project_id)
    ensure_initial_version(db, user, project)
    return version_dict(get_version(db, project.id, number))


@router.post("/{project_id}/versions/{number}/restore", status_code=201)
def restore_version(
    project_id: int, number: int, body: VersionRestore,
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    project = require_project(db, user, project_id)
    ensure_initial_version(db, user, project)
    source = get_version(db, project.id, number)
    version = save_version(
        db, user, project, base_version=body.base_version,
        snapshot=json.loads(source.snapshot_json), change_note=body.change_note,
        restored_from_version=source.version,
    )
    db.commit()
    return version_dict(version)
