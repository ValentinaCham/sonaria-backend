from pydantic import BaseModel

from app.models.registered_sound import SoundCategory


class SoundConfigRequest(BaseModel):
    category: SoundCategory
    custom_name: str | None = None
    is_active: bool = True
    notification_preference: dict | None = None


class SoundResponse(BaseModel):
    id: str
    category: str
    custom_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}
