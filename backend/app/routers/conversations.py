from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.voice_repository import VoiceRepository
from app.schemas.conversation import (
    ConversationDetailResponse,
    EndConversationResponse,
    StartConversationResponse,
)
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/start", response_model=StartConversationResponse, status_code=201)
def start_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ConversationService(
        ConversationRepository(db),
        MessageRepository(db),
        VoiceRepository(db),
    )
    conv = service.start(current_user.id)
    return conv


@router.post("/{conversation_id}/end", response_model=EndConversationResponse)
def end_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ConversationService(
        ConversationRepository(db),
        MessageRepository(db),
        VoiceRepository(db),
    )
    conv = service.end(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.get("/history", response_model=list[StartConversationResponse])
def conversation_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ConversationService(
        ConversationRepository(db),
        MessageRepository(db),
        VoiceRepository(db),
    )
    return service.get_history(current_user.id)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def conversation_detail(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ConversationService(
        ConversationRepository(db),
        MessageRepository(db),
        VoiceRepository(db),
    )
    conv = service.get_detail(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv
