"""Dependências de autenticação."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.models import OrgMembership, User
from backend.app.security import read_session
from backend.app.services.orgs import membership

settings = get_settings()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    user_id = read_session(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado."
        )
    return user


def _membership_dep(require_admin: bool):
    def dep(
        org: str,
        user: User = Depends(require_user),
        db: Session = Depends(get_db),
    ) -> OrgMembership:
        m = membership(db, user, org)
        if m is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Você não é membro da organização '{org}' (ou falta sincronizar).",
            )
        if require_admin and m.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ação restrita a coordenadores (admins) da organização.",
            )
        return m

    return dep


require_org_member = _membership_dep(require_admin=False)
require_coordinator = _membership_dep(require_admin=True)
