"""add stateful agent workflow tables

Revision ID: 20260914_03
Revises: 20260730_02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260914_03"
down_revision: str | None = "20260730_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_threads_owner_id", "agent_threads", ["owner_id"])
    op.create_index("ix_agent_threads_status", "agent_threads", ["status"])
    op.create_table(
        "agent_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "estimated_cost_usd",
            sa.String(length=30),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["agent_threads.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_turns_thread_id", "agent_turns", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_turns_thread_id", table_name="agent_turns")
    op.drop_table("agent_turns")
    op.drop_index("ix_agent_threads_status", table_name="agent_threads")
    op.drop_index("ix_agent_threads_owner_id", table_name="agent_threads")
    op.drop_table("agent_threads")
