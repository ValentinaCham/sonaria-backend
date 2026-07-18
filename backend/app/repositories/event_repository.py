import uuid

from sqlalchemy.orm import Session

from app.models.registered_sound import SoundEvent


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: uuid.UUID,
        context_message: str,
        registered_sound_id: uuid.UUID | None = None,
    ) -> SoundEvent:
        event = SoundEvent(
            user_id=user_id,
            registered_sound_id=registered_sound_id,
            context_message=context_message,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_by_user(
        self, user_id: uuid.UUID, limit: int = 50
    ) -> list[SoundEvent]:
        return (
            self.db.query(SoundEvent)
            .filter(SoundEvent.user_id == user_id)
            .order_by(SoundEvent.detected_at.desc())
            .limit(limit)
            .all()
        )
