import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    registered_voices = relationship("RegisteredVoice", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    registered_sounds = relationship("RegisteredSound", back_populates="user")
    sound_events = relationship("SoundEvent", back_populates="user")
    devices = relationship("UserDevice", back_populates="user")


class UserDevice(Base):
    __tablename__ = "user_devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    device_type: Mapped[str | None] = mapped_column(String(50))
    push_token: Mapped[str | None] = mapped_column(String(255))
    registered_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp()
    )

    user = relationship("User", back_populates="devices")
