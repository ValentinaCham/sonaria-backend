import uuid

from sqlalchemy.orm import Session

from app.models.registered_sound import RegisteredSound, SoundCategory


class SoundRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_or_update(
        self,
        user_id: uuid.UUID,
        category: SoundCategory,
        custom_name: str | None = None,
        is_active: bool = True,
        notification_preference: dict | None = None,
    ) -> RegisteredSound:
        existing = (
            self.db.query(RegisteredSound)
            .filter(
                RegisteredSound.user_id == user_id,
                RegisteredSound.category == category,
            )
            .first()
        )
        if existing:
            existing.custom_name = custom_name
            existing.is_active = is_active
            if notification_preference:
                existing.notification_preference = notification_preference
            self.db.commit()
            self.db.refresh(existing)
            return existing

        sound = RegisteredSound(
            user_id=user_id,
            category=category,
            custom_name=custom_name,
            is_active=is_active,
            notification_preference=notification_preference
            or {"vibration": True, "visual": True},
        )
        self.db.add(sound)
        self.db.commit()
        self.db.refresh(sound)
        return sound

    def get_by_user(self, user_id: uuid.UUID) -> list[RegisteredSound]:
        return (
            self.db.query(RegisteredSound)
            .filter(RegisteredSound.user_id == user_id)
            .all()
        )
