"""Card de perfil: PAT (write-only) + configurações gerais."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.deps import require_user
from backend.app.github import token_identity
from backend.app.models import User
from backend.app.security import decrypt_pat, encrypt_pat

router = APIRouter(prefix="/api/profile", tags=["profile"])

# Chaves de configuração aceitas (o resto é ignorado).
_ALLOWED_CONFIG_KEYS = {
    "project_title_pattern",  # ex.: "{owner}/{repo} - Roadmap"
    "default_project_start_date",  # "AAAA-MM-DD"
    "date_field_start",  # nome do campo de data "início" no Project
    "date_field_end",
}


class ProfileUpdate(BaseModel):
    pat: str | None = None
    config: dict | None = None


def _load_config(user: User) -> dict:
    try:
        return json.loads(user.config_json or "{}")
    except json.JSONDecodeError:
        return {}


def _profile_payload(user: User) -> dict:
    return {"config": _load_config(user), "has_pat": user.pat_encrypted is not None}


@router.get("")
def get_profile(user: User = Depends(require_user)):
    return _profile_payload(user)


@router.put("")
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    result: dict = {}

    if body.pat is not None:
        pat = body.pat.strip()
        if pat == "":
            user.pat_encrypted = None  # remover PAT
        else:
            try:
                ident = token_identity(pat)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            user.pat_encrypted = encrypt_pat(pat)
            result["pat_login"] = ident.login
            result["pat_scopes"] = ident.scopes

    if body.config is not None:
        current = _load_config(user)
        for key, value in body.config.items():
            if key in _ALLOWED_CONFIG_KEYS:
                current[key] = value
        user.config_json = json.dumps(current)

    db.commit()
    db.refresh(user)
    return {**_profile_payload(user), **result}


@router.get("/pat/test")
def test_pat(user: User = Depends(require_user)):
    if user.pat_encrypted is None:
        raise HTTPException(status_code=404, detail="Nenhum PAT configurado.")
    try:
        ident = token_identity(decrypt_pat(user.pat_encrypted))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"login": ident.login, "scopes": ident.scopes}
