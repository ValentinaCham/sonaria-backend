import uuid

from sqlalchemy.orm import Session

from app.models.registered_voice import RegisteredVoice


class VoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: uuid.UUID, name: str) -> RegisteredVoice:
        voice = RegisteredVoice(user_id=user_id, name=name)
        self.db.add(voice)
        self.db.commit()
        self.db.refresh(voice)
        return voice

    def get_by_user(self, user_id: uuid.UUID) -> list[RegisteredVoice]:
        return (
            self.db.query(RegisteredVoice)
            .filter(RegisteredVoice.user_id == user_id)
            .all()
        )

    def get_by_id(self, voice_id: uuid.UUID) -> RegisteredVoice | None:
        return self.db.query(RegisteredVoice).filter(RegisteredVoice.id == voice_id).first()

    def update(
        self, voice_id: uuid.UUID, name: str | None = None, is_prioritized: bool | None = None
    ) -> RegisteredVoice | None:
        voice = self.get_by_id(voice_id)
        if not voice:
            return None
        if name is not None:
            voice.name = name
        if is_prioritized is not None:
            voice.is_prioritized = is_prioritized
        self.db.commit()
        self.db.refresh(voice)
        return voice

    def delete(self, voice_id: uuid.UUID) -> bool:
        voice = self.get_by_id(voice_id)
        if not voice:
            return False
        self.db.delete(voice)
        self.db.commit()
        return True
