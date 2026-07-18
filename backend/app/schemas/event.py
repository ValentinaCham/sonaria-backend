from datetime import datetime

from pydantic import BaseModel


class EventResponse(BaseModel):
    id: str
    context_message: str
    detected_at: datetime
    is_notified: bool

    model_config = {"from_attributes": True}
