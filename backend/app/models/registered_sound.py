import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class SoundCategory(str, enum.Enum):
    doorbell = "doorbell"
    alarm = "alarm"
    microwave = "microwave"
    kettle = "kettle"
    dog = "dog"
    baby_crying = "baby_crying"
    custom = "custom"


class RegisteredSound(Base):
    __tablename__ = "registered_sounds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[SoundCategory] = mapped_column(
        Enum(SoundCategory), nullable=False
    )
    custom_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_preference: Mapped[dict] = mapped_column(
        JSONB,
        default={"vibration": True, "visual": True},
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp()
    )

    user = relationship("User", back_populates="registered_sounds")
    events = relationship("SoundEvent", back_populates="registered_sound")


class SoundEvent(Base):
    __tablename__ = "sound_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    registered_sound_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("registered_sounds.id", ondelete="CASCADE"),
    )
    context_message: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp()
    )
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="sound_events")
    registered_sound = relationship("RegisteredSound", back_populates="events")
