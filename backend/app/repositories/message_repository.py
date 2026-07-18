import uuid

from sqlalchemy.orm import Session

from app.models.conversation_message import ConversationMessage


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        conversation_id: uuid.UUID,
        transcription: str,
        speaker_label: str | None = None,
        registered_voice_id: uuid.UUID | None = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            registered_voice_id=registered_voice_id,
            speaker_label=speaker_label,
            transcription=transcription,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_by_conversation(self, conversation_id: uuid.UUID) -> list[ConversationMessage]:
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.spoken_at)
            .all()
        )
