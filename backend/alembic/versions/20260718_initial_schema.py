"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_type("sound_category", sa.Enum("doorbell", "alarm", "microwave", "kettle", "dog", "baby_crying", "custom", name="sound_category"))

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("settings", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
    )

    op.create_table(
        "user_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_type", sa.String(50)),
        sa.Column("push_token", sa.String(255)),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
    )

    op.create_table(
        "registered_voices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("voice_signature", sa.Text),
        sa.Column("is_prioritized", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index("idx_registered_voices_user", "registered_voices", ["user_id"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("summary", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )
    op.create_index("idx_conversations_user", "conversations", ["user_id"])
    op.create_index("idx_conversations_active", "conversations", ["is_active"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registered_voice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("registered_voices.id", ondelete="SET NULL")),
        sa.Column("speaker_label", sa.String(50)),
        sa.Column("transcription", sa.Text, nullable=False),
        sa.Column("emotion_detected", sa.String(50)),
        sa.Column("translation", sa.Text),
        sa.Column("spoken_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
    )
    op.create_index("idx_messages_conversation", "conversation_messages", ["conversation_id"])
    op.create_index("idx_messages_spoken_at", "conversation_messages", ["spoken_at"])

    op.create_table(
        "registered_sounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", postgresql.ENUM("doorbell", "alarm", "microwave", "kettle", "dog", "baby_crying", "custom", name="sound_category"), nullable=False),
        sa.Column("custom_name", sa.String(100)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("notification_preference", postgresql.JSONB, server_default=sa.text("'{\"vibration\": true, \"visual\": true}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
    )
    op.create_index("idx_registered_sounds_user", "registered_sounds", ["user_id"])

    op.create_table(
        "sound_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registered_sound_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("registered_sounds.id", ondelete="CASCADE")),
        sa.Column("context_message", sa.Text, nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column("is_notified", sa.Boolean, server_default=sa.text("false")),
    )
    op.create_index("idx_sound_events_user", "sound_events", ["user_id"])
    op.create_index("idx_sound_events_detected", "sound_events", ["detected_at"])


def downgrade() -> None:
    op.drop_table("sound_events")
    op.drop_table("registered_sounds")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("registered_voices")
    op.drop_table("user_devices")
    op.drop_table("users")
    op.drop_type("sound_category")
