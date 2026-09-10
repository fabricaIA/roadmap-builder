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


def _org_projects(db: Session, org_login: str) -> list[dict]:
    """Projetos (owner/repo/nº do Project) daquele tenant, de qualquer usuário."""
    rows = db.execute(
        select(Project.owner, Project.repo, Project.project_number).where(
            (Project.org_login == org_login) | (Project.owner == org_login)
        )
    ).all()
    dedup: dict[tuple[str, str], int | None] = {}
    for o, r, n in rows:
        dedup.setdefault((o, r), n)
        if n and not dedup[(o, r)]:
            dedup[(o, r)] = n
    return [
        {"owner": o, "repo": r, "project_number": n}
        for (o, r), n in sorted(dedup.items())
    ]


@router.get("/my-issues")
def my_issues(
    org: str,
    _m: OrgMembership = Depends(require_org_member),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    projects = _org_projects(db, org)
    issues, errors, status_order = collect_issues(_pat(user), projects)
    mine = filter_mine(issues, user.login)
    return {
        "issues": mine,
        "agg": aggregate(mine),
        "errors": errors,
        "repos": len(projects),
        "status_order": status_order,
    }


@router.get("/org-issues")
def org_issues(
    org: str,
    _m: OrgMembership = Depends(require_org_member),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    projects = _org_projects(db, org)
    issues, errors, status_order = collect_issues(_pat(user), projects)
    return {
        "issues": issues,
        "agg": aggregate(issues),
        "errors": errors,
        "repos": len(projects),
        "status_order": status_order,
    }


@router.get("/devs")
def devs(
    org: str,
    _m: OrgMembership = Depends(require_coordinator),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    projects = _org_projects(db, org)
    issues, errors, _status_order = collect_issues(_pat(user), projects)

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
        "repos": len(projects),
    }
