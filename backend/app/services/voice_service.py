import uuid

from app.repositories.voice_repository import VoiceRepository


class VoiceService:
    def __init__(self, repo: VoiceRepository):
        self.repo = repo

    def register(self, user_id: uuid.UUID, name: str):
        return self.repo.create(user_id, name)

    def list_by_user(self, user_id: uuid.UUID):
        return self.repo.get_by_user(user_id)

    def update(self, voice_id: uuid.UUID, name: str | None = None, is_prioritized: bool | None = None):
        return self.repo.update(voice_id, name, is_prioritized)

    def delete(self, voice_id: uuid.UUID) -> bool:
        return self.repo.delete(voice_id)
