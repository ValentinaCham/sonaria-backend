---
name: ambient-sound-detection
description: Detectar sonidos importantes del hogar en tiempo real (timbre, alarma de humo, microondas, hervidor, perro ladrando, bebé llorando, golpes en la puerta) usando YAMNet/AudioSet en Python, y convertirlos en notificaciones con contexto. Úsala SIEMPRE que el trabajo toque "AI Ambient Sound Assistant", detección/clasificación de sonidos ambientales, monitoreo de sonidos del hogar, o alertas para personas con discapacidad auditiva sobre lo que suena a su alrededor. Cubre carga del modelo, ventanas, mapeo de clases AudioSet a eventos del hogar, umbrales, antirrebote y mensaje contextual.
---

# Detección de sonidos del hogar en tiempo real (YAMNet)

Base de la Feature 2. Escucha el ambiente e identifica sonidos relevantes para avisar al usuario
qué está ocurriendo, con contexto ("Alguien está tocando el timbre"), no solo "hubo un sonido".

## Modelo

**YAMNet** (Google, AudioSet): clasifica **521 clases** de audio. Corre local en tiempo real,
ligero (MobileNet). Entrada: audio mono **16 kHz** float32 en `[-1, 1]`.

```python
import tensorflow_hub as hub, numpy as np, csv
yamnet = hub.load("https://tfhub.dev/google/yamnet/1")
# nombres de clase
class_map = list(csv.reader(open(yamnet.class_map_path().numpy().decode())))
CLASSES = [row[2] for row in class_map[1:]]   # índice → nombre AudioSet

def classify(wav_16k_mono_float32):
    scores, _, _ = yamnet(wav_16k_mono_float32)   # scores: [frames, 521]
    mean = scores.numpy().mean(axis=0)            # promedio de la ventana
    return mean                                   # vector de 521 probabilidades
```

Para TFLite/on-device existe la variante `yamnet.tflite`; aquí (backend Python) usa el modelo de TF-Hub.

## Ventanas

Procesa ventanas de **~1 s** (buffer deslizante de audio del micro). YAMNet internamente usa marcos
de 0.96 s; una ventana de 1s por evaluación va bien para latencia baja.

## Mapa AudioSet → eventos del hogar (Flujo 2.1)

Filtra las 521 clases a las relevantes y agrúpalas en eventos con mensaje contextual:

```python
HOME_SOUNDS = {
    "Doorbell":        ("🔔", "Alguien está tocando el timbre."),
    "Ding-dong":       ("🔔", "Alguien está tocando el timbre."),
    "Smoke detector, smoke alarm": ("🚨", "La alarma de humo se activó."),
    "Fire alarm":      ("🚨", "Suena la alarma de incendios."),
    "Microwave oven":  ("🍳", "El microondas está sonando."),
    "Kettle whistle":  ("🫖", "El hervidor está listo."),
    "Boiling":         ("🫖", "El agua está hirviendo."),
    "Dog":             ("🐶", "El perro está ladrando."),
    "Bark":            ("🐶", "El perro está ladrando."),
    "Baby cry, infant cry": ("👶", "El bebé está llorando."),
    "Knock":           ("🚪", "Están tocando la puerta."),
    "Telephone bell ringing": ("📞", "Está sonando el teléfono."),
}
```

El usuario elige cuáles monitorear (Flujo 2.1) → filtra el dict a los activos.

## Detección + umbral + antirrebote

```python
THRESHOLD = 0.4          # confianza mínima (calibrar por clase)
COOLDOWN_S = 8           # no repetir el mismo evento dentro de esta ventana
last_fired = {}

def detect(mean_scores, active_sounds, now):
    events = []
    for cls, (emoji, msg) in active_sounds.items():
        idx = CLASS_INDEX.get(cls)
        if idx is None: continue
        if mean_scores[idx] >= THRESHOLD and now - last_fired.get(cls, 0) > COOLDOWN_S:
            last_fired[cls] = now
            events.append({"emoji": emoji, "message": msg, "class": cls,
                           "confidence": float(mean_scores[idx])})
    return events
```

- **Antirrebote (cooldown)** evita spamear: un timbre que suena 3s no debe generar 30 notificaciones.
- Umbrales por-clase: alarmas conviene bajarlas (seguridad, mejor falso positivo que perderla);
  sonidos ruidosos comunes súbelos.

## Salida

Cada evento se emite al app como mensaje `sound_event` (ver skill `realtime-audio-protocol`) para
que genere notificación visual + **vibración distintiva por tipo** (ver `accessible-deaf-ui-patterns`).
Guarda también el evento en el historial (para el asistente de contexto).

## Corre en paralelo a la conversación

El mismo audio del micro alimenta a la vez la transcripción (AssemblyAI) y a YAMNet. En el backend,
duplica el stream de audio a dos consumidores (transcripción y detección de sonidos).

## Dependencias

`pip install tensorflow tensorflow_hub`. Alternativa más ligera: `tflite-runtime` + `yamnet.tflite`.

## Prueba

Reproduce clips de timbre/alarma/ladrido y confirma que se dispara el evento correcto una sola vez
(no repetido), y que un sonido no monitoreado no dispara nada.
