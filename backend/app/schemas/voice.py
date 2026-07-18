from pydantic import BaseModel


class RegisterVoiceRequest(BaseModel):
    name: str


class VoiceResponse(BaseModel):
    id: str
    name: str
    is_prioritized: bool

    model_config = {"from_attributes": True}


class UpdateVoiceRequest(BaseModel):
    name: str | None = None
    is_prioritized: bool | None = None
