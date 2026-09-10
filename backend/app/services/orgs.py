"""Sincronização de organizações e papéis a partir do GitHub."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import OrgMembership, Organization, User

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _get(token: str, path: str) -> httpx.Response:
    return httpx.get(
        f"{GITHUB_API}{path}",
        headers={**_HEADERS, "Authorization": f"Bearer {token}"},
        timeout=15,
    )


def sync_orgs(db: Session, user: User, token: str) -> list[dict]:
    """Atualiza Organization/OrgMembership do usuário. Best-effort: se o token
    não tem `read:org`, retorna [] sem falhar."""
    try:
        resp = _get(token, "/user/orgs?per_page=100")
    except httpx.HTTPError as exc:
        logger.warning("Falha ao listar orgs: %s", exc)
        return []
    if resp.status_code != 200:
        logger.info("GET /user/orgs -> %s (provável falta de read:org)", resp.status_code)
        return []

    out = []
    for gh_org in resp.json():
        org = db.execute(
            select(Organization).where(Organization.github_org_id == gh_org["id"])
        ).scalar_one_or_none()
        if org is None:
            org = Organization(github_org_id=gh_org["id"])
            db.add(org)
        org.login = gh_org["login"]
        org.name = gh_org.get("name") or org.name
        org.avatar_url = gh_org.get("avatar_url")
        db.flush()

        role = "member"
        try:
            m = _get(token, f"/orgs/{org.login}/memberships/{user.login}")
            if m.status_code == 200:
                role = m.json().get("role", "member")
        except httpx.HTTPError:
            pass

        membership = db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id, OrgMembership.org_id == org.id
            )
        ).scalar_one_or_none()
        if membership is None:
            membership = OrgMembership(user_id=user.id, org_id=org.id)
            db.add(membership)
        membership.role = role
        out.append({"login": org.login, "name": org.name, "role": role})

    db.commit()
    return out


def user_orgs(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(OrgMembership, Organization)
        .join(Organization, OrgMembership.org_id == Organization.id)
        .where(OrgMembership.user_id == user.id)
        .order_by(Organization.login)
    ).all()
    orgs = [
        {
            "login": org.login,
            "name": org.name,
            "avatar_url": org.avatar_url,
            "role": m.role,
            "is_coordinator": m.role == "admin",
            "personal": False,
        }
        for m, org in rows
    ]
    # "Tenant pessoal": permite ao usuário ver seus projetos de conta pessoal
    # de forma consolidada, sem depender de uma organização do GitHub.
    personal = {
        "login": user.login,
        "name": (user.name or user.login) + " (conta pessoal)",
        "avatar_url": user.avatar_url,
        "role": "admin",
        "is_coordinator": True,
        "personal": True,
    }
    return [personal, *orgs]


def membership(db: Session, user: User, org_login: str):
    if org_login == user.login:
        # tenant pessoal — coordenador da própria conta
        return OrgMembership(user_id=user.id, org_id=0, role="admin")
    return db.execute(
        select(OrgMembership)
        .join(Organization, OrgMembership.org_id == Organization.id)
        .where(OrgMembership.user_id == user.id, Organization.login == org_login)
    ).scalar_one_or_none()
