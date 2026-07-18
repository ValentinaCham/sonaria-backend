"""
audio_stream.py
───────────────
WebSocket /ws/audio — Reconocimiento de voz en tiempo real con diarización.

Protocolo cliente ↔ servidor:

  CONEXIÓN:
    ws://host/ws/audio?token=<JWT>&max_speakers=<N>&sample_rate=<Hz>

    Parámetros query (todos opcionales):
      token        JWT de autenticación (alternativa a header Authorization)
      max_speakers Número máximo de hablantes esperados (default: 5)
      sample_rate  Hz del audio enviado (default: 16000)

  CLIENTE → SERVIDOR:
    Bytes crudos: audio PCM 16kHz mono int16 (sin cabecera WAV)
    ─ o ─
    JSON de control: { "action": "ping" }

  SERVIDOR → CLIENTE:
    JSON con transcripciones:
    {
      "type": "connected" | "partial" | "final" | "revision" | "error" | "pong",
      "speaker": "Persona 1",       # etiqueta amigable
      "speaker_label": "A",         # etiqueta cruda AssemblyAI
      "text": "...",
      "is_final": true,
      "segments": [                 # en "final" y "revision"
        { "speaker": "...", "speaker_label": "...", "text": "..." }
      ],
      "timestamp_ms": 1234567890
    }
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import settings
from app.dependencies import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.voice_repository import VoiceRepository
from app.security.jwt import decode_access_token
from app.services.ai.assemblyai_service import AssemblyAIStreamingService
from app.services.audio.speech_enhancer import SpeechEnhancer
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────────────────────
# Endpoint WebSocket
# ──────────────────────────────────────────────────────────────

@router.websocket("/ws/audio")
async def audio_stream(
    websocket: WebSocket,
    token: str | None = Query(default=None, description="JWT opcional vía query param"),
    conversation_id: str | None = Query(default=None, description="ID de conversación opcional"),
    max_speakers: int = Query(default=5, ge=1, le=10, description="Máximo de hablantes"),
    sample_rate: int = Query(default=16000, description="Sample rate del audio en Hz"),
    clean: bool | None = Query(default=None, description="Activar limpieza de ruido (por defecto según config)"),
):
    """
    WebSocket de reconocimiento de voz multi-persona en tiempo real.

    El cliente envía chunks de audio PCM y recibe transcripciones
    con identificación de hablante en tiempo real.
    """
    await websocket.accept()
    logger.info(
        "Nueva conexión WebSocket /ws/audio | max_speakers=%d | sample_rate=%d",
        max_speakers, sample_rate,
    )

    token_value = token
    if not token_value:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token_value = auth_header.split(" ", 1)[1].strip()

    if not token_value:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    payload = decode_access_token(token_value)
    if payload is None:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return

    effective_conversation_id: uuid.UUID | None = None
    if conversation_id:
        try:
            effective_conversation_id = uuid.UUID(conversation_id)
        except ValueError:
            logger.warning("conversation_id inválido en /ws/audio: %s", conversation_id)

    loop = asyncio.get_event_loop()
    svc: AssemblyAIStreamingService | None = None

    # ── Limpiador de audio (denoise + VAD) antes de transcribir ──
    cleaning_enabled = settings.ENABLE_AUDIO_CLEANING if clean is None else clean
    enhancer: SpeechEnhancer | None = None
    if cleaning_enabled:
        try:
            enhancer = SpeechEnhancer(
                sample_rate=sample_rate,
                strength=settings.NOISE_REDUCTION_STRENGTH,
                enable_denoise=True,
                enable_highpass=settings.ENABLE_HIGHPASS,
                enable_vad_gate=settings.ENABLE_VAD_GATE,
            )
            logger.info("Limpieza de audio ACTIVADA (denoise+VAD) para esta conexión")
        except Exception as exc:
            logger.warning("No se pudo iniciar la limpieza de audio: %s", exc)
            enhancer = None

    async def send_json_safe(data: dict):
        """Envía JSON al cliente, ignora si el WebSocket ya cerró."""
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    async def on_transcript(event: dict):
        """Callback que recibe eventos de AssemblyAI y los reenvía al cliente."""
        if event.get("type") == "final" and effective_conversation_id is not None:
            try:
                db = next(get_db())
                service = ConversationService(
                    ConversationRepository(db),
                    MessageRepository(db),
                    VoiceRepository(db),
                )
                service.process_audio_turn(effective_conversation_id, [event])
            except Exception as exc:
                logger.warning("No se pudo guardar turno de audio: %s", exc)
        await send_json_safe(event)

    try:
        # ── Inicializar servicio AssemblyAI ──────────────────
        svc = AssemblyAIStreamingService(
            on_transcript=on_transcript,
            loop=loop,
            max_speakers=max_speakers,
            sample_rate=sample_rate,
        )
        await svc.connect()
        logger.info("AssemblyAI conectado para cliente WebSocket")

        # ── Loop principal: recibir audio ────────────────────
        while True:
            try:
                message = await websocket.receive()
            except (WebSocketDisconnect, RuntimeError):
                # RuntimeError: Starlette lanza esto si el cliente ya cerró.
                logger.info("Cliente WebSocket desconectado")
                break

            # Mensaje de cierre enviado por el cliente.
            if message.get("type") == "websocket.disconnect":
                logger.info("Cliente WebSocket desconectado")
                break

            if "text" in message:
                try:
                    ctrl = json.loads(message["text"])
                    if not isinstance(ctrl, dict):
                        continue
                    if ctrl.get("action") == "ping":
                        await send_json_safe({"type": "pong", "timestamp_ms": 0})
                        continue
                    if ctrl.get("conversation_id"):
                        try:
                            effective_conversation_id = uuid.UUID(str(ctrl["conversation_id"]))
                        except ValueError:
                            logger.warning("conversation_id inválido en handshake: %s", ctrl["conversation_id"])
                    if ctrl.get("max_speakers"):
                        max_speakers = int(ctrl["max_speakers"])
                    if ctrl.get("sample_rate"):
                        sample_rate = int(ctrl["sample_rate"])
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
                continue

            # Bytes (audio PCM)
            if "bytes" in message and message["bytes"]:
                audio = message["bytes"]
                if enhancer is not None:
                    audio = enhancer.process_pcm(audio)
                if audio:
                    svc.send_audio(audio)

    except RuntimeError as e:
        # Error de configuración (API key faltante, SDK no instalado, etc.)
        logger.error("Error de configuración en /ws/audio: %s", e)
        await send_json_safe({
            "type": "error",
            "speaker": None,
            "speaker_label": None,
            "text": str(e),
            "is_final": False,
            "segments": [],
            "timestamp_ms": 0,
        })
    except WebSocketDisconnect:
        logger.info("WebSocket cerrado durante handshake")
    except Exception as e:
        logger.exception("Error inesperado en /ws/audio: %s", e)
        await send_json_safe({
            "type": "error",
            "speaker": None,
            "speaker_label": None,
            "text": f"Error interno: {e}",
            "is_final": False,
            "segments": [],
            "timestamp_ms": 0,
        })
    finally:
        if svc:
            await svc.disconnect()
        logger.info("Conexión /ws/audio cerrada")
