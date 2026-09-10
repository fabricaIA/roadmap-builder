"""Template do backlog e criação do roadmap (usa o PAT do perfil do usuário)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.deps import require_user
from backend.app.models import User
from backend.app.security import decrypt_pat
from backend.app.services.roadmap import build_roadmap, load_backlog_template

router = APIRouter(prefix="/api", tags=["roadmap"])


class RoadmapPayload(BaseModel):
    owner: str
    repo: str
    apply: bool = False
    create_project: bool = False
    project_title: str = "RoadmapBuilder"
    project_number: int | None = None
    project_start_date: str | None = None
    config: dict[str, Any]


def _user_pat(user: User) -> str:
    if user.pat_encrypted is None:
        raise HTTPException(
            status_code=400,
            detail="Configure seu PAT do GitHub no perfil antes de criar um roadmap.",
        )
    try:
        return decrypt_pat(user.pat_encrypted)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/backlog-template")
def get_backlog_template():
    return load_backlog_template()


@router.post("/build-roadmap")
def post_build_roadmap(
    payload: RoadmapPayload, user: User = Depends(require_user)
):
    token = _user_pat(user)
    return build_roadmap(
        token=token,
        owner=payload.owner,
        repo=payload.repo,
        apply=payload.apply,
        create_project_flag=payload.create_project,
        project_title=payload.project_title,
        project_number=payload.project_number,
        project_start_date=payload.project_start_date,
        cfg=payload.config,
    )
