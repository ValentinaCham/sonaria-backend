import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: uuid.UUID) -> Conversation:
        conv = Conversation(user_id=user_id)
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def end(self, conversation_id: uuid.UUID) -> Conversation | None:
        conv = self.get_by_id(conversation_id)
        if not conv:
            return None
        conv.is_active = False
        conv.ended_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        return (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

    def get_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.started_at.desc())
            .all()
        )
