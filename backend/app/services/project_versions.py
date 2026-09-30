"""Histórico por projeto e atualização otimista em uma única transação."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Project, ProjectVersion, User
from backend.app.services.roadmap import load_backlog_template


def require_project(db: Session, user: User, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.created_by_user_id != user.id:
        raise HTTPException(404, "Projeto não encontrado.")
    return project


def get_version(db: Session, project_id: int, number: int) -> ProjectVersion:
    version = db.scalar(select(ProjectVersion).where(
        ProjectVersion.project_id == project_id, ProjectVersion.version == number,
    ))
    if version is None:
        raise HTTPException(404, "Versão do projeto não encontrada.")
    return version


def version_dict(version: ProjectVersion, *, include_snapshot=True) -> dict:
    result = {
        "id": version.id, "project_id": version.project_id, "version": version.version,
        "change_note": version.change_note,
        "created_by_user_id": version.created_by_user_id,
        "author_login": version.author_login,
        "created_at": (version.created_at if version.created_at.tzinfo else version.created_at.replace(tzinfo=timezone.utc)).isoformat(),
        "restored_from_version": version.restored_from_version,
    }
    if include_snapshot:
        result["snapshot"] = json.loads(version.snapshot_json)
    return result


def project_config(project: Project) -> dict:
    try:
        config = json.loads(project.config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    if isinstance(config, dict) and (project.current_version > 0 or config.get("issues")):
        return config
    return load_backlog_template()


def snapshot_for(project: Project, config: dict, phase_keys=None) -> dict:
    return {
        "owner": project.owner, "repo": project.repo, "title": project.title,
        "project_number": project.project_number, "project_url": project.project_url,
        "phase_keys": phase_keys, "config": deepcopy(config),
    }


def save_version(
    db: Session, user: User, project: Project, *, base_version: int,
    snapshot: dict, change_note: str, restored_from_version: int | None = None,
) -> ProjectVersion:
    """Reserva o número com compare-and-swap; snapshot e Project são atômicos.

    Não efetua commit: a rota confirma todos os seus registros em conjunto.
    """
    duplicate = db.scalar(select(Project.id).where(
        Project.created_by_user_id == project.created_by_user_id,
        Project.id != project.id,
        func.lower(Project.owner) == snapshot["owner"].lower(),
        func.lower(Project.repo) == snapshot["repo"].lower(),
    ))
    if duplicate is not None:
        raise HTTPException(409, "Você já possui um projeto para esse owner e repositório.")
    try:
        changed = db.execute(update(Project).where(
            Project.id == project.id, Project.current_version == base_version,
        ).values(
            current_version=base_version + 1, title=snapshot["title"],
            owner=snapshot["owner"], repo=snapshot["repo"], org_login=snapshot["owner"],
            project_number=snapshot["project_number"], project_url=snapshot["project_url"],
            config_json=json.dumps(snapshot["config"], ensure_ascii=False),
        ).execution_options(synchronize_session=False))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Conflito com outro projeto para esse repositório.") from exc
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "O projeto foi alterado. Recarregue a configuração antes de salvar.")
    version = ProjectVersion(
        project_id=project.id, version=base_version + 1,
        snapshot_json=json.dumps(snapshot, ensure_ascii=False), change_note=change_note,
        created_by_user_id=user.id, author_login=user.login,
        restored_from_version=restored_from_version,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Conflito ao salvar versão. Recarregue o projeto.") from exc
    db.refresh(project)
    return version


def ensure_initial_version(db: Session, user: User, project: Project) -> ProjectVersion:
    # Projetos antigos são migrados pelo Alembic. Também cobre registros criados
    # por integrações locais que ainda não chamam save_version.
    if project.current_version:
        return get_version(db, project.id, project.current_version)
    version = save_version(
        db, user, project, base_version=0,
        snapshot=snapshot_for(project, project_config(project)),
        change_note="Configuração inicial registrada",
    )
    db.commit()
    return version
