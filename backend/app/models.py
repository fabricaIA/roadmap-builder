"""Modelos ORM.

Usuários, projetos, versões de configuração, aplicações de fases e organizações.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    current_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Config do roadmap (milestones/labels/issues) informada no wizard.
    # Cópia efetiva da versão atual, usada para aplicar issues por fase.
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class ProjectVersion(Base):
    """Snapshot imutável de toda a configuração local de um projeto."""

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_version"),
        CheckConstraint("version >= 1", name="ck_project_version_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[str] = mapped_column(Text)
    change_note: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    author_login: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    restored_from_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PhaseRun(Base):
    """Auditoria de cada aplicação de fase (base para os dashboards do PR4)."""

    __tablename__ = "phase_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True, index=True
    )
    phase_key: Mapped[str] = mapped_column(String(32))
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Organization(Base):
    """Tenant = organização do GitHub."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_org_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    login: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)


class OrgMembership(Base):
    """Vínculo usuário↔org com o papel derivado do GitHub.

    role "admin" → coordenador; "member" → dev.
    """

    __tablename__ = "org_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    @property
    def is_coordinator(self) -> bool:
        return self.role == "admin"
