"""add name trigram search indexes

Revision ID: e9a1b2c3d4f5
Revises: d8f1a2b3c4e5
Create Date: 2026-09-16 10:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e9a1b2c3d4f5"
down_revision: Union[str, None] = "d8f1a2b3c4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lightweight substring search for ILIKE '%q%' — no external search engine.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_files_name_trgm
        ON files
        USING gin (name gin_trgm_ops)
        WHERE is_trashed = false AND status = 'ready'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_folders_name_trgm
        ON folders
        USING gin (name gin_trgm_ops)
        WHERE is_trashed = false
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_folders_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_files_name_trgm")
    # Leave pg_trgm installed — other DBs/apps may use it.
