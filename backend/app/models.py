"""Modelos ORM.

PR1 introduz apenas `User`. `Project`, `Organization`, `OrgMembership` e
`PhaseRun` entram nos PRs seguintes (ver plano).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
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
