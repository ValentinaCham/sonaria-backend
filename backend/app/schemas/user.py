from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Convertir UUID a str para serialización JSON
        if hasattr(obj, "id") and not isinstance(obj.id, str):
            obj = type(obj)(
                id=str(obj.id),
                email=obj.email,
            )
        return super().model_validate(obj, *args, **kwargs)
