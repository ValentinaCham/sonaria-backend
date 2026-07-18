import os
import sys
import time
import threading
from pathlib import Path

import sounddevice as sd
from assemblyai.streaming.v3 import (
    BeginEvent,
    SpeakerRevisionEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)

# ══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════
SAMPLE_RATE = 16000       # AssemblyAI espera 16 kHz por defecto
BLOCK_SIZE = 800          # ~50 ms de audio

# ──────────────────────────────────────────────────────────────
#  ¿CÓMO SEPARAR A LAS PERSONAS?  Elige UNO de los dos modos:
# ──────────────────────────────────────────────────────────────
#
#  MODO A — UN MICRÓFONO POR PERSONA  (SEPARACIÓN GARANTIZADA) ✅
#     Cada persona con su propio micro (auriculares, celular por
#     Bluetooth, etc.). Pon aquí el índice de cada dispositivo, uno
#     por persona. Abre UNA sesión por micro → cada quien es SIEMPRE
#     una persona distinta. Esto SÍ resuelve el "todos salen Persona 1".
#
#     Para ver los índices:   python streaming_assemblyai.py --list
#     Ejemplo con 3 personas:  MIC_DEVICES = [1, 20, 30]
#
#  MODO B — UN SOLO MICRÓFONO COMPARTIDO  (deja la lista vacía)
#     Usa la diarización de la IA sobre un único micro. Funciona
#     razonable SOLO si hablan por turnos y sin pisarse; con voces
#     cruzadas la IA tiende a juntar todo en una sola persona.
#
MIC_DEVICES: list[int] = []      # ← p.ej. [1, 20, 30]. Vacío = un solo micro.

# Nombres opcionales para cada persona del MODO A (mismo orden que MIC_DEVICES)
SPEAKER_NAMES: list[str] = []    # ← p.ej. ["Ana", "Luis", "Marta"]

# ¿Cuántas personas esperar en el MODO B?  Ponlo igual al número real
# de personas (rango 1-10). Es una pista clave para la separación.
EXPECTED_SPEAKERS = 5

# Modelo de voz. Para separar voces en ESPAÑOL el multilingüe suele ir
# mejor; universal-3-5-pro es el más nuevo. Prueba ambos.
SPEECH_MODEL = "universal-3-5-pro"   # o "universal-streaming-multilingual"

# Muestra en vivo qué hablante asigna la API a cada palabra (MODO B).
DEBUG_SPEAKERS = True

SAVE_TO_FILE = False
FILE_NAME = "subtitulos_assemblyai.txt"

# Colores ANSI para cada persona
SPEAKER_COLORS = [
    "\033[94m",   # azul
    "\033[92m",   # verde
    "\033[93m",   # amarillo
    "\033[91m",   # rojo
    "\033[95m",   # magenta
    "\033[96m",   # cian
]
RESET_COLOR = "\033[0m"
CLEAR_LINE = "\r\033[K"   # vuelve al inicio de línea y la borra

# ══════════════════════════════════════════════════════════════
# 1. Cargar la API Key de AssemblyAI
# ══════════════════════════════════════════════════════════════

def load_api_key():
    """Busca la API key en ASSEMBLYAI_API_KEY (entorno) o en un archivo local."""
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if api_key:
        return api_key.strip()

    for name in ("assemblyai_key.txt", "apai.txt"):
        api_file = Path(__file__).parent / name
        if api_file.exists():
            api_key = api_file.read_text(encoding="utf-8").strip()
            if api_key:
                return api_key

    raise ValueError(
        "No se encontró la API Key de AssemblyAI. "
        "Usa la variable de entorno ASSEMBLYAI_API_KEY "
        "o crea un archivo assemblyai_key.txt con la clave."
    )


API_KEY = load_api_key()

# ══════════════════════════════════════════════════════════════
# 2. Helpers de salida en terminal
# ══════════════════════════════════════════════════════════════

_print_lock = threading.Lock()   # evita que dos sesiones pisen la salida

# Etiquetas que NO son un hablante confirmado: el modelo aún aprende la
# voz. 'UNKNOWN' llega en frases muy cortas ("sí", "ok"); 'PENDING' lo
# usa el modelo multilingüe durante el calentamiento inicial.
NON_SPEAKER_LABELS = {"UNKNOWN", "PENDING"}


def enable_utf8_and_ansi():
    os.system("")   # habilita colores ANSI en la consola de Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def speaker_label(assembly_label: str | None) -> str:
    """Convierte 'A', 'B', 'C'... en 'Persona 1', 'Persona 2'..."""
    if not assembly_label or assembly_label.upper() in NON_SPEAKER_LABELS:
        return "🎧 identificando voz…"
    label = assembly_label.upper()
    if len(label) == 1 and "A" <= label <= "Z":
        return f"Persona {ord(label) - ord('A') + 1}"
    return f"Persona {assembly_label}"


def speaker_color(assembly_label: str | None) -> str:
    if not assembly_label or assembly_label.upper() in NON_SPEAKER_LABELS:
        return "\033[90m"   # gris: aún sin hablante confirmado
    label = assembly_label.upper()
    if len(label) == 1 and "A" <= label <= "Z":
        return SPEAKER_COLORS[(ord(label) - ord("A")) % len(SPEAKER_COLORS)]
    return ""


def save_line(label: str, text: str):
    if not SAVE_TO_FILE:
        return
    with open(FILE_NAME, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} | {label}: {text}\n")


def group_words_by_speaker(words, fallback_label: str | None):
    """Agrupa palabras consecutivas del mismo hablante en segmentos.

    La diarización llega PALABRA por PALABRA (word.speaker). Si dos
    personas hablan dentro del mismo turno, separamos el turno en un
    segmento por cada cambio de voz.
    """
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
    return [(spk, " ".join(parts)) for spk, parts in segments]


def print_segments(segments, prefix: str = ""):
    for spk, text in segments:
        label = speaker_label(spk)
        color = speaker_color(spk)
        print(f"{prefix}{color}{label}: {text}{RESET_COLOR}")
        save_line(label, text)


# ══════════════════════════════════════════════════════════════
# 3. Captura de micrófono
# ══════════════════════════════════════════════════════════════

def mic_stream(device: int | None = None, stop_event: threading.Event | None = None):
    """Generador que entrega chunks de audio de un micrófono concreto."""
    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=BLOCK_SIZE,
        device=device,
    ) as mic:
        while stop_event is None or not stop_event.is_set():
            frames, _ = mic.read(BLOCK_SIZE)
            yield bytes(frames)


def list_input_devices():
    print("\n🎚️  Dispositivos de ENTRADA disponibles (usa el número en MIC_DEVICES):\n")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i:>2}] {d['name']}  (canales in: {d['max_input_channels']})")
    print(
        "\nEjemplo: para 3 personas con 3 micros pon  MIC_DEVICES = [1, 20, 30]\n"
        "y (opcional)  SPEAKER_NAMES = [\"Ana\", \"Luis\", \"Marta\"]\n"
    )


# ══════════════════════════════════════════════════════════════
# 4A. MODO A — un micrófono por persona (separación garantizada)
# ══════════════════════════════════════════════════════════════

def run_multi_mic(devices: list[int]):
    """Abre una sesión de streaming por micrófono. Cada micro = una
    persona fija, así la separación es 100% fiable sin importar cuánto
    se pisen las voces (cada quien tiene su propio audio)."""
    stop_event = threading.Event()
    clients: list[StreamingClient] = []
    threads: list[threading.Thread] = []

    def make_session(person_idx: int, device: int):
        if person_idx < len(SPEAKER_NAMES) and SPEAKER_NAMES[person_idx]:
            label = SPEAKER_NAMES[person_idx]
        else:
            label = f"Persona {person_idx + 1}"
        color = SPEAKER_COLORS[person_idx % len(SPEAKER_COLORS)]

        client = StreamingClient(StreamingClientOptions(api_key=API_KEY))

        def on_turn(c, e: TurnEvent):
            if not e.transcript or not e.end_of_turn:
                return  # en multi-micro imprimimos solo turnos finales (salida limpia)
            text = e.transcript.strip()
            with _print_lock:
                print(f"{color}{label}: {text}{RESET_COLOR}")
                save_line(label, text)

        def on_error(c, err: StreamingError):
            with _print_lock:
                print(f"⚠️ [{label}] {err}")

        client.on(StreamingEvents.Turn, on_turn)
        client.on(StreamingEvents.Error, on_error)
        client.connect(StreamingParameters(
            speech_model=SPEECH_MODEL,
            sample_rate=SAMPLE_RATE,
            language_codes=["es"],
            format_turns=True,
            # speaker_labels NO hace falta: cada sesión ya es una persona.
        ))
        clients.append(client)

        def run():
            try:
                client.stream(mic_stream(device, stop_event))
            except Exception as e:
                with _print_lock:
                    print(f"⚠️ [{label}] error de audio: {e}")

        t = threading.Thread(target=run, daemon=True)
        t.start()
        threads.append(t)

    print("🎙️ MODO MULTI-MICRÓFONO — separación garantizada")
    for i, dev in enumerate(devices):
        name = SPEAKER_NAMES[i] if i < len(SPEAKER_NAMES) else f"Persona {i+1}"
        dev_name = sd.query_devices(dev)["name"]
        print(f"   {SPEAKER_COLORS[i % len(SPEAKER_COLORS)]}{name}{RESET_COLOR} → mic [{dev}] {dev_name}")
        make_session(i, dev)

    print("\n✅ Escuchando. Habla ahora (Ctrl+C para detener)\n")

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n\n⏹️ Deteniendo...")
    finally:
        stop_event.set()
        for c in clients:
            try:
                c.disconnect(terminate=True)
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════
# 4B. MODO B — un solo micrófono compartido (diarización de la IA)
# ══════════════════════════════════════════════════════════════

def debug_dump_turn(event: TurnEvent):
    """Muestra los datos crudos de diarización que devuelve la API.

    Si TODAS las palabras salen con el mismo hablante (o vacío), la API
    no está separando las voces del audio (micrófono único mezclado, sala
    ruidosa o poco tiempo de voz). Si ves 'A', 'B', 'C'... sí separa.
    """
    per_word = [f"{w.text}={w.speaker}" for w in event.words]
    distintos = sorted({w.speaker for w in event.words if w.speaker})
    print(
        f"\n\033[90m[debug] turn_label={event.speaker_label} "
        f"hablantes_en_turno={distintos or 'ninguno'} "
        f"| {' '.join(per_word)}\033[0m"
    )


def on_begin(client: StreamingClient, event: BeginEvent):
    print(f"✅ Sesión iniciada: {event.id}")
    print("🎙️ Escuchando en vivo... Habla ahora (Ctrl+C para detener)\n")


def on_turn(client: StreamingClient, event: TurnEvent):
    if not event.transcript:
        return

    if event.end_of_turn:
        if DEBUG_SPEAKERS:
            debug_dump_turn(event)
        segments = group_words_by_speaker(event.words, event.speaker_label)
        if not segments:
            segments = [(event.speaker_label, event.transcript.strip())]
        print(CLEAR_LINE, end="")
        print_segments(segments)
    else:
        label = speaker_label(event.speaker_label)
        color = speaker_color(event.speaker_label)
        text = event.transcript.strip()
        print(f"{CLEAR_LINE}{color}{label}: {text}{RESET_COLOR}", end="", flush=True)


def on_speaker_revision(client: StreamingClient, event: SpeakerRevisionEvent):
    """El modelo re-analiza las voces y corrige turnos anteriores."""
    for item in event.revisions:
        segments = group_words_by_speaker(item.words, item.speaker_label)
        if not segments:
            continue
        print(f"{CLEAR_LINE}🔁 Corrección del turno {item.turn_order}:")
        print_segments(segments, prefix="   ")


def on_terminated(client: StreamingClient, event: TerminationEvent):
    print(
        f"\n🔌 Sesión terminada. "
        f"Audio procesado: {event.audio_duration_seconds:.1f}s"
    )


def on_error(client: StreamingClient, error: StreamingError):
    print(f"\n⚠️ Error de AssemblyAI: {error}")


def run_single_mic():
    client = StreamingClient(StreamingClientOptions(api_key=API_KEY))
    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.SpeakerRevision, on_speaker_revision)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)

    client.connect(StreamingParameters(
        speech_model=SPEECH_MODEL,
        sample_rate=SAMPLE_RATE,
        language_codes=["es"],
        speaker_labels=True,
        max_speakers=EXPECTED_SPEAKERS,
        format_turns=True,
    ))

    print(f"🧑‍🤝‍🧑 MODO UN SOLO MICRÓFONO · hasta {EXPECTED_SPEAKERS} personas · modelo {SPEECH_MODEL}")
    print(
        "ℹ️  Con un micro compartido la separación MEJORA con el tiempo y "
        "funciona mejor si hablan por turnos. Si sigue saliendo todo como\n"
        "    una persona, usa el MODO MULTI-MICRÓFONO (un micro por persona) "
        "editando MIC_DEVICES arriba.\n"
    )
    if SAVE_TO_FILE:
        print(f"💾 También se guardará en: {FILE_NAME}\n")

    try:
        client.stream(mic_stream())
    except KeyboardInterrupt:
        print("\n\n⏹️ Deteniendo...")
    finally:
        client.disconnect(terminate=True)


# ══════════════════════════════════════════════════════════════
# 5. Programa principal
# ══════════════════════════════════════════════════════════════

def main():
    enable_utf8_and_ansi()

    if "--list" in sys.argv or "--list-devices" in sys.argv:
        list_input_devices()
        return

    if MIC_DEVICES:
        run_multi_mic(MIC_DEVICES)   # separación garantizada
    else:
        run_single_mic()             # diarización sobre un solo micro


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error fatal: {e}")
        sys.exit(1)
