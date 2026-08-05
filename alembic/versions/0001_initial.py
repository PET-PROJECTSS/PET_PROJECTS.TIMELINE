"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-02

"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _existing_tables()
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("role", sa.String(length=10), nullable=False),
            sa.UniqueConstraint("username"),
        )
    if "roadmaps" not in tables:
        op.create_table(
            "roadmaps",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "sessions" not in tables:
        op.create_table(
            "sessions",
            sa.Column("token", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("expires_at", sa.String(length=64), nullable=True),
        )
    if "login_attempts" not in tables:
        op.create_table(
            "login_attempts",
            sa.Column("key", sa.String(length=64), primary_key=True),
            sa.Column("count", sa.Integer(), nullable=False),
            sa.Column("window_start", sa.Float(), nullable=False),
            sa.Column("blocked_until", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("sessions")
    op.drop_table("roadmaps")
    op.drop_table("users")
