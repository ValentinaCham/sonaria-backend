# ============================================================================
# LigaCenter Backend - Multi-stage Dockerfile optimizado
# ============================================================================
# Stage 1 (deps): instala torch CPU (~200MB) + speechbrain + resto
# Stage 2 (runtime): copia deps instaladas + codigo, ~1.5GB total
# Pre-descarga modelo ECAPA-TDNN al build time (sino tarda 30-60s en startup)
# ============================================================================

# ─── Stage 1: deps + modelo ───────────────────────────────────────────────
FROM python:3.12-slim AS deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Torch CPU-only (reduce ~1.8GB vs full torch)
RUN pip install --no-cache-dir \
    torch==2.13.0+cpu \
    torchaudio==2.11.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Resto de deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# SpeechBrain + ECAPA-TDNN (pre-descargar el modelo al build time)
RUN pip install --no-cache-dir speechbrain==1.1.0 && \
    python -c "from speechbrain.inference.speaker import SpeakerRecognition; \
               SpeakerRecognition.from_hparams( \
                   source='speechbrain/spkrec-ecapa-voxceleb', \
                   savedir='/app/pretrained_models/spkrec-ecapa-voxceleb')" \
    && echo "OK: modelo ECAPA-TDNN pre-descargado"

# ─── Stage 2: runtime ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar todo el sitio de paquetes Python del stage 1
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copiar modelo pre-descargado
COPY --from=deps /app/pretrained_models /app/pretrained_models

# Copiar codigo
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
