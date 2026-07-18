from io import BytesIO


def bytes_to_wav(audio_bytes: bytes, sample_rate: int = 16000) -> bytes:
    import soundfile as sf
    import numpy as np
    buffer = BytesIO()
    data = np.frombuffer(audio_bytes, dtype=np.int16)
    sf.write(buffer, data, sample_rate, format="WAV")
    buffer.seek(0)
    return buffer.read()


def resample(audio_bytes: bytes, target_rate: int = 16000) -> bytes:
    import librosa
    import soundfile as sf
    data, sr = sf.read(BytesIO(audio_bytes))
    if sr == target_rate:
        return audio_bytes
    resampled = librosa.resample(data, orig_sr=sr, target_sr=target_rate)
    buffer = BytesIO()
    sf.write(buffer, resampled, target_rate, format="WAV")
    buffer.seek(0)
    return buffer.read()
