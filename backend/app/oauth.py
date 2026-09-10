"""Fluxo OAuth2 Authorization Code do GitHub (apenas para login)."""

from __future__ import annotations

import secrets
import urllib.parse

import httpx

from backend.app.config import get_settings

settings = get_settings()

_AUTHORIZE = "https://github.com/login/oauth/authorize"
_TOKEN = "https://github.com/login/oauth/access_token"
_API_USER = "https://api.github.com/user"
_API_EMAILS = "https://api.github.com/user/emails"


def new_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    params = {
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "scope": settings.oauth_scopes,
        "state": state,
        "allow_signup": "false",
    }
    return f"{_AUTHORIZE}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> str:
    resp = httpx.post(
        _TOKEN,
        headers={"Accept": "application/json"},
        data={
            "client_id": settings.github_oauth_client_id,
            "client_secret": settings.github_oauth_client_secret,
            "code": code,
            "redirect_uri": settings.oauth_redirect_uri,
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise ValueError(
            f"GitHub não retornou access_token: {body.get('error_description') or body}"
        )
    return token


def fetch_github_user(access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = httpx.get(_API_USER, headers=headers, timeout=15)
    resp.raise_for_status()
    user = resp.json()

    if not user.get("email"):
        try:
            emails = httpx.get(_API_EMAILS, headers=headers, timeout=15).json()
            primary = next(
                (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                None,
            )
            if primary:
                user["email"] = primary
        except (httpx.HTTPError, KeyError, TypeError):
            pass
    return user
