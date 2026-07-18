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
from app.services.voice_biometrics import voice_biometrics

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
    
    # Diccionario para mapear temporalmente A, B, C a "Dueña"
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
                if speaker not in ["UNKNOWN", "Dueña"] and speaker not in speaker_mapping:
                    # Extraer audio del buffer (1 ms = 32 bytes, a 16kHz, 16 bits mono)
                    start_byte = seg["start"] * 32
                    end_byte = seg["end"] * 32
                    audio_chunk = bytes(audio_buffer[start_byte:end_byte])
                    
                    # Verificamos si dura más de 1 segundo (32000 bytes) para que sea confiable
                    if len(audio_chunk) > 32000:
                        is_owner = voice_biometrics.verify_speaker(audio_chunk)
                        if is_owner:
                            speaker_mapping[speaker] = "Dueña"
                            print(f"🎉 ¡Hablante {speaker} identificado como Dueña!")
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
async def audio_stream(websocket: WebSocket):
    print("Conexión WebSocket recibida en el backend!")
    await websocket.accept()
    
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
