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
    API,
    add_issues_to_project,
    create_project,
    ensure_issues,
    ensure_labels,
    ensure_milestones,
    format_validation_errors,
    get_project_id,
    link_project_to_repository,
    milestone_due_dates,
    paginate_get,
    parse_date,
    schedule_issues,
    select_issues,
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


def _parse_start_date(project_start_date: str | None, cfg: dict[str, Any]):
    if project_start_date:
        return parse_date(project_start_date)
    if cfg.get("schedule", {}).get("project_start_date"):
        return parse_date(cfg["schedule"]["project_start_date"])
    return None


def _existing_issue_titles(token: str, owner: str, repo: str) -> set[str]:
    rows = paginate_get(
        f"{API}/repos/{owner}/{repo}/issues?state=all&per_page=100", token
    )
    return {r["title"] for r in rows if "pull_request" not in r}


def _tally(results: list[dict[str, Any]]) -> dict[str, int]:
    out = {"created": 0, "updated": 0, "skipped": 0}
    for r in results:
        if r["outcome"] in ("created", "would_create"):
            out["created"] += 1
        elif r["outcome"] in ("updated", "would_update"):
            out["updated"] += 1
    return out


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
    phase_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Cria/atualiza milestones, labels, issues e (opcionalmente) o Project V2.

    `phase_keys` (opcional) restringe a criação de issues às fases dadas;
    milestones/labels continuam garantidos por inteiro.

    Devolve `{status: "success"|"partial", message, issues_created, project_error?}`.
    Levanta HTTPException(400/500) nos erros de validação/negócio.
    """
    validation_errors = validate_config(cfg)
    if validation_errors:
        raise HTTPException(
            status_code=400, detail=format_validation_errors(validation_errors)
        )

    start_date = _parse_start_date(project_start_date, cfg)
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
        milestones = ensure_milestones(
            owner, repo, token, cfg, apply, due_dates, phase_keys=phase_keys
        )
        ensure_labels(owner, repo, token, cfg, apply, phase_keys=phase_keys)
        issue_results = ensure_issues(
            owner, repo, token, cfg, milestones, apply, issue_schedule, phase_keys
        )
        titles = [r["title"] for r in issue_results]
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=humanize_error(str(exc)))
    except Exception:
        logger.exception("Erro inesperado ao criar milestones/labels/issues.")
        raise HTTPException(
            status_code=500, detail="Erro interno, verifique os logs do servidor"
        )

    # Painel de projeto — falha aqui não invalida o que já foi criado.
    project_node_id: str | None = None
    if wants_project and apply:
        try:
            if create_project_flag:
                project_node_id = create_project(owner, repo, token, project_title)
            else:
                project_node_id = get_project_id(owner, token, project_number)
                link_project_to_repository(owner, repo, token, project_node_id)
            add_issues_to_project(
                owner, repo, token, project_node_id, cfg, titles, apply, issue_schedule
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
                "issue_results": issue_results,
                "project_error": humanize_error(str(exc)),
                "project_node_id": project_node_id,
            }

    return {
        "status": "success",
        "message": "Roadmap processado com sucesso!",
        "issues_created": titles,
        "issue_results": issue_results,
        "project_node_id": project_node_id,
    }


def phase_status(
    token: str, owner: str, repo: str, cfg: dict[str, Any]
) -> list[dict[str, Any]]:
    """Estado de cada fase: quantas issues esperadas já existem no repo."""
    existing = _existing_issue_titles(token, owner, repo)
    milestones = cfg.get("milestones") or []
    out = []
    for m in milestones:
        key = m["key"]
        expected = [i for i in cfg.get("issues", []) if i["milestone"] == key]
        exp_titles = [i["title"] for i in expected]
        have = sum(1 for t in exp_titles if t in existing)
        if not exp_titles:
            status = "empty"
        elif have == 0:
            status = "not_created"
        elif have < len(exp_titles):
            status = "partial"
        else:
            status = "created"
        out.append(
            {
                "phase": key,
                "title": m.get("title", key),
                "description": m.get("description", ""),
                "expected": len(exp_titles),
                "existing": have,
                "status": status,
            }
        )
    return out


def apply_phase(
    *,
    token: str,
    owner: str,
    repo: str,
    cfg: dict[str, Any],
    phase_key: str,
    on_duplicate: str = "skip",
    apply: bool = True,
    project_number: int | None = None,
    project_start_date: str | None = None,
) -> dict[str, Any]:
    """Cria apenas as issues de uma fase, tratando duplicação.

    - `on_duplicate="skip"` (default): se a fase já está completa, no-op
      (`status="already_done"`).
    - `on_duplicate="error"`: 409 se a fase já está completa.
    Milestones e labels são sempre garantidos por inteiro (datas coerentes).
    """
    validation_errors = validate_config(cfg)
    if validation_errors:
        raise HTTPException(
            status_code=400, detail=format_validation_errors(validation_errors)
        )

    expected = select_issues(cfg, [phase_key])
    if not expected:
        raise HTTPException(
            status_code=400,
            detail=f"Fase '{phase_key}' não tem issues no template/config.",
        )
    expected_titles = [i["title"] for i in expected]

    start_date = _parse_start_date(project_start_date, cfg)
    issue_schedule = schedule_issues(cfg, start_date)
    due_dates = milestone_due_dates(issue_schedule)

    if not apply:
        results = ensure_issues(
            owner, repo, token, cfg, {}, False, issue_schedule, [phase_key]
        )
        return {"status": "dry_run", "phase": phase_key, "issues": results, **_tally(results)}

    remote_errors = validate_remote_access(
        _MockArgs(owner, repo, False, project_number), token
    )
    if remote_errors:
        raise HTTPException(
            status_code=400,
            detail=humanize_error(format_validation_errors(remote_errors)),
        )

    try:
        existing = _existing_issue_titles(token, owner, repo)
        if all(t in existing for t in expected_titles):
            if on_duplicate == "error":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Fase {phase_key} já foi criada "
                        f"({len(expected_titles)} issues já existem no repositório)."
                    ),
                )
            return {
                "status": "already_done",
                "phase": phase_key,
                "message": f"Fase {phase_key} já está completa — nada a fazer.",
                "created": 0,
                "updated": 0,
                "skipped": len(expected_titles),
                "issues": [
                    {"title": t, "milestone": phase_key, "outcome": "skipped"}
                    for t in expected_titles
                ],
            }

        milestones = ensure_milestones(
            owner, repo, token, cfg, True, due_dates, phase_keys=[phase_key]
        )
        ensure_labels(owner, repo, token, cfg, True, phase_keys=[phase_key])
        results = ensure_issues(
            owner, repo, token, cfg, milestones, True, issue_schedule, [phase_key]
        )
        titles = [r["title"] for r in results]
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=humanize_error(str(exc)))
    except Exception:
        logger.exception("Erro inesperado ao aplicar a fase %s.", phase_key)
        raise HTTPException(
            status_code=500, detail="Erro interno, verifique os logs do servidor"
        )

    project_error = None
    if project_number:
        try:
            project_node_id = get_project_id(owner, token, project_number)
            link_project_to_repository(owner, repo, token, project_node_id)
            add_issues_to_project(
                owner, repo, token, project_node_id, cfg, titles, True, issue_schedule
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao vincular a fase %s ao painel.", phase_key)
            project_error = humanize_error(str(exc))

    tally = _tally(results)
    return {
        "status": "applied",
        "phase": phase_key,
        "message": (
            f"Fase {phase_key}: {tally['created']} criada(s), "
            f"{tally['updated']} atualizada(s)."
        ),
        **tally,
        "issues": results,
        "project_error": project_error,
    }
