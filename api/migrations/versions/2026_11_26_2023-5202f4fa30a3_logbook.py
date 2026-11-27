"""logbook

Revision ID: 5202f4fa30a3
Revises: 59eb015ba1ea
Create Date: 2026-11-26 20:23:31.807759

Migration order (docs/API.md "Migration order"): this one went in before role
A's (``refresh_tokens``, ``file_permissions``), whose ``down_revision`` is this
revision, ``5202f4fa30a3``. ``alembic heads`` must print one line; with two heads
the API container fails at startup.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5202f4fa30a3"
down_revision: str | Sequence[str] | None = "59eb015ba1ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "logbook",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_logbook")),
    )
    op.create_index(op.f("ix_logbook_ts"), "logbook", ["ts"], unique=False)
    op.create_index(
        "ix_logbook_username_action_ts", "logbook", ["username", "action", "ts"], unique=False
    )
    op.create_index("ix_logbook_ip_action_ts", "logbook", ["ip", "action", "ts"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_logbook_ip_action_ts", table_name="logbook")
    op.drop_index("ix_logbook_username_action_ts", table_name="logbook")
    op.drop_index(op.f("ix_logbook_ts"), table_name="logbook")
    op.drop_table("logbook")
