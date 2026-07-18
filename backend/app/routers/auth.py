from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security.jwt import create_access_token
from app.security.password import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# UUID estable para el usuario demo (solo desarrollo, sin base de datos).
_DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"


@router.post("/dev-token", response_model=TokenResponse)
def dev_token():
    """
    Devuelve un JWT válido sin necesidad de base de datos.

    Pensado SOLO para desarrollo/demo: permite probar el WebSocket de audio
    (`/ws/audio`) sin tener PostgreSQL configurado. Se deshabilita poniendo
    ALLOW_DEV_LOGIN=false en el entorno.
    """
    if not settings.ALLOW_DEV_LOGIN:
        raise HTTPException(status_code=404, detail="Not found")
    token = create_access_token(_DEMO_USER_ID)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    existing = repo.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = repo.create(body.email, hash_password(body.password))
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_email(body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
