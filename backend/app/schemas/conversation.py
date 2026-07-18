from datetime import datetime

from pydantic import BaseModel


class StartConversationResponse(BaseModel):
    id: str
    started_at: datetime

    model_config = {"from_attributes": True}


class EndConversationResponse(BaseModel):
    id: str
    ended_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    speaker_label: str | None
    transcription: str
    spoken_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    id: str
    title: str | None
    summary: str | None
    started_at: datetime
    ended_at: datetime | None
    is_active: bool
    messages: list[MessageResponse]

    model_config = {"from_attributes": True}
