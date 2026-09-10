"""Organizações do usuário (tenant) e sincronização de papéis."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.deps import require_user
from backend.app.models import User
from backend.app.security import decrypt_pat
from backend.app.services.orgs import sync_orgs, user_orgs

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


@router.get("")
def list_orgs(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return user_orgs(db, user)


@router.post("/sync")
def sync(user: User = Depends(require_user), db: Session = Depends(get_db)):
    if user.pat_encrypted is None:
        raise HTTPException(
            status_code=400,
            detail="Configure um PAT com escopo `read:org` no perfil para sincronizar.",
        )
    try:
        token = decrypt_pat(user.pat_encrypted)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    synced = sync_orgs(db, user, token)
    return {"synced": synced}
