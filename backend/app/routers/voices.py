from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.repositories.voice_repository import VoiceRepository
from app.schemas.voice import (
    RegisterVoiceRequest,
    UpdateVoiceRequest,
    VoiceResponse,
)
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voices", tags=["voices"])


@router.post("/register", response_model=VoiceResponse, status_code=201)
def register_voice(
    body: RegisterVoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = VoiceService(VoiceRepository(db))
    voice = service.register(current_user.id, body.name)
    return voice


@router.get("", response_model=list[VoiceResponse])
def list_voices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = VoiceService(VoiceRepository(db))
    return service.list_by_user(current_user.id)


@router.put("/{voice_id}", response_model=VoiceResponse)
def update_voice(
    voice_id: str,
    body: UpdateVoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = VoiceService(VoiceRepository(db))
    voice = service.update(voice_id, body.name, body.is_prioritized)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    return voice


@router.delete("/{voice_id}", status_code=204)
def delete_voice(
    voice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = VoiceService(VoiceRepository(db))
    deleted = service.delete(voice_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Voice not found")
