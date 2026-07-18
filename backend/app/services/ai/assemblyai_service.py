"""
assemblyai_service.py
─────────────────────
Servicio de reconocimiento de voz en tiempo real con diarización de hablantes
usando AssemblyAI Streaming SDK v3.

Cada cliente WebSocket instancia un AssemblyAIStreamingService independiente.
El servicio:
  1. Abre una sesión AssemblyAI al conectarse.
  2. Recibe chunks de audio (bytes PCM 16kHz mono) y los envía a la API.
  3. Convierte los eventos TurnEvent / SpeakerRevisionEvent en dicts JSON.
  4. Llama a un callback async para que el WebSocket los envíe al cliente.
  5. Se desconecta limpiamente cuando el WebSocket cierra.

Formato del JSON emitido al callback:
  {
    "type": "partial" | "final" | "revision",
    "speaker": "Persona 1",          # etiqueta amigable
    "speaker_label": "A",            # etiqueta cruda de AssemblyAI
    "text": "Hola, cómo estás",
    "is_final": True | False,
    "segments": [                    # solo en "final" y "revision"
      {"speaker": "Persona 1", "speaker_label": "A", "text": "..."},
      ...
    ],
    "timestamp_ms": 1234567890
  }
"""

import asyncio
import logging
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings
from app.utils.text_cleaning import clean_text

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Constantes de configuración
# ──────────────────────────────────────────────────────────────
SPEECH_MODEL = "universal-3-5-pro"
SAMPLE_RATE = 16_000       # Hz — PCM mono int16
MAX_SPEAKERS = 10
LANGUAGE_CODES = ["es"]    # español; agrega "en" si necesitas multilingüe

# Etiquetas que la API asigna mientras aún no identifica al hablante
NON_SPEAKER_LABELS = {"UNKNOWN", "PENDING"}


# ──────────────────────────────────────────────────────────────
# Helpers de formato
# ──────────────────────────────────────────────────────────────

def _friendly_label(raw: str | None) -> str:
    """Convierte 'A' → 'Persona 1', 'B' → 'Persona 2', etc."""
    if not raw or raw.upper() in NON_SPEAKER_LABELS:
        return "Identificando voz…"
    label = raw.upper()
    if len(label) == 1 and "A" <= label <= "Z":
        return f"Persona {ord(label) - ord('A') + 1}"
    return f"Persona {raw}"


def _group_words(words, fallback_label: str | None) -> list[dict]:
    """Agrupa palabras consecutivas del mismo hablante en segmentos."""
    segments: list[tuple[str | None, list[str]]] = []
    for word in words:
        text = word.text.strip()
        if not text:
            continue
        spk = word.speaker or fallback_label
        if segments and segments[-1][0] == spk:
            segments[-1][1].append(text)
        else:
            segments.append((spk, [text]))
    result = []
    for spk, parts in segments:
        cleaned = clean_text(" ".join(parts), level="full")
        if not cleaned:
            continue
        result.append({
            "speaker": _friendly_label(spk),
            "speaker_label": spk or "?",
            "text": cleaned,
        })
    return result


# ──────────────────────────────────────────────────────────────
# Servicio principal
# ──────────────────────────────────────────────────────────────

class AssemblyAIStreamingService:
    """
    Wrapper async-compatible sobre el AssemblyAI Streaming SDK v3.

    El SDK usa threads internos + callbacks síncronos. Aquí usamos una
    asyncio.Queue para pasar los eventos al loop async del WebSocket.
    """

    def __init__(
        self,
        on_transcript: Callable[[dict], Coroutine[Any, Any, None]],
        loop: asyncio.AbstractEventLoop,
        max_speakers: int = MAX_SPEAKERS,
        sample_rate: int = SAMPLE_RATE,
    ):
        self._api_key = settings.ASSEMBLYAI_API_KEY
        self._on_transcript = on_transcript
        self._loop = loop
        self._max_speakers = max_speakers
        self._sample_rate = sample_rate

        self._client = None
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._connected = False
        self._audio_buffer: list[bytes] = []
        self._buffer_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._sender_thread: threading.Thread | None = None
        self._dispatch_task: asyncio.Task | None = None

    # ── Ciclo de vida ────────────────────────────────────────

    async def connect(self):
        """Abre la sesión AssemblyAI y lanza el dispatcher de eventos."""
        if not self._api_key:
            logger.error("ASSEMBLYAI_API_KEY no configurada")
            raise RuntimeError("ASSEMBLYAI_API_KEY no está configurada en el entorno.")

        try:
            from assemblyai.streaming.v3 import (
                StreamingClient,
                StreamingClientOptions,
                StreamingError,
                StreamingEvents,
                StreamingParameters,
                TurnEvent,
                SpeakerRevisionEvent,
                BeginEvent,
                TerminationEvent,
            )
        except ImportError as e:
            logger.error("assemblyai no instalado: %s", e)
            raise RuntimeError(
                "El paquete 'assemblyai' no está instalado. "
                "Ejecuta: pip install 'assemblyai>=0.39.0'"
            ) from e

        self._client = StreamingClient(
            StreamingClientOptions(api_key=self._api_key)
        )

        # ── Callbacks síncronos del SDK ──────────────────────

        def on_begin(client, event: BeginEvent):
            logger.info("AssemblyAI sesión iniciada: %s", event.id)
            self._connected = True
            self._put_nowait({
                "type": "connected",
                "session_id": event.id,
                "speaker": None,
                "speaker_label": None,
                "text": "Sesión de reconocimiento iniciada",
                "is_final": False,
                "segments": [],
                "timestamp_ms": int(time.time() * 1000),
            })

        def on_turn(client, event: TurnEvent):
            if not event.transcript:
                return
            if event.end_of_turn:
                # Turno final: segmentamos por hablante
                segs = _group_words(event.words, event.speaker_label)
                if not segs:
                    fallback = clean_text(event.transcript, level="full")
                    if not fallback:
                        return
                    segs = [{
                        "speaker": _friendly_label(event.speaker_label),
                        "speaker_label": event.speaker_label or "?",
                        "text": fallback,
                    }]
                # Emitir un evento por segmento (más fácil de manejar en cliente)
                for seg in segs:
                    self._put_nowait({
                        "type": "final",
                        "speaker": seg["speaker"],
                        "speaker_label": seg["speaker_label"],
                        "text": seg["text"],
                        "is_final": True,
                        "segments": segs,
                        "timestamp_ms": int(time.time() * 1000),
                    })
            else:
                # Transcripción parcial (en vivo)
                partial_text = clean_text(event.transcript, level="light")
                if not partial_text:
                    return
                self._put_nowait({
                    "type": "partial",
                    "speaker": _friendly_label(event.speaker_label),
                    "speaker_label": event.speaker_label or "?",
                    "text": partial_text,
                    "is_final": False,
                    "segments": [],
                    "timestamp_ms": int(time.time() * 1000),
                })

        def on_revision(client, event: SpeakerRevisionEvent):
            """El modelo corrige atribución de voz de turnos pasados."""
            for item in event.revisions:
                segs = _group_words(item.words, item.speaker_label)
                if not segs:
                    continue
                self._put_nowait({
                    "type": "revision",
                    "speaker": _friendly_label(item.speaker_label),
                    "speaker_label": item.speaker_label or "?",
                    "text": " ".join(s["text"] for s in segs),
                    "is_final": True,
                    "segments": segs,
                    "turn_order": item.turn_order,
                    "timestamp_ms": int(time.time() * 1000),
                })

        def on_terminated(client, event: TerminationEvent):
            logger.info(
                "AssemblyAI sesión terminada. Audio: %.1fs",
                event.audio_duration_seconds,
            )
            self._connected = False
            self._put_nowait(None)   # señal de fin al dispatcher

        def on_error(client, error: StreamingError):
            logger.error("AssemblyAI error: %s", error)
            self._put_nowait({
                "type": "error",
                "speaker": None,
                "speaker_label": None,
                "text": str(error),
                "is_final": False,
                "segments": [],
                "timestamp_ms": int(time.time() * 1000),
            })

        self._client.on(StreamingEvents.Begin, on_begin)
        self._client.on(StreamingEvents.Turn, on_turn)
        self._client.on(StreamingEvents.SpeakerRevision, on_revision)
        self._client.on(StreamingEvents.Termination, on_terminated)
        self._client.on(StreamingEvents.Error, on_error)

        # Conectar (bloqueante, se hace en thread)
        params = StreamingParameters(
            speech_model=SPEECH_MODEL,
            sample_rate=self._sample_rate,
            language_codes=LANGUAGE_CODES,
            speaker_labels=True,
            max_speakers=self._max_speakers,
            format_turns=True,
        )
        self._client.connect(params)

        # ── Thread que envía audio a AssemblyAI ─────────────
        def _sender():
            try:
                self._client.stream(self._audio_generator())
            except Exception as e:
                logger.error("Error en sender thread: %s", e)

        self._sender_thread = threading.Thread(target=_sender, daemon=True)
        self._sender_thread.start()

        # ── Task async que despacha eventos al WebSocket ─────
        self._dispatch_task = asyncio.ensure_future(self._dispatcher())

    async def disconnect(self):
        """Desconecta limpiamente de AssemblyAI."""
        self._stop_event.set()
        if self._client and self._connected:
            try:
                self._client.disconnect(terminate=True)
            except Exception as e:
                logger.warning("Error al desconectar AssemblyAI: %s", e)
        if self._dispatch_task and not self._dispatch_task.done():
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

    # ── Envío de audio ───────────────────────────────────────

    def send_audio(self, chunk: bytes):
        """Encola un chunk de audio PCM para enviarlo a AssemblyAI."""
        with self._buffer_lock:
            self._audio_buffer.append(chunk)

    def _audio_generator(self):
        """
        Generador bloqueante que el SDK consume en su thread interno.

        AssemblyAI exige que CADA chunk enviado dure entre 50 y 1000 ms.
        Como el audio de entrada puede llegar en trozos irregulares (sobre todo
        tras la limpieza de ruido, que re-fragmenta el audio), aquí acumulamos y
        entregamos siempre bloques fijos de ~100 ms para cumplir el requisito.
        """
        target = int(0.1 * self._sample_rate) * 2   # 100 ms en bytes (int16 mono)
        acc = bytearray()
        while not self._stop_event.is_set():
            with self._buffer_lock:
                if self._audio_buffer:
                    acc.extend(b"".join(self._audio_buffer))
                    self._audio_buffer.clear()
            emitted = False
            while len(acc) >= target:
                yield bytes(acc[:target])
                del acc[:target]
                emitted = True
            if not emitted:
                time.sleep(0.01)   # 10 ms de polling si no hay suficiente audio

    # ── Dispatcher async ─────────────────────────────────────

    async def _dispatcher(self):
        """
        Loop async que saca eventos de la queue y llama al callback
        on_transcript del WebSocket.
        """
        while True:
            try:
                event = await self._queue.get()
                if event is None:   # señal de fin
                    break
                await self._on_transcript(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error en dispatcher: %s", e)

    def _put_nowait(self, event: dict | None):
        """Thread-safe: encola un evento desde el thread del SDK."""
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except Exception as e:
            logger.warning("No se pudo encolar evento: %s", e)
