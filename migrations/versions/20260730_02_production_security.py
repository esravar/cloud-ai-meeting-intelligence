"""Add authentication, encrypted fields, jobs, and embedding metadata.

Revision ID: 20260730_02
Revises: 20260727_01
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260730_02"
down_revision = "20260727_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.add_column(
        "meetings",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column("transcript_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "source_type",
            sa.String(length=20),
            server_default="text",
            nullable=False,
        ),
    )
    op.add_column("meetings", sa.Column("source_name", sa.Text()))
    op.add_column(
        "meetings",
        sa.Column(
            "embedding_model",
            sa.String(length=200),
            server_default="openai/text-embedding-3-small",
            nullable=False,
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "embedding_dimensions",
            sa.Integer(),
            server_default="1536",
            nullable=False,
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_meetings_owner_id",
        "meetings",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_meetings_owner_id", "meetings", ["owner_id"])
    op.add_column(
        "meeting_chunks",
        sa.Column("content_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_meeting_chunks_meeting_index",
        "meeting_chunks",
        ["meeting_id", "chunk_index"],
    )

    # This database has no production data yet. For a non-empty database,
    # plaintext rows must be encrypted by a dedicated data migration first.
    op.drop_column("meeting_chunks", "content")
    op.drop_column("meetings", "transcript")
    op.alter_column("meetings", "owner_id", nullable=False)
    op.alter_column("meetings", "transcript_encrypted", nullable=False)
    op.alter_column("meeting_chunks", "content_encrypted", nullable=False)

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True)),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_jobs_owner_id", "processing_jobs", ["owner_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.add_column("meetings", sa.Column("transcript", sa.Text()))
    op.add_column("meeting_chunks", sa.Column("content", sa.Text()))
    op.drop_constraint(
        "uq_meeting_chunks_meeting_index", "meeting_chunks", type_="unique"
    )
    op.drop_column("meeting_chunks", "content_encrypted")
    op.drop_index("ix_meetings_owner_id", table_name="meetings")
    op.drop_constraint("fk_meetings_owner_id", "meetings", type_="foreignkey")
    for column in (
        "updated_at",
        "embedding_dimensions",
        "embedding_model",
        "source_name",
        "source_type",
        "transcript_encrypted",
        "owner_id",
    ):
        op.drop_column("meetings", column)
    op.drop_table("users")
