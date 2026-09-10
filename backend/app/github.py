"""Utilitários de acesso ao GitHub compartilhados pelos routers.

- `humanize_error`: traduz erros de baixo nível (do roadmap_builder ou da API)
  para mensagens acionáveis (era `humanize_error` em backend/api/api.py).
- `token_identity`: valida um PAT e devolve login + escopos (usado no card de
  perfil e na pré-checagem de escopo).
- `missing_project_scope`: pré-checa escopo de Projects V2 antes de escrever.
"""

from __future__ import annotations

import httpx

GITHUB_API = "https://api.github.com"


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
        return (
            "Limite de requisições da API do GitHub atingido. "
            "Aguarde alguns minutos e tente novamente."
        )
    if "not found" in low or "nao encontrado" in low or "não encontrado" in low:
        return (
            "Repositório não encontrado ou o token não tem acesso a ele. "
            "Confira owner, repo e as permissões do token."
        )
    return text


class TokenIdentity:
    def __init__(self, login: str, scopes: list[str]):
        self.login = login
        self.scopes = scopes


def token_identity(token: str) -> TokenIdentity:
    """Valida o PAT. Levanta ValueError com mensagem amigável se inválido."""
    try:
        resp = httpx.get(
            f"{GITHUB_API}/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"Falha ao contatar a API do GitHub: {exc}") from exc

    if resp.status_code == 401:
        raise ValueError("Token do GitHub inválido ou expirado.")
    if resp.status_code >= 400:
        raise ValueError(humanize_error(f"HTTP {resp.status_code}: {resp.text}"))

    login = resp.json().get("login", "")
    raw_scopes = resp.headers.get("X-OAuth-Scopes", "")
    scopes = [s.strip() for s in raw_scopes.split(",") if s.strip()]
    return TokenIdentity(login=login, scopes=scopes)


def missing_project_scope(token: str, need_write: bool) -> str | None:
    """Mensagem se faltar escopo de Projects V2; None se ok ou indeterminável
    (fine-grained PAT não expõe X-OAuth-Scopes)."""
    try:
        ident = token_identity(token)
    except ValueError as exc:
        return str(exc)

    if not ident.scopes:
        return None  # provavelmente fine-grained PAT — não dá para pré-validar
    scopes = set(ident.scopes)
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
