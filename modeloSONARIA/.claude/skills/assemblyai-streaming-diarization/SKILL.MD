---
name: assemblyai-streaming-diarization
description: Configurar transcripción en vivo con separación de hablantes (diarización) usando AssemblyAI Streaming v3 en Python. Úsala SIEMPRE que el trabajo toque transcripción en tiempo real, "quién habla", speaker_labels, StreamingClient/TurnEvent, diarización en streaming, o cuando varias personas hablen y haya que separarlas. También cuando alguien reporte que "todos salen como una sola persona" / "solo reconoce un hablante". Cubre modelos, parámetros correctos, etiquetas por palabra, calentamiento (PENDING/UNKNOWN) y el patrón multi-micrófono.
---

# Diarización en vivo con AssemblyAI Streaming v3

Receta probada para transcribir en tiempo real y separar hablantes. La referencia
funcional está en `D:\hackaton\streaming_assemblyai.py` (léela antes de tocar código).

## Verdad #1 — la diarización de AssemblyAI es EFÍMERA, no identidad persistente

Devuelve etiquetas `A`, `B`, `C`… **por sesión**. NO reconoce a "Carlos" entre sesiones.
Para identidad persistente (registrar y reconocer una voz por nombre) hace falta un sistema
de voiceprints aparte → usar la skill `speaker-voiceprint-enrollment`.

## Verdad #2 — un micrófono compartido COLAPSA las voces

Verificado por prueba: con audio limpio por turnos, la API separa `A`/`B` bien; pero cuando
las voces llegan **mezcladas en una sola onda** (varias personas por un mismo micro con cruce
de voces), la API mete todo en un solo hablante. **La separación fiable de N personas requiere
N micrófonos = N sesiones** (ver "Patrón multi-micrófono" abajo). Es un límite físico, no un bug.

## Parámetros correctos (`StreamingParameters`)

```python
StreamingParameters(
    speech_model="universal-3-5-pro",   # o "universal-streaming-multilingual" (mejor para ES puro)
    sample_rate=16000,
    language_codes=["es"],              # lista, no string. 'language_code' está deprecado
    speaker_labels=True,                # activa diarización
    max_speakers=N,                     # PISTA: nº real de personas (1-10). Mal valor = fusiona voces
    format_turns=True,                  # turnos formateados/estables
)
```

- Modelos válidos: `universal-3-5-pro`, `universal-streaming-multilingual`, `universal-streaming-english`.
- NO uses `voice_focus` con varias personas: la supresión de ruido se enfoca en la voz más cercana
  y empeora la separación del resto.

## Leer al hablante correctamente

El hablante llega **palabra por palabra** en `event.words[i].speaker`, no solo en
`event.speaker_label` (que es una etiqueta por turno completo). Si dos personas hablan dentro
del mismo turno y solo usas `speaker_label`, todo cae en el hablante dominante. Agrupa por palabra:

```python
def group_words_by_speaker(words, fallback_label):
    segments = []
    for w in words:
        t = w.text.strip()
        if not t: continue
        spk = w.speaker or fallback_label
        if segments and segments[-1][0] == spk:
            segments[-1][1].append(t)
        else:
            segments.append((spk, [t]))
    return [(spk, " ".join(parts)) for spk, parts in segments]
```

Los `word.speaker` solo se rellenan en palabras finales (`end_of_turn`).

## Calentamiento — etiquetas que NO son un hablante

- `universal-3-5-pro`: los primeros turnos pueden llegar con `speaker_label=None`.
- `universal-streaming-multilingual`: usa `PENDING` durante el calentamiento.
- Frases muy cortas ("sí", "ok", <1s de audio): `UNKNOWN`.

Trátalas como "identificando voz…" (no las fuerces a Persona 1). La separación **mejora con el
tiempo**: cuanto más larga la conversación, mejores las etiquetas. Existe el evento
`SpeakerRevision` que corrige turnos anteriores — suscríbete y reimprime la corrección:

```python
client.on(StreamingEvents.SpeakerRevision, on_speaker_revision)
# event.revisions: cada item tiene turn_order, speaker_label y words corregidos
```

## Patrón multi-micrófono (separación GARANTIZADA)

Una sesión `StreamingClient` por micrófono/persona, cada una en su hilo, etiqueta fija por micro.
Como cada persona tiene su propio audio, no importa cuánto se pisen. En cada sesión NO hace falta
`speaker_labels` (la sesión ya es una persona). Ver `run_multi_mic()` en `streaming_assemblyai.py`.
Listar dispositivos: `python streaming_assemblyai.py --list`.

## Windows

- `os.system("")` habilita colores ANSI; `sys.stdout.reconfigure(encoding="utf-8")` evita que los
  emojis/acentos rompan la consola cp1252.

## Cómo cargar la API key

Nunca hardcodear. Orden: env `ASSEMBLYAI_API_KEY` → `assemblyai_key.txt` → `apai.txt`.

## Probadores de referencia (en el scratchpad de la sesión)

- `selftest_diar.py` — transmite audio con 2 voces y reporta si la API separa (1 micro).
- `selftest_multimic.py` — 2 sesiones concurrentes; verifica separación garantizada por micro.
