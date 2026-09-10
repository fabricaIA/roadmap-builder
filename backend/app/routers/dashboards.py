"""Dashboards de issues (live): minhas issues e issues da organização."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.deps import require_coordinator, require_org_member, require_user
from backend.app.models import OrgMembership, Project, User
from backend.app.security import decrypt_pat
from backend.app.services.dashboards import aggregate, collect_issues, filter_mine

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


def _pat(user: User) -> str:
    if user.pat_encrypted is None:
        raise HTTPException(
            status_code=400, detail="Configure seu PAT do GitHub no perfil."
        )
    try:
        return decrypt_pat(user.pat_encrypted)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _org_repos(db: Session, org_login: str) -> list[tuple[str, str]]:
    rows = db.execute(
        select(Project.owner, Project.repo).where(Project.owner == org_login)
    ).all()
    return sorted({(o, r) for o, r in rows})


@router.get("/my-issues")
def my_issues(
    org: str,
    _m: OrgMembership = Depends(require_org_member),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repos = _org_repos(db, org)
    issues, errors = collect_issues(_pat(user), repos)
    mine = filter_mine(issues, user.login)
    return {"issues": mine, "agg": aggregate(mine), "errors": errors, "repos": len(repos)}


@router.get("/org-issues")
def org_issues(
    org: str,
    _m: OrgMembership = Depends(require_org_member),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repos = _org_repos(db, org)
    issues, errors = collect_issues(_pat(user), repos)
    return {"issues": issues, "agg": aggregate(issues), "errors": errors, "repos": len(repos)}


@router.get("/devs")
def devs(
    org: str,
    _m: OrgMembership = Depends(require_coordinator),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repos = _org_repos(db, org)
    issues, errors = collect_issues(_pat(user), repos)

    per_dev: dict[str, dict] = {}
    for i in issues:
        who = set(i["assignees"]) or ({i["author"]} if i["author"] else set())
        for d in who:
            row = per_dev.setdefault(
                d, {"dev": d, "open": 0, "closed": 0, "phases": {}}
            )
            key = "open" if i["state"] == "OPEN" else "closed"
            row[key] += 1
            ph = row["phases"].setdefault(i["phase"], {"open": 0, "closed": 0})
            ph[key] += 1

    return {
        "devs": sorted(per_dev.values(), key=lambda r: r["dev"] or ""),
        "errors": errors,
        "repos": len(repos),
    }
