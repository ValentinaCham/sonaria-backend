import asyncio
import queue
import threading
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from assemblyai.streaming.v3 import (
    StreamingClient,
    StreamingClientOptions,
    StreamingEvents,
    StreamingParameters,
    TurnEvent,
)

from app.config import settings

router = APIRouter()

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
    client = StreamingClient(StreamingClientOptions(api_key=settings.ASSEMBLYAI_API_KEY))
    
    def on_turn(c: StreamingClient, event: TurnEvent):
        if not event.transcript:
            return
        
        # event.speaker_label is the speaker (e.g. 'A', 'B')
        text = event.transcript.strip()
        speaker = event.speaker_label if event.speaker_label else "UNKNOWN"
        is_final = event.end_of_turn
        
        payload = {
            "speaker": speaker,
            "text": text,
            "is_final": is_final
        }
        
        # Send back to the websocket
        asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)
        
    def on_error(c: StreamingClient, error):
        print(f"AssemblyAI Error: {error}")
        
    client.on(StreamingEvents.Turn, on_turn)
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
        client.stream(audio_generator(q, stop_event))
    except Exception as e:
        print(f"AssemblyAI Stream exception: {e}")
    finally:
        client.disconnect(terminate=True)


@router.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket):
    await websocket.accept()
    
    q = queue.Queue()
    stop_event = threading.Event()
    loop = asyncio.get_running_loop()
    
    # Start AssemblyAI in a background thread
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
        print("Client disconnected from audio stream")
    finally:
        stop_event.set()
        q.put(None) # Unblock generator
        aai_thread.join(timeout=2)

