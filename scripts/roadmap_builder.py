#!/usr/bin/env python3
"""RoadmapBuilder: cria milestones, labels, issues e Project v2 no GitHub.

Uso (dry-run):
  python scripts/roadmap_builder.py --owner ORG --repo REPO

Com cronograma estimado:
  python scripts/roadmap_builder.py --owner ORG --repo REPO --project-start-date 2026-05-01

Aplicar de fato:
  GITHUB_TOKEN=... python scripts/roadmap_builder.py --owner ORG --repo REPO --apply
"""

from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
DATE_FORMAT = "%Y-%m-%d"
VALID_DURATION_UNITS = {"days", "months"}

# A API de Projects V2 devolve erros transitorios (UNPROCESSABLE "temporary
# conflict", limites secundarios) quando muitos itens sao adicionados em
# sequencia. Repetimos com backoff exponencial antes de desistir.
GRAPHQL_MAX_ATTEMPTS = 6
GRAPHQL_RETRY_BASE_DELAY = 1.0
GRAPHQL_RETRY_MAX_DELAY = 8.0
PROJECT_ITEM_PACING = 0.25
_TRANSIENT_MARKERS = (
    "temporary conflict",
    "please try again",
    "try again later",
    "was submitted too quickly",
    "submitted too quickly",
    "secondary rate limit",
)


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def require_mapping(value: Any, name: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"`{name}` deve ser um objeto")
        return {}
    return value


def require_list(value: Any, name: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"`{name}` deve ser uma lista")
        return []
    return value


def validate_string_list(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"`{name}` deve ser uma lista nao vazia")
        return
    for idx, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"`{name}[{idx}]` deve ser um texto nao vazio")


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def format_validation_errors(errors: list[str]) -> str:
    return "Validacao falhou:\n" + "\n".join(f"- {error}" for error in errors)


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Data invalida '{value}'. Use AAAA-MM-DD.") from exc


def add_days(start: date, days: int) -> date:
    if days < 1:
        raise ValueError("A duracao estimada deve ser maior ou igual a 1 dia")
    return start + timedelta(days=days - 1)


def add_months(start: date, months: int) -> date:
    if months < 1:
        raise ValueError("A duracao estimada deve ser maior ou igual a 1 mes")

    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_duration(start: date, duration: dict[str, Any]) -> date:
    value = int(duration["value"])
    unit = duration["unit"]
    if unit == "days":
        return add_days(start, value)
    if unit == "months":
        return add_months(start, value) - timedelta(days=1)
    raise ValueError(f"Unidade de duracao invalida: {unit}")


def iso_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


def validate_config(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schedule = require_mapping(cfg.get("schedule"), "schedule", errors)
    milestones = require_list(cfg.get("milestones"), "milestones", errors)
    labels = require_list(cfg.get("labels"), "labels", errors)
    issues = require_list(cfg.get("issues"), "issues", errors)

    if schedule.get("project_start_date"):
        try:
            parse_date(str(schedule["project_start_date"]))
        except argparse.ArgumentTypeError as exc:
            errors.append(f"`schedule.project_start_date`: {exc}")

    date_fields = schedule.get("project_date_fields", {})
    if date_fields:
        date_fields = require_mapping(date_fields, "schedule.project_date_fields", errors)
        for key in ("start", "end"):
            value = date_fields.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"`schedule.project_date_fields.{key}` deve ser um texto nao vazio")

    milestone_keys: list[str] = []
    milestone_titles: list[str] = []
    for index, milestone in enumerate(milestones, start=1):
        if not isinstance(milestone, dict):
            errors.append(f"`milestones[{index}]` deve ser um objeto")
            continue
        key = milestone.get("key")
        title = milestone.get("title")
        if not isinstance(key, str) or not key.strip():
            errors.append(f"`milestones[{index}].key` deve ser um texto nao vazio")
        else:
            milestone_keys.append(key)
        if not isinstance(title, str) or not title.strip():
            errors.append(f"`milestones[{index}].title` deve ser um texto nao vazio")
        else:
            milestone_titles.append(title)

    for key in duplicate_values(milestone_keys):
        errors.append(f"Milestone duplicado: {key}")
    for title in duplicate_values(milestone_titles):
        errors.append(f"Titulo de milestone duplicado: {title}")

    durations = schedule.get("milestone_durations", {})
    durations = require_mapping(durations, "schedule.milestone_durations", errors)
    milestone_key_set = set(milestone_keys)
    for key in milestone_keys:
        duration = durations.get(key)
        if not isinstance(duration, dict):
            errors.append(f"Duracao nao configurada para o milestone {key}")
            continue
        value = duration.get("value")
        unit = duration.get("unit")
        if not isinstance(value, int) or value < 1:
            errors.append(f"`schedule.milestone_durations.{key}.value` deve ser inteiro >= 1")
        if unit not in VALID_DURATION_UNITS:
            errors.append(
                f"`schedule.milestone_durations.{key}.unit` deve ser um de: "
                f"{', '.join(sorted(VALID_DURATION_UNITS))}"
            )
    for key in sorted(set(durations) - milestone_key_set):
        errors.append(f"Duracao configurada para milestone inexistente: {key}")

    label_names: list[str] = []
    for index, label in enumerate(labels, start=1):
        if not isinstance(label, dict):
            errors.append(f"`labels[{index}]` deve ser um objeto")
            continue
        name = label.get("name")
        color = label.get("color")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"`labels[{index}].name` deve ser um texto nao vazio")
        else:
            label_names.append(name)
        if not isinstance(color, str) or len(color) != 6:
            errors.append(f"`labels[{index}].color` deve ter 6 caracteres hexadecimais")
        else:
            try:
                int(color, 16)
            except ValueError:
                errors.append(f"`labels[{index}].color` deve ser hexadecimal")

    for name in duplicate_values(label_names):
        errors.append(f"Label duplicada: {name}")

    label_name_set = set(label_names)
    issue_titles: list[str] = []
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            errors.append(f"`issues[{index}]` deve ser um objeto")
            continue
        title = issue.get("title")
        milestone = issue.get("milestone")
        issue_labels = issue.get("labels", [])
        if not isinstance(title, str) or not title.strip():
            errors.append(f"`issues[{index}].title` deve ser um texto nao vazio")
        else:
            issue_titles.append(title)
        if milestone not in milestone_key_set:
            errors.append(f"`issues[{index}]` referencia milestone inexistente: {milestone}")
        if not isinstance(issue_labels, list):
            errors.append(f"`issues[{index}].labels` deve ser uma lista")
            continue
        for label_name in issue_labels:
            if label_name not in label_name_set:
                errors.append(f"`issues[{index}]` referencia label inexistente: {label_name}")

        entregaveis = issue.get("entregaveis")
        criterios_aceite = issue.get("criterios_aceite")
        if entregaveis is not None:
            validate_string_list(entregaveis, f"issues[{index}].entregaveis", errors)
        if criterios_aceite is not None:
            validate_string_list(criterios_aceite, f"issues[{index}].criterios_aceite", errors)

    for title in duplicate_values(issue_titles):
        errors.append(f"Issue duplicada: {title}")

    return errors


def milestone_windows(cfg: dict[str, Any], project_start_date: date | None) -> dict[str, dict[str, Any]]:
    """Calcula a janela sequencial de cada milestone."""
    if project_start_date is None:
        return {}

    durations = cfg.get("schedule", {}).get("milestone_durations", {})
    current_start = project_start_date
    windows: dict[str, dict[str, Any]] = {}

    for sequence, milestone in enumerate(cfg["milestones"], start=1):
        key = milestone["key"]
        duration = durations.get(key)
        if duration is None:
            raise ValueError(f"Duracao nao configurada para o milestone {key}")

        end_date = add_duration(current_start, duration)
        windows[key] = {
            "sequence": sequence,
            "start_date": current_start,
            "end_date": end_date,
            "duration": duration,
        }
        current_start = end_date + timedelta(days=1)

    return windows


def schedule_issues(cfg: dict[str, Any], project_start_date: date | None) -> dict[str, dict[str, Any]]:
    """Alinha todas as issues a janela prevista do milestone correspondente."""
    if project_start_date is None:
        return {}

    windows = milestone_windows(cfg, project_start_date)
    schedule: dict[str, dict[str, Any]] = {}

    for index, issue in enumerate(cfg["issues"], start=1):
        window = windows[issue["milestone"]]
        duration = window["duration"]
        schedule[issue["title"]] = {
            "sequence": index,
            "milestone_sequence": window["sequence"],
            "duration_value": int(duration["value"]),
            "duration_unit": duration["unit"],
            "start_date": window["start_date"],
            "end_date": window["end_date"],
            "milestone": issue["milestone"],
        }

    return schedule


def milestone_due_dates(issue_schedule: dict[str, dict[str, Any]]) -> dict[str, date]:
    out: dict[str, date] = {}
    for item in issue_schedule.values():
        milestone = item["milestone"]
        end_date = item["end_date"]
        if milestone not in out or end_date > out[milestone]:
            out[milestone] = end_date
    return out


def request_json(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404 and "/repos/" in url:
            parsed = urllib.parse.urlparse(url)
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "repos":
                repo_name = "/".join(parts[1:3])
                raise RuntimeError(
                    f"Repositorio {repo_name} nao encontrado ou token sem acesso. "
                    "Confira --owner, --repo e se o GITHUB_TOKEN tem permissao para esse repositorio."
                ) from exc
        raise RuntimeError(f"HTTP {exc.code} em {method} {url}: {body}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise RuntimeError(
                "Falha ao validar o certificado SSL do GitHub. "
                "No macOS com Python instalado via python.org, execute "
                "'/Applications/Python 3.14/Install Certificates.command' "
                "e tente novamente."
            ) from exc
        raise


def _is_transient(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _TRANSIENT_MARKERS) or (
        "http 50" in low  # 500/502/503/504 do endpoint GraphQL sob carga
    )


def graphql(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    last_error = "erro desconhecido"
    for attempt in range(1, GRAPHQL_MAX_ATTEMPTS + 1):
        try:
            data = request_json(
                "POST", GRAPHQL, token, {"query": query, "variables": variables}
            )
        except RuntimeError as exc:
            last_error = str(exc)
            if attempt < GRAPHQL_MAX_ATTEMPTS and _is_transient(last_error):
                delay = min(GRAPHQL_RETRY_BASE_DELAY * (2 ** (attempt - 1)), GRAPHQL_RETRY_MAX_DELAY)
                print(
                    f"[RETRY] GraphQL transitorio (tentativa {attempt}/{GRAPHQL_MAX_ATTEMPTS}): "
                    f"{last_error[:120]} - aguardando {delay:.0f}s"
                )
                time.sleep(delay)
                continue
            raise

        if "errors" not in data:
            return data["data"]

        last_error = f"GraphQL erro: {data['errors']}"
        if attempt < GRAPHQL_MAX_ATTEMPTS and _is_transient(last_error):
            delay = min(GRAPHQL_RETRY_BASE_DELAY * (2 ** (attempt - 1)), GRAPHQL_RETRY_MAX_DELAY)
            print(
                f"[RETRY] GraphQL transitorio (tentativa {attempt}/{GRAPHQL_MAX_ATTEMPTS}): "
                f"{last_error[:120]} - aguardando {delay:.0f}s"
            )
            time.sleep(delay)
            continue
        raise RuntimeError(last_error)

    raise RuntimeError(last_error)


def paginate_get(base_url: str, token: str, per_page: int = 100) -> list[dict[str, Any]]:
    """GET paginado da API REST. `base_url` deve conter '?' e `per_page`.

    Corrige a limitacao anterior de ler apenas a primeira pagina (100 itens),
    que quebrava a deducao de duplicados em repositorios maiores.
    """
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        chunk = request_json("GET", f"{base_url}&page={page}", token)
        if not chunk:
            break
        items.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
    return items


def phases_filter(phase_keys: list[str] | None) -> set[str] | None:
    return None if phase_keys is None else set(phase_keys)


def phase_label_names(cfg: dict[str, Any], phase_keys: list[str] | None) -> set[str] | None:
    """Nomes das labels usadas pelas issues das fases dadas (None = todas)."""
    keys = phases_filter(phase_keys)
    if keys is None:
        return None
    used: set[str] = set()
    for issue in cfg["issues"]:
        if issue["milestone"] in keys:
            used.update(issue.get("labels", []))
    return used


def ensure_milestones(
    owner: str,
    repo: str,
    token: str,
    cfg: dict[str, Any],
    apply: bool,
    due_dates: dict[str, date],
    phase_keys: list[str] | None = None,
) -> dict[str, int]:
    keys = phases_filter(phase_keys)
    selected = [
        m for m in cfg["milestones"] if keys is None or m["key"] in keys
    ]
    url = f"{API}/repos/{owner}/{repo}/milestones?state=all&per_page=100"
    if not apply:
        print(f"[DRY-RUN] Consultaria milestones: {url}")
        for m in selected:
            due_on = due_dates.get(m["key"])
            if due_on:
                print(f"[DRY-RUN] Milestone {m['key']} teria data alvo {iso_date(due_on)}")
        return {}

    current = paginate_get(
        f"{API}/repos/{owner}/{repo}/milestones?state=all&per_page=100", token
    )
    by_title = {m["title"]: m["number"] for m in current}
    out: dict[str, int] = {}

    for m in selected:
        due_on = due_dates.get(m["key"])
        if m["title"] in by_title:
            out[m["key"]] = by_title[m["title"]]
            print(f"[OK] Milestone ja existe: {m['title']} (#{by_title[m['title']]})")
            if due_on:
                request_json(
                    "PATCH",
                    f"{API}/repos/{owner}/{repo}/milestones/{by_title[m['title']]}",
                    token,
                    {"due_on": f"{iso_date(due_on)}T23:59:59Z"},
                )
                print(f"[OK] Data alvo atualizada: {m['title']} -> {iso_date(due_on)}")
            continue

        payload = {"title": m["title"], "description": m["description"]}
        if due_on:
            payload["due_on"] = f"{iso_date(due_on)}T23:59:59Z"
        created = request_json(
            "POST",
            f"{API}/repos/{owner}/{repo}/milestones",
            token,
            payload,
        )
        out[m["key"]] = created["number"]
        suffix = f" - vence em {iso_date(due_on)}" if due_on else ""
        print(f"[NEW] Milestone criada: {m['title']} (#{created['number']}){suffix}")

    return out


def ensure_labels(
    owner: str,
    repo: str,
    token: str,
    cfg: dict[str, Any],
    apply: bool,
    phase_keys: list[str] | None = None,
) -> None:
    names = phase_label_names(cfg, phase_keys)
    selected = [
        label for label in cfg["labels"] if names is None or label["name"] in names
    ]
    url = f"{API}/repos/{owner}/{repo}/labels?per_page=100"
    if not apply:
        print(f"[DRY-RUN] Consultaria labels: {url} ({len(selected)} a garantir)")
        return

    current = paginate_get(
        f"{API}/repos/{owner}/{repo}/labels?per_page=100", token
    )
    existing = {label["name"] for label in current}

    for label in selected:
        if label["name"] in existing:
            print(f"[OK] Label ja existe: {label['name']}")
            continue
        request_json(
            "POST",
            f"{API}/repos/{owner}/{repo}/labels",
            token,
            {
                "name": label["name"],
                "color": label["color"],
                "description": label["description"],
            },
        )
        print(f"[NEW] Label criada: {label['name']}")


def issue_body(issue: dict[str, Any], schedule: dict[str, Any] | None = None) -> str:
    schedule_block = ""
    if schedule:
        unit_labels = {
            "days": "dia" if schedule["duration_value"] == 1 else "dias",
            "months": "mes" if schedule["duration_value"] == 1 else "meses",
        }
        unit_label = unit_labels[schedule["duration_unit"]]
        schedule_block = (
            "\n## Planejamento\n"
            f"- Sequencia da issue: {schedule['sequence']}\n"
            f"- Sequencia do milestone: {schedule['milestone_sequence']}\n"
            f"- Inicio estimado: {iso_date(schedule['start_date'])}\n"
            f"- Fim estimado: {iso_date(schedule['end_date'])}\n"
            f"- Duracao estimada do milestone: {schedule['duration_value']} {unit_label}\n"
        )

    objetivo = issue.get("description", "Executar esta atividade conforme o processo da Fabrica de IA.")

    entregaveis = issue.get("entregaveis", ["Evidencia principal anexada", "Criterios de aceite validados"])
    criterios_aceite = issue.get(
        "criterios_aceite",
        ["Resultado revisado com stakeholders", "Registro no Project atualizado"],
    )
    entregaveis_block = "\n".join(f"- [ ] {item}" for item in entregaveis)
    criterios_block = "\n".join(f"- [ ] {item}" for item in criterios_aceite)

    return (
        "## Contexto\n"
        f"Fase/marco: **{issue['milestone']}**.\n\n"
        "## Objetivo\n"
        f"{objetivo}\n\n"
        "## Entregaveis\n"
        f"{entregaveis_block}\n\n"
        "## Criterios de aceite\n"
        f"{criterios_block}\n"
        f"{schedule_block}"
    )


def select_issues(
    cfg: dict[str, Any], phase_keys: list[str] | None
) -> list[dict[str, Any]]:
    """Issues do cfg, opcionalmente filtradas pelas fases (milestone keys)."""
    if phase_keys is None:
        return list(cfg["issues"])
    keys = set(phase_keys)
    return [i for i in cfg["issues"] if i["milestone"] in keys]


def ensure_issues(
    owner: str,
    repo: str,
    token: str,
    cfg: dict[str, Any],
    milestones: dict[str, int],
    apply: bool,
    issue_schedule: dict[str, dict[str, Any]],
    phase_keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Cria/atualiza issues (idempotente por titulo).

    Retorna, para cada issue considerada, `{"title", "milestone", "outcome"}`
    com outcome em {"created", "updated", "would_create", "would_update"}.
    """
    selected = select_issues(cfg, phase_keys)

    if not apply:
        results = []
        for item in selected:
            schedule = issue_schedule.get(item["title"])
            if schedule:
                unit_label = "dia(s)" if schedule["duration_unit"] == "days" else "mes(es)"
                print(
                    "[DRY-RUN] "
                    f"{item['title']}: {iso_date(schedule['start_date'])} "
                    f"-> {iso_date(schedule['end_date'])} "
                    f"({schedule['duration_value']} {unit_label}, milestone {schedule['milestone']})"
                )
            results.append(
                {
                    "title": item["title"],
                    "milestone": item["milestone"],
                    "outcome": "would_create",
                }
            )
        print(f"[DRY-RUN] Criaria/atualizaria {len(results)} issues")
        return results

    current = paginate_get(
        f"{API}/repos/{owner}/{repo}/issues?state=all&per_page=100", token
    )
    existing = {
        item.get("title"): item for item in current if "pull_request" not in item
    }

    results: list[dict[str, Any]] = []
    for item in selected:
        schedule = issue_schedule.get(item["title"])
        payload_body = {
            "body": issue_body(item, schedule),
            "labels": item["labels"],
            "milestone": milestones[item["milestone"]],
        }
        if item["title"] in existing:
            request_json(
                "PATCH",
                f"{API}/repos/{owner}/{repo}/issues/{existing[item['title']]['number']}",
                token,
                payload_body,
            )
            print(f"[OK] Issue atualizada: {item['title']}")
            outcome = "updated"
        else:
            request_json(
                "POST",
                f"{API}/repos/{owner}/{repo}/issues",
                token,
                {"title": item["title"], **payload_body},
            )
            print(f"[NEW] Issue criada: {item['title']}")
            outcome = "created"
        results.append(
            {"title": item["title"], "milestone": item["milestone"], "outcome": outcome}
        )

    return results


def get_owner_type(owner: str, token: str) -> str:
    data = request_json("GET", f"{API}/users/{owner}", token)
    owner_type = data.get("type")
    if owner_type not in {"User", "Organization"}:
        raise RuntimeError(f"Nao foi possivel resolver o tipo do owner '{owner}'")
    return owner_type


def validate_remote_access(args: argparse.Namespace, token: str) -> list[str]:
    errors: list[str] = []
    try:
        owner_type = get_owner_type(args.owner, token)
        print(f"[OK] Owner encontrado: {args.owner} ({owner_type})")
    except Exception as exc:
        errors.append(f"Owner/token invalido: {exc}")
        return errors

    try:
        request_json("GET", f"{API}/repos/{args.owner}/{args.repo}", token)
        print(f"[OK] Repositorio acessivel: {args.owner}/{args.repo}")
    except Exception as exc:
        errors.append(f"Repositorio/token invalido: {exc}")

    if args.create_project and args.project_number:
        errors.append("Use apenas um: --create-project ou --project-number")

    if args.project_number:
        try:
            get_project_id(args.owner, token, args.project_number)
        except Exception as exc:
            errors.append(f"Project existente invalido: {exc}")

    return errors


def get_project_owner_id(owner: str, token: str) -> str:
    owner_type = get_owner_type(owner, token)
    root_field = "organization" if owner_type == "Organization" else "user"
    query_owner = f"""
    query($login: String!) {{
      {root_field}(login: $login) {{ id }}
    }}
    """
    data = graphql(token, query_owner, {"login": owner})
    owner_data = data.get(root_field)
    if owner_data is None:
        raise RuntimeError(f"Nao foi possivel resolver owner '{owner}' como {owner_type}")
    return owner_data["id"]


def get_repository_id(owner: str, repo: str, token: str) -> str:
    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) { id }
    }
    """
    data = graphql(token, query, {"owner": owner, "repo": repo})
    repository = data.get("repository")
    if repository is None:
        raise RuntimeError(f"Repositorio {owner}/{repo} nao encontrado")
    return repository["id"]


def create_project(owner: str, repo: str, token: str, title: str) -> str:
    owner_id = get_project_owner_id(owner, token)
    mutation = """
    mutation($ownerId: ID!, $title: String!) {
      createProjectV2(input: {ownerId: $ownerId, title: $title}) {
        projectV2 { id title number }
      }
    }
    """
    out = graphql(token, mutation, {"ownerId": owner_id, "title": title})
    p = out["createProjectV2"]["projectV2"]
    print(f"[NEW] Project criado: {p['title']} (number={p['number']})")
    link_project_to_repository(owner, repo, token, p["id"])
    return p["id"]


def get_project_id(owner: str, token: str, project_number: int) -> str:
    owner_type = get_owner_type(owner, token)
    root_field = "organization" if owner_type == "Organization" else "user"
    query = f"""
    query($login: String!, $number: Int!) {{
      {root_field}(login: $login) {{ projectV2(number: $number) {{ id title }} }}
    }}
    """
    data = graphql(token, query, {"login": owner, "number": project_number})
    owner_data = data.get(root_field)
    project = owner_data.get("projectV2") if owner_data else None
    if not project:
        raise RuntimeError(f"Project number {project_number} nao encontrado em {owner}")
    print(f"[OK] Project encontrado: {project['title']}")
    return project["id"]


def link_project_to_repository(owner: str, repo: str, token: str, project_id: str) -> None:
    repository_id = get_repository_id(owner, repo, token)
    mutation = """
    mutation($projectId: ID!, $repositoryId: ID!) {
      linkProjectV2ToRepository(input: {projectId: $projectId, repositoryId: $repositoryId}) {
        repository { nameWithOwner }
      }
    }
    """
    out = graphql(token, mutation, {"projectId": project_id, "repositoryId": repository_id})
    linked_repo = out["linkProjectV2ToRepository"]["repository"]["nameWithOwner"]
    print(f"[OK] Project vinculado ao repositorio: {linked_repo}")


def project_fields(token: str, project_id: str) -> dict[str, dict[str, str]]:
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2Field { id name dataType }
              ... on ProjectV2IterationField { id name dataType }
              ... on ProjectV2SingleSelectField { id name dataType }
            }
          }
        }
      }
    }
    """
    data = graphql(token, query, {"projectId": project_id})
    fields = data["node"]["fields"]["nodes"]
    return {field["name"]: field for field in fields if field}


def create_project_date_field(token: str, project_id: str, name: str) -> str:
    mutation = """
    mutation($projectId: ID!, $name: String!) {
      createProjectV2Field(input: {projectId: $projectId, dataType: DATE, name: $name}) {
        projectV2Field {
          ... on ProjectV2Field { id name dataType }
        }
      }
    }
    """
    data = graphql(token, mutation, {"projectId": project_id, "name": name})
    field = data["createProjectV2Field"]["projectV2Field"]
    print(f"[NEW] Campo de data criado no Project: {field['name']}")
    return field["id"]


def ensure_project_date_field(token: str, project_id: str, name: str) -> str:
    field = project_fields(token, project_id).get(name)
    if field:
        if field["dataType"] != "DATE":
            raise RuntimeError(f"Campo '{name}' ja existe no Project, mas nao e do tipo DATE")
        print(f"[OK] Campo de data ja existe no Project: {name}")
        return field["id"]
    return create_project_date_field(token, project_id, name)


def project_item_ids_by_issue_title(token: str, project_id: str) -> dict[str, str]:
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100) {
            nodes {
              id
              content {
                ... on Issue { title }
              }
            }
          }
        }
      }
    }
    """
    data = graphql(token, query, {"projectId": project_id})
    items = data["node"]["items"]["nodes"]
    return {
        item["content"]["title"]: item["id"]
        for item in items
        if item.get("content") and item["content"].get("title")
    }


def update_project_item_date(token: str, project_id: str, item_id: str, field_id: str, value: date) -> None:
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: Date!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: {date: $value}
        }
      ) {
        projectV2Item { id }
      }
    }
    """
    graphql(
        token,
        mutation,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "value": iso_date(value),
        },
    )


def update_project_dates(
    token: str,
    project_id: str,
    cfg: dict[str, Any],
    titles: list[str],
    issue_schedule: dict[str, dict[str, Any]],
) -> None:
    date_fields = cfg.get("schedule", {}).get("project_date_fields", {})
    start_field_name = date_fields.get("start", "Inicio previsto")
    end_field_name = date_fields.get("end", "Fim previsto")
    start_field_id = ensure_project_date_field(token, project_id, start_field_name)
    end_field_id = ensure_project_date_field(token, project_id, end_field_name)
    item_ids = project_item_ids_by_issue_title(token, project_id)

    for title in titles:
        item_id = item_ids.get(title)
        schedule = issue_schedule.get(title)
        if not item_id or not schedule:
            print(f"[WARN] Item do Project sem datas atualizadas: {title}")
            continue
        update_project_item_date(
            token,
            project_id,
            item_id,
            start_field_id,
            schedule["start_date"],
        )
        update_project_item_date(
            token,
            project_id,
            item_id,
            end_field_id,
            schedule["end_date"],
        )
        print(
            "[OK] Datas atualizadas no Project: "
            f"{title} ({iso_date(schedule['start_date'])} -> {iso_date(schedule['end_date'])})"
        )
        time.sleep(PROJECT_ITEM_PACING)


def add_issues_to_project(
    owner: str,
    repo: str,
    token: str,
    project_id: str,
    cfg: dict[str, Any],
    titles: list[str],
    apply: bool,
    issue_schedule: dict[str, dict[str, Any]],
) -> None:
    if not apply:
        print(f"[DRY-RUN] Adicionaria {len(titles)} issues ao project {project_id}")
        return

    all_issues = paginate_get(
        f"{API}/repos/{owner}/{repo}/issues?state=all&per_page=100", token
    )
    by_title = {i["title"]: i for i in all_issues if "pull_request" not in i}

    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """

    for title in titles:
        issue = by_title.get(title)
        if not issue:
            print(f"[WARN] Issue nao encontrada para adicionar no project: {title}")
            continue
        try:
            graphql(token, mutation, {"projectId": project_id, "contentId": issue["node_id"]})
            print(f"[OK] Issue adicionada ao project: {title}")
        except RuntimeError as exc:
            if "already" not in str(exc).lower() and "existe" not in str(exc).lower():
                raise
            print(f"[OK] Issue ja estava no project: {title}")
        # Ritmo entre chamadas para reduzir os "temporary conflict" da API de Projects V2.
        time.sleep(PROJECT_ITEM_PACING)

    update_project_dates(token, project_id, cfg, titles, issue_schedule)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RoadmapBuilder: cria milestones/issues/project no GitHub")
    parser.add_argument("--owner", required=True, help="Owner do repositorio (organizacao ou usuario)")
    parser.add_argument("--repo", required=True, help="Nome do repositorio")
    parser.add_argument("--config", default="backlog_github_project.json", help="Arquivo JSON de configuracao")
    parser.add_argument("--apply", action="store_true", help="Executa alteracoes no GitHub")
    parser.add_argument("--create-project", action="store_true", help="Cria novo Project v2")
    parser.add_argument("--project-title", default="RoadmapBuilder", help="Titulo do novo project")
    parser.add_argument("--project-number", type=int, help="Numero de Project v2 existente")
    parser.add_argument(
        "--project-start-date",
        type=parse_date,
        help="Data estimada de inicio do projeto no formato AAAA-MM-DD. Habilita calculo de prazos.",
    )
    parser.add_argument(
        "--phase",
        action="append",
        metavar="M1",
        help="Cria apenas as issues desta fase (milestone key). Repita para varias. "
        "Sem --phase, cria todas.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(Path(args.config))

    validation_errors = validate_config(cfg)
    if validation_errors:
        raise RuntimeError(format_validation_errors(validation_errors))

    project_start_date = args.project_start_date
    if project_start_date is None and cfg.get("schedule", {}).get("project_start_date"):
        project_start_date = parse_date(cfg["schedule"]["project_start_date"])
    issue_schedule = schedule_issues(cfg, project_start_date)
    due_dates = milestone_due_dates(issue_schedule)

    token = os.getenv("GITHUB_TOKEN", "")
    if args.apply and not token:
        print("ERRO: defina GITHUB_TOKEN para executar com --apply", file=sys.stderr)
        return 2
    if args.apply:
        remote_errors = validate_remote_access(args, token)
        if remote_errors:
            raise RuntimeError(format_validation_errors(remote_errors))

    milestones = ensure_milestones(
        args.owner, args.repo, token, cfg, args.apply, due_dates, phase_keys=args.phase
    )
    ensure_labels(args.owner, args.repo, token, cfg, args.apply, phase_keys=args.phase)
    issue_results = ensure_issues(
        args.owner,
        args.repo,
        token,
        cfg,
        milestones,
        args.apply,
        issue_schedule,
        phase_keys=args.phase,
    )
    titles = [r["title"] for r in issue_results]

    if args.create_project or args.project_number:
        if not args.apply:
            print("[DRY-RUN] Criaria/encontraria project e adicionaria issues.")
        else:
            if args.create_project:
                project_id = create_project(args.owner, args.repo, token, args.project_title)
            else:
                project_id = get_project_id(args.owner, token, args.project_number)
                link_project_to_repository(args.owner, args.repo, token, project_id)
            add_issues_to_project(
                args.owner,
                args.repo,
                token,
                project_id,
                cfg,
                titles,
                args.apply,
                issue_schedule,
            )

    print("Concluido.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
