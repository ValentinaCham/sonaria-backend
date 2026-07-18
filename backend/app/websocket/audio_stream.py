"""
audio_stream.py
───────────────
WebSocket /ws/audio — Reconocimiento de voz en tiempo real con diarización,
limpieza de ruido y análisis/clasificación de voz (diagrama de voz).

Protocolo cliente ↔ servidor:

  CONEXIÓN:
    ws://host/ws/audio?token=<JWT>&max_speakers=<N>&sample_rate=<Hz>&clean=<bool>&analyze=<bool>

  CLIENTE → SERVIDOR:
    Bytes crudos: audio PCM 16kHz mono int16 (sin cabecera WAV)
    ─ o ─
    JSON de control: { "action": "ping" }

  SERVIDOR → CLIENTE (JSON):
    - Transcripción por turno:
      { "type": "partial"|"final"|"revision", "turn_order": N,
        "speaker": "Persona 1", "speaker_label": "A", "text": "...",
        "segments": [ { "speaker", "speaker_label", "text" } ], "is_final": bool }
    - Análisis de voz (diagrama):
      { "type": "voice_analysis", "mel": [...], "pitch_hz", "centroid_hz",
        "rms", "is_speech", "voice_id", "voice_name", "confidence", "is_new_voice" }
    - Otros: "connected", "error", "pong".
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
from app.services.audio.voice_features import VoiceAnalyzer
from app.services.conversation_service import ConversationService
from app.services.voice_biometrics import voice_biometrics

logger = logging.getLogger(__name__)
router = APIRouter()

def group_words_by_speaker(words, fallback_label: str | None):
    segments = []
    for word in words:
        text = word.text.strip()
        if not text:
            continue
        spk = word.speaker or fallback_label
        
        # Guardar también el start y end de cada segmento para extraer el audio
        start = word.start
        end = word.end
        
        if segments and segments[-1]["speaker"] == spk:
            segments[-1]["text"].append(text)
            segments[-1]["end"] = end
        else:
            segments.append({"speaker": spk, "text": [text], "start": start, "end": end})
            
    return [{"speaker": s["speaker"], "text": " ".join(s["text"]), "start": s["start"], "end": s["end"]} for s in segments]

def audio_generator(q: queue.Queue, stop_event: threading.Event, audio_buffer: bytearray):
    while not stop_event.is_set():
        try:
            chunk = q.get(timeout=0.1)
            if chunk is None:
                break
            audio_buffer.extend(chunk)
            yield chunk
        except queue.Empty:
            continue

def start_assemblyai_client(websocket: WebSocket, loop: asyncio.AbstractEventLoop, q: queue.Queue, stop_event: threading.Event, audio_buffer: bytearray):
    print("Iniciando cliente de AssemblyAI...")
    client = StreamingClient(StreamingClientOptions(api_key=settings.ASSEMBLYAI_API_KEY))
    
    # Diccionario para mapear temporalmente A, B, C a "me"
    speaker_mapping = {}
    
    def on_begin(c: StreamingClient, event: BeginEvent):
        print(f"✅ AssemblyAI Sesión iniciada: {event.id}")
    
    def on_turn(c: StreamingClient, event: TurnEvent):
        if not event.transcript:
            return
            
        if event.end_of_turn:
            segments = group_words_by_speaker(event.words, event.speaker_label)
            if not segments:
                # Si no hay palabras, creamos un segmento artificial sin timestamps exactos
                segments = [{"speaker": event.speaker_label, "text": event.transcript.strip(), "start": 0, "end": 0}]
                
            for i, seg in enumerate(segments):
                spk = seg["speaker"]
                text = seg["text"]
                speaker = spk if spk else "UNKNOWN"
                
                # Biometría en vivo: Si no sabemos quién es este speaker, analizamos su audio
                if speaker not in ["UNKNOWN", "me"] and speaker not in speaker_mapping:
                    # Extraer audio del buffer (1 ms = 32 bytes, a 16kHz, 16 bits mono)
                    start_byte = seg["start"] * 32
                    end_byte = seg["end"] * 32
                    audio_chunk = bytes(audio_buffer[start_byte:end_byte])
                    
                    # Verificamos si dura más de 1 segundo (32000 bytes) para que sea confiable
                    if len(audio_chunk) > 32000:
                        is_owner = voice_biometrics.verify_speaker(audio_chunk)
                        if is_owner:
                            speaker_mapping[speaker] = "me"
                            print(f"🎉 ¡Hablante {speaker} identificado como 'me'!")
                        else:
                            # Lo marcamos para no volver a analizarlo pronto (o podríamos seguir reintentando)
                            speaker_mapping[speaker] = speaker

                # Reemplazar con el mapeo si existe
                final_speaker = speaker_mapping.get(speaker, speaker)
                
                payload = {
                    "type": "turn",
                    "turn_order": f"{event.turn_order}_{i}",
                    "speaker": final_speaker, 
                    "text": text, 
                    "is_final": True
                }
                asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)
        else:
            text = event.transcript.strip()
            speaker = event.speaker_label if event.speaker_label else "UNKNOWN"
            final_speaker = speaker_mapping.get(speaker, speaker)
            
            payload = {
                "type": "turn",
                "turn_order": f"{event.turn_order}_0",
                "speaker": final_speaker, 
                "text": text, 
                "is_final": False
            }
            asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)
            
    def on_speaker_revision(c: StreamingClient, event: SpeakerRevisionEvent):
        revisions = []
        for item in event.revisions:
            segments = group_words_by_speaker(item.words, item.speaker_label)
            if not segments:
                continue
            for i, seg in enumerate(segments):
                spk = seg["speaker"]
                text = seg["text"]
                speaker = spk if spk else "UNKNOWN"
                final_speaker = speaker_mapping.get(speaker, speaker)
                
                revisions.append({
                    "turn_order": f"{item.turn_order}_{i}",
                    "speaker": final_speaker,
                    "text": text
                })
        if revisions:
            payload = {
                "type": "revision",
                "revisions": revisions
            }
            asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)

    def on_error(c: StreamingClient, error):
        print(f"⚠️ Error de AssemblyAI: {error}")
        
    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.SpeakerRevision, on_speaker_revision)
    client.on(StreamingEvents.Error, on_error)
    
    try:
        client.connect(StreamingParameters(
            speech_model="universal-3-5-pro",
            sample_rate=16000,
            language_codes=["es"],
            speaker_labels=True,
            max_speakers=5,
            format_turns=True,
        ))
        print("▶️ Conectado, iniciando stream de audio...")
        client.stream(audio_generator(q, stop_event, audio_buffer))
    except Exception as e:
        print(f"🛑 AssemblyAI Stream exception: {e}")
    finally:
        print("🔌 Desconectando AssemblyAI...")
        try:
            client.disconnect(terminate=True)
        except Exception:
            pass


@router.websocket("/ws/audio")
async def audio_stream(
    websocket: WebSocket,
    token: str | None = Query(default=None, description="JWT opcional vía query param"),
    conversation_id: str | None = Query(default=None, description="ID de conversación opcional"),
    max_speakers: int = Query(default=5, ge=1, le=10, description="Máximo de hablantes"),
    sample_rate: int = Query(default=16000, description="Sample rate del audio en Hz"),
    clean: bool | None = Query(default=None, description="Activar limpieza de ruido (por defecto según config)"),
    analyze: bool | None = Query(default=None, description="Activar análisis/clasificación de voz (por defecto según config)"),
):
    """WebSocket de reconocimiento de voz multi-persona en tiempo real."""
    await websocket.accept()
    logger.info(
        "Nueva conexión WebSocket /ws/audio | max_speakers=%d | sample_rate=%d",
        max_speakers, sample_rate,
    )

    # Inicializar biometría en el primer request si no se ha hecho
    if not voice_biometrics.is_ready:
        voice_biometrics.initialize()
        
    q = queue.Queue()
    stop_event = threading.Event()
    loop = asyncio.get_running_loop()
    audio_buffer = bytearray()
    
    aai_thread = threading.Thread(
        target=start_assemblyai_client,
        args=(websocket, loop, q, stop_event, audio_buffer),
        daemon=True
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

    # ── Análisis de voz (espectrograma + clasificación) ──
    analysis_enabled = settings.ENABLE_VOICE_ANALYSIS if analyze is None else analyze
    analyzer: VoiceAnalyzer | None = None
    if analysis_enabled:
        try:
            analyzer = VoiceAnalyzer(sample_rate=sample_rate)
            logger.info("Análisis de voz ACTIVADO (espectrograma+MFCC) para esta conexión")
        except Exception as exc:
            logger.warning("No se pudo iniciar el análisis de voz: %s", exc)
            analyzer = None

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
                logger.info("Cliente WebSocket desconectado")
                break

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
                raw = message["bytes"]
                # Análisis del "diagrama de voz" sobre el audio original (continuo).
                if analyzer is not None:
                    try:
                        for ev in analyzer.feed(raw):
                            await send_json_safe(ev)
                    except Exception as exc:
                        logger.warning("Fallo análisis de voz: %s", exc)
                audio = raw
                if enhancer is not None:
                    audio = enhancer.process_pcm(audio)
                if audio:
                    svc.send_audio(audio)

    except RuntimeError as e:
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
        stop_event.set()
        q.put(None)
        aai_thread.join(timeout=2)
