from pydantic import BaseModel


class SoundConfigRequest(BaseModel):
    category: str
    custom_name: str | None = None
    is_active: bool = True
    notification_preference: dict | None = None


class SoundResponse(BaseModel):
    id: str
    category: str
    custom_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}
