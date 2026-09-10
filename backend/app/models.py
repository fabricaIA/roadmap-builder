"""Modelos ORM.

PR1: `User`. PR2: `Project`. `Organization`, `OrgMembership` e `PhaseRun`
entram nos PRs seguintes (ver plano).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    login: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # PAT do GitHub cifrado (Fernet). Nulo até o usuário configurar no perfil.
    pat_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configurações gerais do usuário (title pattern, data padrão, nomes de campos).
    # Guardado como JSON serializado em texto para portabilidade SQLite/Postgres.
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Project(Base):
    """Registro de um roadmap gerenciado pelo app (criado ou importado).

    É a fonte de verdade da lista pós-login e dos dashboards; os números
    (contagens de issues, progresso por fase) são buscados live no GitHub.
    """

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("created_by_user_id", "owner", "repo", name="uq_project_user_repo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    owner: Mapped[str] = mapped_column(String(255), index=True)
    repo: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512), default="")
    project_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # "created" (feito pelo wizard) ou "imported".
    source: Mapped[str] = mapped_column(String(16), default="created")
    # Preenchido no PR4 (multi-tenant); nulo = conta pessoal.
    org_login: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Config do roadmap (milestones/labels/issues) informada no wizard.
    # Usada para aplicar issues por fase; vazio => cai no template do repo.
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class PhaseRun(Base):
    """Auditoria de cada aplicação de fase (base para os dashboards do PR4)."""

    __tablename__ = "phase_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    phase_key: Mapped[str] = mapped_column(String(32))
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
