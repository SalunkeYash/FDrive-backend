"""add access_requests table

Revision ID: f1a2b3c4d5e6
Revises: e9a1b2c3d4f5
Create Date: 2026-09-21 17:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e9a1b2c3d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    access_request_status = postgresql.ENUM(
        "pending",
        "approved",
        "denied",
        name="access_request_status",
        create_type=False,
    )
    access_request_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "access_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column(
            "requested_role",
            postgresql.ENUM(
                "viewer",
                "editor",
                name="share_role",
                create_type=False,
            ),
            server_default="viewer",
            nullable=False,
        ),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "denied",
                name="access_request_status",
                create_type=False,
            ),
            server_default="pending",
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_access_requests_owner_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_access_requests_requester_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_requests")),
    )
    op.create_index(
        op.f("ix_access_requests_owner_id"), "access_requests", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_access_requests_requester_id"),
        "access_requests",
        ["requester_id"],
        unique=False,
    )
    op.create_index(
        "ix_access_requests_resource",
        "access_requests",
        ["resource_type", "resource_id"],
        unique=False,
    )
    op.create_index(
        "ix_access_requests_owner_status",
        "access_requests",
        ["owner_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_access_requests_owner_status", table_name="access_requests")
    op.drop_index("ix_access_requests_resource", table_name="access_requests")
    op.drop_index(op.f("ix_access_requests_requester_id"), table_name="access_requests")
    op.drop_index(op.f("ix_access_requests_owner_id"), table_name="access_requests")
    op.drop_table("access_requests")
    op.execute("DROP TYPE IF EXISTS access_request_status")
