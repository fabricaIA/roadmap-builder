"""Ponte entre a API e o motor `scripts.roadmap_builder`.

Contém a orquestração que antes vivia em backend/api/api.py::build_roadmap,
agora recebendo o token (PAT do perfil) como argumento em vez de header.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.app.github import humanize_error, missing_project_scope
from scripts.roadmap_builder import (
    add_issues_to_project,
    create_project,
    ensure_issues,
    ensure_labels,
    ensure_milestones,
    format_validation_errors,
    get_project_id,
    link_project_to_repository,
    milestone_due_dates,
    parse_date,
    schedule_issues,
    validate_config,
    validate_remote_access,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = BASE_DIR / "backlog_github_project.json"


def load_backlog_template() -> dict[str, Any]:
    if not TEMPLATE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Arquivo template não encontrado em: {TEMPLATE_PATH}",
        )
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Erro inesperado ao carregar template JSON.")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao ler template de backlog, verifique os logs do servidor",
        )


class _MockArgs:
    def __init__(self, owner: str, repo: str, create_project: bool, project_number):
        self.owner = owner
        self.repo = repo
        self.create_project = create_project
        self.project_number = project_number


def build_roadmap(
    *,
    token: str,
    owner: str,
    repo: str,
    apply: bool,
    create_project_flag: bool,
    project_title: str,
    project_number: int | None,
    project_start_date: str | None,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Cria/atualiza milestones, labels, issues e (opcionalmente) o Project V2.

    Devolve `{status: "success"|"partial", message, issues_created, project_error?}`.
    Levanta HTTPException(400/500) nos erros de validação/negócio.
    """
    validation_errors = validate_config(cfg)
    if validation_errors:
        raise HTTPException(
            status_code=400, detail=format_validation_errors(validation_errors)
        )

    start_date = None
    if project_start_date:
        start_date = parse_date(project_start_date)
    elif cfg.get("schedule", {}).get("project_start_date"):
        start_date = parse_date(cfg["schedule"]["project_start_date"])

    issue_schedule = schedule_issues(cfg, start_date)
    due_dates = milestone_due_dates(issue_schedule)

    wants_project = bool(create_project_flag or project_number)

    if apply:
        remote_errors = validate_remote_access(
            _MockArgs(owner, repo, create_project_flag, project_number), token
        )
        if remote_errors:
            raise HTTPException(
                status_code=400,
                detail=humanize_error(format_validation_errors(remote_errors)),
            )
        if wants_project:
            scope_problem = missing_project_scope(
                token, need_write=bool(create_project_flag)
            )
            if scope_problem:
                raise HTTPException(status_code=400, detail=scope_problem)

    # Milestones / labels / issues
    try:
        milestones = ensure_milestones(owner, repo, token, cfg, apply, due_dates)
        ensure_labels(owner, repo, token, cfg, apply)
        titles = ensure_issues(
            owner, repo, token, cfg, milestones, apply, issue_schedule
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=humanize_error(str(exc)))
    except Exception:
        logger.exception("Erro inesperado ao criar milestones/labels/issues.")
        raise HTTPException(
            status_code=500, detail="Erro interno, verifique os logs do servidor"
        )

    # Painel de projeto — falha aqui não invalida o que já foi criado.
    if wants_project and apply:
        try:
            if create_project_flag:
                project_id = create_project(owner, repo, token, project_title)
            else:
                project_id = get_project_id(owner, token, project_number)
                link_project_to_repository(owner, repo, token, project_id)
            add_issues_to_project(
                owner, repo, token, project_id, cfg, titles, apply, issue_schedule
            )
        except Exception as exc:
            logger.exception("Falha na etapa do painel de projeto.")
            return {
                "status": "partial",
                "message": (
                    "Milestones, labels e issues foram criados. A etapa do painel "
                    "de projeto (Projects V2) não foi concluída."
                ),
                "issues_created": titles,
                "project_error": humanize_error(str(exc)),
            }

    return {
        "status": "success",
        "message": "Roadmap processado com sucesso!",
        "issues_created": titles,
    }
