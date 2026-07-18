import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    registered_voice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("registered_voices.id", ondelete="SET NULL"),
    )
    speaker_label: Mapped[str | None] = mapped_column(String(50))
    transcription: Mapped[str] = mapped_column(Text, nullable=False)
    emotion_detected: Mapped[str | None] = mapped_column(String(50))
    translation: Mapped[str | None] = mapped_column(Text)
    spoken_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp()
    )

    conversation = relationship("Conversation", back_populates="messages")
    registered_voice = relationship("RegisteredVoice", back_populates="messages")
