"""
speech_enhancer.py
──────────────────
Limpieza de audio EN TIEMPO REAL antes de enviarlo a la transcripción.

Objetivo: quitar el sonido del ambiente (ruido de fondo estacionario, zumbidos,
ventiladores, tráfico lejano, etc.) y quedarse con la VOZ, para que AssemblyAI
transcriba mejor y separe mejor a las personas.

Técnica (100% NumPy/SciPy, sin dependencias nativas frágiles):
  1. Filtro paso-alto  → elimina retumbe/zumbido de baja frecuencia (< ~80 Hz).
  2. Spectral gating    → resta un perfil de ruido estimado adaptativamente
                          (misma idea que la librería `noisereduce`), atenuando
                          las frecuencias dominadas por ruido y conservando la voz.
  3. VAD por energía    → cuando NADIE habla (solo ambiente), atenúa fuerte el
                          fragmento; así "solo se reconoce el audio de voz".

Es agnóstico al hablante: NO separa ni mezcla voces, por lo que el soporte
multi-persona de AssemblyAI (diarización) se mantiene intacto — varias personas
a la vez siguen funcionando.

Cada conexión WebSocket usa su propia instancia (mantiene estado del filtro y del
perfil de ruido). El procesamiento es en streaming (overlap-add) para no cortar
palabras entre chunks.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi

logger = logging.getLogger(__name__)


class SpeechEnhancer:
    def __init__(
        self,
        sample_rate: int = 16000,
        n_fft: int = 512,
        hop: int = 128,
        strength: float = 0.85,
        enable_denoise: bool = True,
        enable_highpass: bool = True,
        enable_vad_gate: bool = True,
        highpass_hz: float = 80.0,
    ):
        self.sr = sample_rate
        self.n_fft = n_fft
        self.hop = hop
        self.enable_denoise = enable_denoise
        self.enable_highpass = enable_highpass
        self.enable_vad_gate = enable_vad_gate

        # strength 0..1 → controla cuánta reducción de ruido aplicar.
        strength = float(max(0.0, min(1.0, strength)))
        self._over_sub = 1.0 + 2.0 * strength      # factor de sobre-sustracción (1..3)
        self._spectral_floor = 0.15 * (1.0 - strength) + 0.02  # piso espectral

        # ── Ventana de análisis/síntesis (WOLA con raíz de Hann) ──
        hann = np.hanning(n_fft + 1)[:-1].astype(np.float32)  # periódica
        self._awin = np.sqrt(np.maximum(hann, 0.0)).astype(np.float32)
        self._wsq = (self._awin * self._awin).astype(np.float32)

        # ── Buffers de streaming ──
        self._inbuf = np.zeros(0, dtype=np.float32)
        self._olap = np.zeros(n_fft - hop, dtype=np.float32)   # señal acumulada
        self._wlap = np.zeros(n_fft - hop, dtype=np.float32)   # ventanas acumuladas

        # ── Estimación de ruido ──
        self._noise_mag: np.ndarray | None = None
        self._noise_frames = 0
        self._init_frames = 30          # ~0.24 s iniciales se asumen ambiente
        self._noise_ema = 0.95          # suavizado del perfil de ruido
        self._prev_gain: np.ndarray | None = None
        self._gain_ema = 0.6            # suavizado temporal de la ganancia

        # ── VAD (detección de voz por SNR con "hangover") ──
        self._vad_on_db = 4.0           # entra a "voz" sobre este SNR (dB)
        self._vad_off_db = 1.5          # sale de "voz" bajo este SNR (dB)
        self._hangover = 0
        self._hangover_frames = 12      # ~0.1 s de cola para no cortar finales
        self._vad_atten = 0.08          # atenuación aplicada al ambiente puro

        # ── Filtro paso-alto ──
        if enable_highpass:
            self._hp_b, self._hp_a = butter(
                2, highpass_hz / (sample_rate / 2.0), btype="high"
            )
            self._hp_zi = (lfilter_zi(self._hp_b, self._hp_a) * 0.0).astype(np.float64)
        else:
            self._hp_b = self._hp_a = self._hp_zi = None

    # ──────────────────────────────────────────────────────────
    def _compute_gain(self, mag: np.ndarray) -> np.ndarray:
        noise_power_mean = 1e-10
        frame_power = float(np.mean(mag * mag)) + 1e-10

        if self._noise_mag is None:
            self._noise_mag = mag.copy()
            self._noise_frames = 1
            return np.ones_like(mag)

        noise_power_mean = float(np.mean(self._noise_mag * self._noise_mag)) + 1e-10
        snr_db = 10.0 * np.log10(frame_power / noise_power_mean)

        # ── VAD con histéresis + hangover ──
        is_speech = False
        if snr_db >= self._vad_on_db:
            self._hangover = self._hangover_frames
            is_speech = True
        elif snr_db > self._vad_off_db and self._hangover > 0:
            is_speech = True
        if self._hangover > 0:
            self._hangover -= 1
            is_speech = True

        # ── Actualizar perfil de ruido en tramos SIN voz ──
        if self._noise_frames < self._init_frames:
            a = 1.0 / (self._noise_frames + 1)
            self._noise_mag = (1 - a) * self._noise_mag + a * mag
            self._noise_frames += 1
        elif not is_speech:
            self._noise_mag = (
                self._noise_ema * self._noise_mag + (1 - self._noise_ema) * mag
            )

        if not self.enable_denoise:
            gain = np.ones_like(mag)
        else:
            # ── Sustracción espectral de potencia (tipo Wiener) ──
            ratio = (self._noise_mag * self._noise_mag) / (mag * mag + 1e-10)
            gain = 1.0 - self._over_sub * ratio
            gain = np.clip(gain, self._spectral_floor, 1.0)
            gain = np.sqrt(gain)
            # Suavizado en frecuencia (reduce "ruido musical")
            gain = np.convolve(gain, np.array([0.25, 0.5, 0.25], np.float32), mode="same")
            # Suavizado temporal
            if self._prev_gain is not None:
                gain = self._gain_ema * self._prev_gain + (1 - self._gain_ema) * gain
            self._prev_gain = gain

        # ── Puerta VAD: atenúa fuerte cuando es solo ambiente ──
        if self.enable_vad_gate and not is_speech:
            gain = gain * self._vad_atten

        return gain.astype(np.float32)

    # ──────────────────────────────────────────────────────────
    def process_pcm(self, pcm_bytes: bytes) -> bytes:
        """Recibe PCM int16 mono y devuelve PCM int16 mono limpio."""
        if not pcm_bytes:
            return pcm_bytes
        try:
            x = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if x.size == 0:
                return pcm_bytes

            if self.enable_highpass and self._hp_b is not None:
                x, self._hp_zi = lfilter(self._hp_b, self._hp_a, x, zi=self._hp_zi)
                x = x.astype(np.float32)

            self._inbuf = np.concatenate([self._inbuf, x])
            out_chunks: list[np.ndarray] = []

            while self._inbuf.shape[0] >= self.n_fft:
                frame = self._inbuf[: self.n_fft] * self._awin
                spec = np.fft.rfft(frame)
                mag = np.abs(spec).astype(np.float32)
                gain = self._compute_gain(mag)
                y = np.fft.irfft(spec * gain, n=self.n_fft).astype(np.float32)
                y = y * self._awin

                acc = np.zeros(self.n_fft, dtype=np.float32)
                wacc = np.zeros(self.n_fft, dtype=np.float32)
                acc[: self._olap.shape[0]] += self._olap
                wacc[: self._wlap.shape[0]] += self._wlap
                acc += y
                wacc += self._wsq

                finalized = acc[: self.hop] / np.maximum(wacc[: self.hop], 1e-8)
                out_chunks.append(finalized)

                self._olap = acc[self.hop :]
                self._wlap = wacc[self.hop :]
                self._inbuf = self._inbuf[self.hop :]

            if not out_chunks:
                # Aún no hay una ventana completa: no emitir audio todavía.
                return b""

            y_all = np.concatenate(out_chunks)
            y_all = np.clip(y_all, -1.0, 1.0)
            return (y_all * 32767.0).astype(np.int16).tobytes()
        except Exception as exc:  # nunca romper el stream por un fallo de limpieza
            logger.warning("Fallo en SpeechEnhancer, se pasa audio sin limpiar: %s", exc)
            return pcm_bytes
