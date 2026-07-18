import uuid

from app.repositories.event_repository import EventRepository
from app.repositories.sound_repository import SoundRepository


class SoundService:
    def __init__(
        self,
        sound_repo: SoundRepository,
        event_repo: EventRepository,
    ):
        self.sound_repo = sound_repo
        self.event_repo = event_repo

    def config(self, user_id: uuid.UUID, category: str, **kwargs):
        from app.models.registered_sound import SoundCategory
        return self.sound_repo.create_or_update(
            user_id=user_id,
            category=SoundCategory(category),
            **kwargs,
        )

    def list_sounds(self, user_id: uuid.UUID):
        return self.sound_repo.get_by_user(user_id)

    def list_events(self, user_id: uuid.UUID):
        return self.event_repo.get_by_user(user_id)

    def register_event(
        self,
        user_id: uuid.UUID,
        context_message: str,
        registered_sound_id: uuid.UUID | None = None,
    ):
        return self.event_repo.create(user_id, context_message, registered_sound_id)
