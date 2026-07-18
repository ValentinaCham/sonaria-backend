"""
voice_features.py
─────────────────
Análisis del "diagrama de la voz" EN TIEMPO REAL y clasificación de la voz de la
persona a partir de las ondas sonoras — todo con NumPy/SciPy (compatibles con
Python 3.14; torch/SpeechBrain no instalan aquí).

Por cada ventana corta de audio se calcula:
  • Espectrograma MEL (para dibujar el diagrama de la voz).
  • Tono / frecuencia fundamental F0 (autocorrelación).
  • Brillo (centroide espectral).
  • MFCC (coeficientes cepstrales) → "huella de voz" compacta.

Con la huella MFCC + el tono, un clasificador ONLINE agrupa las voces:
compara con las voces ya vistas (similitud coseno) y, si es suficientemente
parecida, la asigna a esa voz; si no, crea una voz nueva (open-set). Así se
"clasifica la voz de la persona" a partir del diagrama, sin entrenamiento previo.
"""

from __future__ import annotations

import logging
import time

import numpy as np
from scipy.fft import dct

logger = logging.getLogger(__name__)


def _hz_to_mel(f: float) -> float:
    return 2595.0 * np.log10(1.0 + f / 700.0)


def _mel_to_hz(m):
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def _mel_filterbank(sr: int, n_fft: int, n_mels: int, fmin=60.0, fmax=None) -> np.ndarray:
    fmax = min(fmax or sr / 2, sr / 2)
    mels = np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    freqs = _mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * freqs / sr).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(1, n_mels + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        c = max(c, l + 1)
        r = max(r, c + 1)
        for k in range(l, c):
            fb[m - 1, k] = (k - l) / max(c - l, 1)
        for k in range(c, min(r, n_fft // 2 + 1)):
            fb[m - 1, k] = (r - k) / max(r - c, 1)
    return fb


class VoiceClassifier:
    """Agrupa voces online por huella MFCC (coseno) + tono, open-set."""

    def __init__(self, sim_threshold: float = 0.62, max_voices: int = 8):
        self.sim_threshold = sim_threshold
        self.max_voices = max_voices
        self._centroids: list[np.ndarray] = []
        self._pitches: list[float] = []
        self._counts: list[int] = []

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        n = float(np.linalg.norm(v))
        return v / n if n > 1e-8 else v

    def classify(self, embedding: np.ndarray, pitch: float) -> tuple[int, float, bool]:
        emb = self._norm(embedding)
        best_id, best_sim = -1, -1.0
        for i, c in enumerate(self._centroids):
            sim = float(np.dot(emb, c))
            # El tono ayuda a no fusionar voces graves con agudas: una diferencia
            # grande de F0 es una señal fuerte de que es OTRA persona.
            if pitch > 0 and self._pitches[i] > 0:
                ratio = max(pitch, self._pitches[i]) / min(pitch, self._pitches[i])
                if ratio > 1.5:
                    sim -= 0.35
                elif ratio > 1.3:
                    sim -= 0.15
            if sim > best_sim:
                best_sim, best_id = sim, i

        if best_id >= 0 and best_sim >= self.sim_threshold:
            n = self._counts[best_id]
            self._centroids[best_id] = self._norm(
                (self._centroids[best_id] * n + emb) / (n + 1)
            )
            if pitch > 0:
                pw = self._pitches[best_id]
                self._pitches[best_id] = pitch if pw <= 0 else 0.9 * pw + 0.1 * pitch
            self._counts[best_id] = n + 1
            return best_id, best_sim, False

        if len(self._centroids) < self.max_voices:
            self._centroids.append(emb)
            self._pitches.append(pitch)
            self._counts.append(1)
            return len(self._centroids) - 1, 1.0, True

        # Lleno: asigna a la más parecida aunque no supere el umbral.
        return best_id, max(best_sim, 0.0), False


class VoiceAnalyzer:
    def __init__(
        self,
        sample_rate: int = 16000,
        n_fft: int = 512,
        n_mels: int = 40,
        window_s: float = 0.15,
    ):
        self.sr = sample_rate
        self.n_fft = n_fft
        self.n_mels = n_mels
        self.hop = 160
        self.win = int(window_s * sample_rate)
        self._buf = np.zeros(0, dtype=np.float32)
        self._fb = _mel_filterbank(sample_rate, n_fft, n_mels)
        self._hann = np.hanning(n_fft).astype(np.float32)
        self._freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate).astype(np.float32)
        self._mel_max = 1e-6
        self._noise_rms = 0.005
        self._clf = VoiceClassifier()

    # ──────────────────────────────────────────────────────────
    def _pitch(self, x: np.ndarray) -> float:
        x = x - float(np.mean(x))
        rms = float(np.sqrt(np.mean(x * x)))
        if rms < 1e-3:
            return 0.0
        corr = np.correlate(x, x, mode="full")[x.size - 1:]
        if corr[0] <= 0:
            return 0.0
        min_lag = max(int(self.sr / 350), 1)
        max_lag = min(int(self.sr / 70), corr.size - 1)
        if max_lag <= min_lag:
            return 0.0
        seg = corr[min_lag:max_lag]
        lag = min_lag + int(np.argmax(seg))
        if corr[lag] < 0.3 * corr[0]:
            return 0.0
        return float(self.sr / lag)

    def _analyze(self, w: np.ndarray) -> dict:
        # Potencia media por frames dentro de la ventana.
        power = np.zeros(self.n_fft // 2 + 1, dtype=np.float32)
        frames = 0
        for i in range(0, max(w.size - self.n_fft, 0) + 1, self.hop):
            fr = w[i:i + self.n_fft]
            if fr.size < self.n_fft:
                break
            spec = np.fft.rfft(fr * self._hann)
            power += (np.abs(spec) ** 2).astype(np.float32)
            frames += 1
        if frames == 0:
            fr = np.pad(w, (0, max(self.n_fft - w.size, 0)))[: self.n_fft]
            spec = np.fft.rfft(fr * self._hann)
            power = (np.abs(spec) ** 2).astype(np.float32)
            frames = 1
        power /= frames

        mel_power = self._fb @ power                      # (n_mels,)
        self._mel_max = max(self._mel_max * 0.999, float(mel_power.max()))
        p_norm = mel_power / (self._mel_max + 1e-9)
        mel_db = 10.0 * np.log10(p_norm + 1e-6)
        mel_disp = np.clip(1.0 + mel_db / 60.0, 0.0, 1.0)  # 0..1 para dibujar

        rms = float(np.sqrt(np.mean(w * w)))
        centroid = float(np.sum(self._freqs * np.sqrt(power)) / (np.sum(np.sqrt(power)) + 1e-9))
        pitch = self._pitch(w)

        # MFCC (huella) desde el log-mel.
        logmel = np.log(mel_power + 1e-6)
        mfcc = dct(logmel, type=2, norm="ortho")[1:13]

        # ¿Hay voz? (energía por encima del piso de ruido)
        if rms < self._noise_rms * 1.8:
            self._noise_rms = 0.95 * self._noise_rms + 0.05 * rms
        is_speech = rms > max(self._noise_rms * 3.0, 0.012)

        voice_id = None
        confidence = 0.0
        is_new = False
        if is_speech:
            vid, conf, is_new = self._clf.classify(np.asarray(mfcc, np.float32), pitch)
            voice_id, confidence = int(vid), float(conf)

        return {
            "type": "voice_analysis",
            "mel": [round(float(v), 3) for v in mel_disp],
            "rms": round(rms, 4),
            "pitch_hz": round(pitch, 1),
            "centroid_hz": round(centroid, 1),
            "is_speech": bool(is_speech),
            "voice_id": voice_id,
            "voice_name": (f"Voz {voice_id + 1}" if voice_id is not None else None),
            "confidence": round(confidence, 3),
            "is_new_voice": bool(is_new),
            "timestamp_ms": int(time.time() * 1000),
        }

    def feed(self, pcm_bytes: bytes) -> list[dict]:
        if not pcm_bytes:
            return []
        try:
            x = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if x.size == 0:
                return []
            self._buf = np.concatenate([self._buf, x])
            out: list[dict] = []
            while self._buf.shape[0] >= self.win:
                w = self._buf[: self.win]
                self._buf = self._buf[self.win:]
                out.append(self._analyze(w))
            return out
        except Exception as exc:
            logger.warning("Fallo en VoiceAnalyzer: %s", exc)
            return []
