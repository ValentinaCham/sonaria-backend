from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.repositories.sound_repository import SoundRepository
from app.schemas.event import EventResponse
from app.services.sound_service import SoundService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventResponse])
def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SoundService(SoundRepository(db), EventRepository(db))
    return service.list_events(current_user.id)
