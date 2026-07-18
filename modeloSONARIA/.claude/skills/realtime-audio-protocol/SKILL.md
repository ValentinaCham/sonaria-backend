---
name: realtime-audio-protocol
description: Definir e implementar el contrato WebSocket entre una app React Native y un backend Python para audio en tiempo real y eventos de IA (transcripción, hablantes, sonidos, enrolar voz). Úsala SIEMPRE que se diseñe o toque la comunicación app↔backend, el streaming de audio del micrófono del celular al servidor, el formato de los chunks de audio, o el esquema de mensajes de eventos que el backend devuelve al app. Evita que cliente y servidor se desincronicen.
---

# Contrato de audio en tiempo real (App RN ↔ Backend Python)

El celular solo **captura y transmite** audio; el backend Python corre AssemblyAI + SpeechBrain +
YAMNet y **devuelve eventos**. Este es el contrato que ambos lados deben respetar.

## Transporte

- **WebSocket** (`websockets` o FastAPI/Starlette en Python; en RN, `WebSocket` nativo).
- Una conexión por dispositivo/usuario. El backend crea una sesión por conexión.
- Considera `wss://` (TLS) siempre; nunca mandes audio del hogar por `ws://` sin cifrar en producción.

## Audio: app → backend

- Formato: **PCM 16-bit, mono, 16 kHz**, little-endian (lo que espera AssemblyAI y YAMNet).
- Enviar en **frames binarios** de ~50–100 ms (800–1600 muestras = 1600–3200 bytes). No JSON para audio.
- En RN, capturar con un módulo tipo `react-native-live-audio-stream` (entrega buffers PCM) y enviar
  cada buffer como binary frame. Remuestrear a 16 kHz en captura si el device usa otro sample rate.

## Eventos: backend → app (mensajes JSON de texto)

Un campo `type` discrimina. Esquema:

```jsonc
// Transcripción parcial o final con hablante ya resuelto a nombre/Persona N
{ "type": "transcript", "speaker": "Carlos", "speakerId": "A",
  "text": "¿Ya terminaste el informe?", "isFinal": true, "ts": 1737200000 }

// Sonido del hogar detectado (Feature 2)
{ "type": "sound_event", "emoji": "🔔", "message": "Alguien está tocando el timbre.",
  "sound": "Doorbell", "confidence": 0.82, "ts": 1737200005 }

// Estado de una voz aún sin identificar (calentamiento / desconocida)
{ "type": "speaker_pending", "speakerId": "B", "label": "Persona 2", "ts": 1737200006 }

// Confirmación de enrolamiento
{ "type": "enroll_result", "name": "María", "ok": true, "ts": 1737200010 }
```

## Comandos: app → backend (mensajes JSON de texto, aparte del audio binario)

```jsonc
{ "type": "enroll_start", "name": "Carlos" }   // empieza a capturar voz para registrar (Flujo 1.2)
{ "type": "enroll_stop" }                       // termina y guarda el voiceprint
{ "type": "focus_set", "speakers": ["Carlos", "María"] }  // Focus Mode (Flujo 1.4)
{ "type": "sounds_config", "active": ["Doorbell", "Baby cry, infant cry"] }  // Flujo 2.1
```

> Regla: **audio = frames binarios**, **control/eventos = frames de texto JSON**. No mezclar.

## Reconexión y robustez

- El app debe reintentar con backoff exponencial si cae la conexión, y reenviar la config
  (`focus_set`, `sounds_config`) al reconectar (el backend arranca sesión nueva sin estado).
- Latencia objetivo: eventos de transcripción < 1 s; `sound_event` < 1.5 s.
- Heartbeat (`ping`/`pong`) cada ~15 s para detectar conexiones muertas.
- El backend descarta audio si el buffer se atrasa (mejor perder audio viejo que acumular latencia).

## Enrolamiento en caliente (cómo encaja)

`enroll_start` → el backend empieza a acumular audio de la voz objetivo → tras `enroll_stop`
(o ~20 s) calcula el voiceprint (skill `speaker-voiceprint-enrollment`) y responde `enroll_result`.
Desde ese momento los `transcript` de esa voz llegan con `speaker` = el nombre.

## Prueba

Con un cliente WebSocket de prueba, enviar un WAV PCM 16k en frames y verificar que llegan mensajes
`transcript`; enviar `sounds_config` y un clip de timbre y verificar `sound_event`.
