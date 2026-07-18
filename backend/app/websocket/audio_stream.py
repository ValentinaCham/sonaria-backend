import asyncio
import queue
import threading
import sys
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from assemblyai.streaming.v3 import (
    StreamingClient,
    StreamingClientOptions,
    StreamingEvents,
    StreamingParameters,
    TurnEvent,
    BeginEvent,
    SpeakerRevisionEvent,
)

from app.config import settings

router = APIRouter()

def group_words_by_speaker(words, fallback_label: str | None):
    segments = []
    for word in words:
        text = word.text.strip()
        if not text:
            continue
        spk = word.speaker or fallback_label
        if segments and segments[-1][0] == spk:
            segments[-1][1].append(text)
        else:
            segments.append((spk, [text]))
    return [(spk, " ".join(parts)) for spk, parts in segments]

def audio_generator(q: queue.Queue, stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            chunk = q.get(timeout=0.1)
            if chunk is None:
                break
            yield chunk
        except queue.Empty:
            continue

def start_assemblyai_client(websocket: WebSocket, loop: asyncio.AbstractEventLoop, q: queue.Queue, stop_event: threading.Event):
    print("Iniciando cliente de AssemblyAI...")
    client = StreamingClient(StreamingClientOptions(api_key=settings.ASSEMBLYAI_API_KEY))
    
    def on_begin(c: StreamingClient, event: BeginEvent):
        print(f"✅ AssemblyAI Sesión iniciada: {event.id}")
    
    def on_turn(c: StreamingClient, event: TurnEvent):
        if not event.transcript:
            return
            
        if event.end_of_turn:
            segments = group_words_by_speaker(event.words, event.speaker_label)
            if not segments:
                segments = [(event.speaker_label, event.transcript.strip())]
            for i, (spk, text) in enumerate(segments):
                speaker = spk if spk else "UNKNOWN"
                payload = {
                    "type": "turn",
                    "turn_order": f"{event.turn_order}_{i}",
                    "speaker": speaker, 
                    "text": text, 
                    "is_final": True
                }
                asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)
        else:
            text = event.transcript.strip()
            speaker = event.speaker_label if event.speaker_label else "UNKNOWN"
            payload = {
                "type": "turn",
                "turn_order": f"{event.turn_order}_0",
                "speaker": speaker, 
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
            for i, (spk, text) in enumerate(segments):
                speaker = spk if spk else "UNKNOWN"
                revisions.append({
                    "turn_order": f"{item.turn_order}_{i}",
                    "speaker": speaker,
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
        client.stream(audio_generator(q, stop_event))
    except Exception as e:
        print(f"🛑 AssemblyAI Stream exception: {e}")
    finally:
        print("🔌 Desconectando AssemblyAI...")
        try:
            client.disconnect(terminate=True)
        except Exception:
            pass


@router.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket):
    print("Conexión WebSocket recibida en el backend!")
    await websocket.accept()
    
    q = queue.Queue()
    stop_event = threading.Event()
    loop = asyncio.get_running_loop()
    
    aai_thread = threading.Thread(
        target=start_assemblyai_client,
        args=(websocket, loop, q, stop_event),
        daemon=True
    )
    aai_thread.start()
    
    try:
        while True:
            data = await websocket.receive_bytes()
            q.put(data)
    except WebSocketDisconnect:
        print("❌ Cliente desconectado del audio stream")
    except Exception as e:
        print(f"❌ Error en websocket loop: {e}")
    finally:
        stop_event.set()
        q.put(None)
        aai_thread.join(timeout=2)


