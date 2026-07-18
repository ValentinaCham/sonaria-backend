---
name: speaker-voiceprint-enrollment
description: Registrar y reconocer voces por NOMBRE de forma persistente entre sesiones (voiceprints) usando SpeechBrain ECAPA-TDNN en Python. Úsala SIEMPRE que haya que "Guardar voz", asociar una voz a un nombre (Carlos, María), reconocer a la misma persona en futuras conversaciones, mostrar el nombre en vez de "Speaker 2", o priorizar voces conocidas. Cubre enrolamiento, embeddings 192-d, match por similitud coseno con umbral, hablantes desconocidos (open-set) y cómo mapear las etiquetas A/B de AssemblyAI a la identidad real.
---

# Voiceprints: registrar y reconocer voces por nombre (SpeechBrain ECAPA-TDNN)

Rellena lo que AssemblyAI NO hace: **identidad persistente**. AssemblyAI da `A`/`B` efímeros por
sesión; aquí convertimos ese audio en un vector de voz estable y lo comparamos con voces guardadas.

## Modelo

`speechbrain/spkrec-ecapa-voxceleb` (ECAPA-TDNN) → embedding de **192 dimensiones** por segmento de
voz. Estado del arte para verificación de hablante, corre en CPU aceptablemente.

```python
from speechbrain.inference.speaker import EncoderClassifier
import torch, torchaudio

enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                     savedir="models/ecapa")

def embed(wav_16k_mono: torch.Tensor) -> torch.Tensor:
    # wav: tensor float32 [1, N] a 16 kHz mono, normalizado a [-1,1]
    e = enc.encode_batch(wav_16k_mono).squeeze()   # [192]
    return e / e.norm()                            # normaliza para coseno
```

## Enrolar una voz (Flujo 1.2 "Guardar voz")

1. Capturar **≥ 20 s** de la voz de la persona (idealmente varios fragmentos → promediar embeddings).
2. Calcular el embedding, promediar y re-normalizar → ese es el **voiceprint**.
3. Guardar `{nombre: [floats 192]}` en disco (JSON/npz/SQLite). Ejemplo mínimo:

```python
import json, numpy as np
def save_voiceprint(name, emb, path="voiceprints.json"):
    db = json.load(open(path)) if os.path.exists(path) else {}
    db[name] = emb.tolist()
    json.dump(db, open(path, "w"))
```

## Reconocer (Flujo 1.3) — match por coseno con umbral

```python
def identify(emb, db, threshold=0.25):
    best_name, best_sim = None, -1.0
    for name, ref in db.items():
        sim = float(np.dot(emb, np.array(ref)))   # ambos normalizados → coseno
        if sim > best_sim:
            best_name, best_sim = name, sim
    return best_name if best_sim >= threshold else None   # None = desconocido (open-set)
```

- Umbral orientativo con ECAPA normalizado: ~**0.25–0.35** de coseno. Calíbralo con voces reales:
  sube si hay falsos positivos, baja si no reconoce a personas ya enroladas.
- **Open-set**: si nadie supera el umbral → voz desconocida → mostrar "Persona N" (numerar por orden
  de aparición) y ofrecer "Guardar voz".

## Puente clave: mapear AssemblyAI `A/B` → nombre

AssemblyAI dice "el turno T es del hablante A". Nosotros no sabemos quién es A hasta oírlo:

1. Por cada turno final, extraer el trozo de audio de ese turno (usar `word.start`/`word.end` en ms).
2. Calcular su embedding e `identify()` contra la base de voiceprints.
3. Mantener un mapa **por sesión** `sessionSpeaker(A) → identidad` (con voto mayoritario/EMA para
   estabilizar): la primera vez que A se identifica como "Carlos", fijar A→Carlos el resto de la sesión.
4. Si A no matchea a nadie → "Persona N" y permitir enrolarlo en caliente.

> Requiere retener el audio PCM del turno. En el pipeline, bufferiza el audio junto con los
> timestamps de las palabras para poder recortar el segmento del hablante.

## Priorización

Marcar identidades enroladas como "confianza" → el UI puede resaltarlas o alimentarlas al Focus Mode
(ver `accessible-deaf-ui-patterns`).

## Dependencias

`pip install speechbrain torch torchaudio`. Primera ejecución descarga el modelo (~80 MB) a `savedir`.

## Prueba

Enrola dos voces distintas (p.ej. dos clips TTS), luego pásale un tercer clip de una de ellas y
confirma que `identify()` devuelve el nombre correcto y que una voz no enrolada devuelve `None`.
