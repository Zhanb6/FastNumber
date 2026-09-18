"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

participant_status = postgresql.ENUM(
    "ACTIVE", "DISQUALIFIED", "DELETED", name="participant_status", create_type=False
)
draw_status = postgresql.ENUM(
    "DRAFT", "PENDING_CONFIRMATION", "COMPLETED", "CANCELLED", name="draw_status", create_type=False
)
draw_result_status = postgresql.ENUM(
    "SELECTED", "CONFIRMED", "REJECTED", name="draw_result_status", create_type=False
)
live_state_value = postgresql.ENUM(
    "IDLE",
    "COUNTDOWN",
    "DRAWING",
    "WINNER",
    "COMPLETED",
    name="live_state_value",
    create_type=False,
)
ENUMS = (participant_status, draw_status, draw_result_status, live_state_value)


def upgrade() -> None:
    bind = op.get_bind()
    for e in ENUMS:
        e.create(bind, checkfirst=True)

    op.create_table(
        "participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(60), nullable=False),
        sa.Column("last_name", sa.String(60), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(254)),
        sa.Column("company", sa.String(120)),
        sa.Column("device_token", postgresql.UUID(as_uuid=True)),
        sa.Column("status", participant_status, nullable=False, server_default="ACTIVE"),
        sa.Column("status_reason", sa.Text()),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("number", name="uq_participants_number"),
    )
    op.create_index("ix_participants_device_token", "participants", ["device_token"])
    op.create_index("ix_participants_status", "participants", ["status"])
    op.create_index("ix_participants_created_at", "participants", ["created_at"])

    op.create_table(
        "number_counter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("next_value", sa.Integer(), nullable=False),
    )

    op.create_table(
        "draws",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("prize", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", draw_status, nullable=False, server_default="DRAFT"),
        sa.Column("exclude_previous_winners", sa.Boolean()),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("winner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_draws_position", "draws", ["position"])
    op.create_index("ix_draws_status", "draws", ["status"])

    op.create_table(
        "draw_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "draw_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("draws.id"), nullable=False
        ),
        sa.Column(
            "participant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.id"),
            nullable=False,
        ),
        sa.Column("status", draw_result_status, nullable=False),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("eligible_hash", sa.CHAR(64), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_draw_results_draw_id", "draw_results", ["draw_id"])
    op.create_index("ix_draw_results_participant_id", "draw_results", ["participant_id"])
    op.create_index(
        "uq_draw_results_active_per_draw",
        "draw_results",
        ["draw_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('SELECTED', 'CONFIRMED')"),
    )

    op.create_table(
        "live_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", live_state_value, nullable=False, server_default="IDLE"),
        sa.Column(
            "draw_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("draws.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("login", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("draw_id", postgresql.UUID(as_uuid=True)),
        sa.Column("admin_login", sa.String(64)),
        sa.Column("ip", postgresql.INET()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_participant_id", "audit_log", ["participant_id"])
    op.create_index("ix_audit_log_draw_id", "audit_log", ["draw_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # Append-only audit log: forbid UPDATE / DELETE at the database level.
    op.execute(
        """
        CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only (% not allowed)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
        """
    )

    # Singleton rows. The number counter value is initialised by the application
    # startup step from settings/env (START_NUMBER), not here.
    op.execute("INSERT INTO live_state (id, state) VALUES (1, 'IDLE') ON CONFLICT DO NOTHING")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable()")
    op.drop_table("audit_log")
    op.drop_table("settings")
    op.drop_table("admins")
    op.drop_table("live_state")
    op.drop_table("draw_results")
    op.drop_table("draws")
    op.drop_table("number_counter")
    op.drop_table("participants")
    bind = op.get_bind()
    for e in ENUMS:
        e.drop(bind, checkfirst=True)
