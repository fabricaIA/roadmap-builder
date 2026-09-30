"""Histórico de configurações completas por projeto.

Revision ID: d9e31ac78204
Revises: 0ab56cd8fc27
"""

from datetime import datetime, timezone
import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "d9e31ac78204"
down_revision = "0ab56cd8fc27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("author_login", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_from_version", sa.Integer(), nullable=True),
        sa.UniqueConstraint("project_id", "version", name="uq_project_version"),
        sa.CheckConstraint("version >= 1", name="ck_project_version_positive"),
    )
    op.create_index("ix_project_versions_project_id", "project_versions", ["project_id"])
    op.create_index("ix_project_versions_created_by_user_id", "project_versions", ["created_by_user_id"])
    # Adição simples evita recriar projects, referenciada por phase_runs.
    op.add_column("projects", sa.Column("current_version", sa.Integer(), server_default="0", nullable=False))
    with op.batch_alter_table("phase_runs") as batch:
        batch.add_column(sa.Column("project_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_phase_run_project_version", "project_versions", ["project_version_id"], ["id"])
        batch.create_index("ix_phase_runs_project_version_id", ["project_version_id"])

    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT p.*, u.login AS author_login FROM projects p JOIN users u ON u.id = p.created_by_user_id"
    )).mappings().all()
    default_config = None
    versions = sa.table("project_versions",
        sa.column("project_id", sa.Integer()), sa.column("version", sa.Integer()),
        sa.column("snapshot_json", sa.Text()), sa.column("change_note", sa.Text()),
        sa.column("created_by_user_id", sa.Integer()), sa.column("author_login", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for row in rows:
        try:
            config = json.loads(row["config_json"] or "{}")
        except (ValueError, TypeError):
            config = None
        if not isinstance(config, dict) or not all(k in config for k in ("schedule", "milestones", "labels", "issues")):
            if default_config is None:
                path = Path(__file__).resolve().parents[2] / "backlog_github_project.json"
                default_config = json.loads(path.read_text(encoding="utf-8"))
            config = default_config
        snapshot = {
            "owner": row["owner"], "repo": row["repo"], "title": row["title"],
            "project_number": row["project_number"], "project_url": row["project_url"],
            "phase_keys": None, "config": config,
        }
        connection.execute(versions.insert().values(
            project_id=row["id"], version=1, snapshot_json=json.dumps(snapshot, ensure_ascii=False),
            change_note="Configuração inicial capturada na migração; histórico anterior indisponível",
            created_by_user_id=row["created_by_user_id"], author_login=row["author_login"],
            created_at=datetime.now(timezone.utc),
        ))
        connection.execute(sa.text(
            "UPDATE projects SET current_version = 1, config_json = :config WHERE id = :id"
        ), {"id": row["id"], "config": json.dumps(config, ensure_ascii=False)})


def downgrade() -> None:
    with op.batch_alter_table("phase_runs") as batch:
        batch.drop_index("ix_phase_runs_project_version_id")
        batch.drop_constraint("fk_phase_run_project_version", type_="foreignkey")
        batch.drop_column("project_version_id")
    # SQLite recente e PostgreSQL suportam DROP COLUMN sem reconstruir projects.
    op.drop_column("projects", "current_version")
    op.drop_index("ix_project_versions_created_by_user_id", table_name="project_versions")
    op.drop_index("ix_project_versions_project_id", table_name="project_versions")
    op.drop_table("project_versions")
