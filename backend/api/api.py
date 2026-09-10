import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scripts.roadmap_builder import (
    validate_config,
    format_validation_errors,
    parse_date,
    schedule_issues,
    milestone_due_dates,
    validate_remote_access,
    ensure_milestones,
    ensure_labels,
    ensure_issues,
    create_project,
    get_project_id,
    link_project_to_repository,
    add_issues_to_project,
)

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Roadmap Builder API")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = BASE_DIR / "backlog_github_project.json"

# F4: origens liberadas para CORS, configuráveis por ambiente.
# ALLOWED_ORIGINS="https://app.exemplo.com,https://outro.exemplo.com"
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RoadmapPayload(BaseModel):
    owner: str
    repo: str
    apply: bool = False
    create_project: bool = False
    project_title: str = "RoadmapBuilder"
    project_number: int | None = None
    project_start_date: str | None = None
    config: dict[str, Any]


# --- F6: tradução de erros de baixo nível para mensagens úteis ao usuário ---
def humanize_error(raw: str) -> str:
    text = raw or "Erro desconhecido."
    low = text.lower()
    if "insufficient_scopes" in low or "required scopes" in low:
        return (
            "O token do GitHub não tem os escopos necessários. Para criar ou "
            "vincular painéis (Projects V2) o token precisa do escopo `project` "
            "(ou `read:project` para apenas vincular). Ajuste em "
            "https://github.com/settings/tokens e tente novamente."
        )
    if "bad credentials" in low or "401" in low:
        return "Token do GitHub inválido ou expirado."
    if "api rate limit exceeded" in low or "rate limit" in low:
        return "Limite de requisições da API do GitHub atingido. Aguarde alguns minutos e tente novamente."
    if "not found" in low or "nao encontrado" in low or "não encontrado" in low:
        return (
            "Repositório não encontrado ou o token não tem acesso a ele. "
            "Confira owner, repo e as permissões do token."
        )
    return text


# --- F5: pré-checagem de escopo do token antes de qualquer escrita ---
def missing_project_scope(token: str, need_write: bool) -> str | None:
    """Retorna uma mensagem se faltar escopo de Project; None se estiver ok
    ou se não for possível determinar (ex.: fine-grained PAT não expõe escopos)."""
    req = urllib.request.Request("https://api.github.com/", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req) as resp:
            header = resp.headers.get("X-OAuth-Scopes")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return "Token do GitHub inválido ou sem permissão para consultar a API."
        return None
    except urllib.error.URLError:
        return None

    if header is None:
        # Sem cabeçalho de escopos (fine-grained PAT ou GitHub App): não dá para
        # pré-validar; segue e, se faltar permissão, o erro é tratado depois.
        return None

    scopes = {s.strip() for s in header.split(",") if s.strip()}
    if need_write and "project" not in scopes:
        return (
            "Para criar um painel (Projects V2) o token precisa do escopo "
            f"`project`. Escopos atuais do token: {', '.join(sorted(scopes)) or 'nenhum'}."
        )
    if not need_write and "project" not in scopes and "read:project" not in scopes:
        return (
            "Para vincular um painel existente o token precisa do escopo "
            f"`read:project` (ou `project`). Escopos atuais: {', '.join(sorted(scopes)) or 'nenhum'}."
        )
    return None


@app.get("/api/backlog-template")
def get_backlog_template():
    """Lê o backlog_github_project.json da raiz e devolve como única fonte de verdade."""
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


@app.post("/api/build-roadmap")
def build_roadmap(payload: RoadmapPayload, github_token: str = Header(...)):
    cfg = payload.config

    # 1. Validação do Config
    validation_errors = validate_config(cfg)
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail=format_validation_errors(validation_errors),
        )

    project_start_date = None
    if payload.project_start_date:
        project_start_date = parse_date(payload.project_start_date)
    elif cfg.get("schedule", {}).get("project_start_date"):
        project_start_date = parse_date(cfg["schedule"]["project_start_date"])

    issue_schedule = schedule_issues(cfg, project_start_date)
    due_dates = milestone_due_dates(issue_schedule)

    wants_project = bool(payload.create_project or payload.project_number)

    class MockArgs:
        owner = payload.owner
        repo = payload.repo
        create_project = payload.create_project
        project_number = payload.project_number

    if payload.apply:
        remote_errors = validate_remote_access(MockArgs(), github_token)
        if remote_errors:
            raise HTTPException(
                status_code=400,
                detail=humanize_error(format_validation_errors(remote_errors)),
            )

        # F5: falha cedo se o token não tem escopo de Project, ANTES de criar
        # milestones/labels/issues (evita aplicação parcial "surpresa").
        if wants_project:
            scope_problem = missing_project_scope(
                github_token, need_write=bool(payload.create_project)
            )
            if scope_problem:
                raise HTTPException(status_code=400, detail=scope_problem)

    # 2. Criação de milestones / labels / issues
    try:
        milestones = ensure_milestones(
            payload.owner,
            payload.repo,
            github_token,
            cfg,
            payload.apply,
            due_dates,
        )
        ensure_labels(payload.owner, payload.repo, github_token, cfg, payload.apply)
        titles = ensure_issues(
            payload.owner,
            payload.repo,
            github_token,
            cfg,
            milestones,
            payload.apply,
            issue_schedule,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=humanize_error(str(exc)))
    except Exception:
        logger.exception("Erro inesperado ao criar milestones/labels/issues.")
        raise HTTPException(
            status_code=500,
            detail="Erro interno, verifique os logs do servidor",
        )

    # 3. Painel de projeto (Projects V2) — F1: falha aqui NÃO invalida o que já
    # foi criado; retorna sucesso parcial com o motivo.
    if wants_project and payload.apply:
        try:
            if payload.create_project:
                project_id = create_project(
                    payload.owner,
                    payload.repo,
                    github_token,
                    payload.project_title,
                )
            else:
                project_id = get_project_id(
                    payload.owner, github_token, payload.project_number
                )
                link_project_to_repository(
                    payload.owner, payload.repo, github_token, project_id
                )

            add_issues_to_project(
                payload.owner,
                payload.repo,
                github_token,
                project_id,
                cfg,
                titles,
                payload.apply,
                issue_schedule,
            )
        except Exception as exc:
            logger.exception("Falha ao criar/vincular o painel de projeto.")
            return {
                "status": "partial",
                "message": "Milestones, labels e issues criados. O painel de projeto falhou.",
                "issues_created": titles,
                "project_error": humanize_error(str(exc)),
            }

    return {
        "status": "success",
        "message": "Roadmap processado com sucesso!",
        "issues_created": titles,
    }
