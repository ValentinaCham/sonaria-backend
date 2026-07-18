import uuid

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.voice_repository import VoiceRepository


class ConversationService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        voice_repo: VoiceRepository,
    ):
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.voice_repo = voice_repo

    def start(self, user_id: uuid.UUID):
        return self.conversation_repo.create(user_id)

    def end(self, conversation_id: uuid.UUID):
        return self.conversation_repo.end(conversation_id)

    def get_history(self, user_id: uuid.UUID):
        return self.conversation_repo.get_by_user(user_id)

    def get_detail(self, conversation_id: uuid.UUID):
        conv = self.conversation_repo.get_by_id(conversation_id)
        if not conv:
            return None
        messages = self.message_repo.get_by_conversation(conversation_id)
        conv.messages = messages
        return conv

    def add_message(
        self,
        conversation_id: uuid.UUID,
        transcription: str,
        speaker_label: str | None = None,
    ):
        return self.message_repo.create(
            conversation_id=conversation_id,
            transcription=transcription,
            speaker_label=speaker_label,
        )

    def process_audio_turn(self, conversation_id: uuid.UUID, segments: list[dict]):
        items = segments
        if len(items) == 1 and isinstance(items[0], dict) and "segments" in items[0]:
            items = items[0].get("segments", []) or []

        for segment in items:
            if not isinstance(segment, dict):
                continue
            text = str(segment.get("text", "") or "").strip()
            if not text:
                continue
            self.add_message(
                conversation_id=conversation_id,
                transcription=text,
                speaker_label=segment.get("speaker_label"),
            )
