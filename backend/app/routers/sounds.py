from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.repositories.sound_repository import SoundRepository
from app.schemas.sound import SoundConfigRequest, SoundResponse
from app.services.sound_service import SoundService

router = APIRouter(prefix="/sounds", tags=["sounds"])


@router.get("", response_model=list[SoundResponse])
def list_sounds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SoundService(SoundRepository(db), EventRepository(db))
    return service.list_sounds(current_user.id)


@router.post("/config", response_model=SoundResponse, status_code=201)
def config_sound(
    body: SoundConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SoundService(SoundRepository(db), EventRepository(db))
    return service.config(
        current_user.id,
        category=body.category,
        custom_name=body.custom_name,
        is_active=body.is_active,
        notification_preference=body.notification_preference,
    )
