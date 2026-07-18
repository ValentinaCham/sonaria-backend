import os
import tempfile
import asyncio
from pathlib import Path
from supabase import create_client, Client
from app.config import settings

# Attempt to import SpeechBrain (will fail if not installed yet)
try:
    from speechbrain.inference.speaker import SpeakerRecognition
except ImportError:
    SpeakerRecognition = None

class VoiceBiometricsService:
    def __init__(self):
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        self.owner_audio_path = "/tmp/owner_voice.wav"
        self.verification_model = None
        self.is_ready = False
        
    def download_owner_audio(self):
        print(f"Descargando audio de la dueña desde Supabase (Bucket: {settings.OWNER_VOICE_BUCKET}, Path: {settings.OWNER_VOICE_PATH})...")
        try:
            res = self.supabase.storage.from_(settings.OWNER_VOICE_BUCKET).download(settings.OWNER_VOICE_PATH)
            with open(self.owner_audio_path, "wb") as f:
                f.write(res)
            print("✅ Audio de la dueña descargado correctamente.")
            return True
        except Exception as e:
            print(f"⚠️ Error descargando audio de la dueña: {e}")
            return False

    def load_model(self):
        if SpeakerRecognition is None:
            print("⚠️ SpeechBrain no está instalado. Ejecuta: pip install speechbrain torch torchaudio")
            return
            
        print("Cargando modelo de biometría de voz (ECAPA-TDNN)...")
        # Esto descargará el modelo de HuggingFace la primera vez
        self.verification_model = SpeakerRecognition.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb", 
            savedir="pretrained_models/spkrec-ecapa-voxceleb"
        )
        self.is_ready = True
        print("✅ Modelo de biometría cargado en memoria.")

    def initialize(self):
        if self.download_owner_audio():
            self.load_model()
            
    def verify_speaker(self, audio_bytes: bytes, sample_rate: int = 16000) -> bool:
        """
        Toma bytes PCM en bruto a 16kHz, los guarda temporalmente y los compara.
        Retorna True si coincide con la dueña.
        """
        if not self.is_ready or not self.verification_model:
            return False
            
        try:
            # Guardamos los bytes en crudo a un .wav (como el modelo de SpeechBrain soporta wav)
            # Primero importamos soundfile para crear un wav válido desde raw bytes
            import soundfile as sf
            import numpy as np
            
            # Convertimos bytes raw (int16) a numpy array (float32)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                tmp_path = tmp_audio.name
                
            sf.write(tmp_path, audio_array, sample_rate)
            
            # Verificamos
            score, prediction = self.verification_model.verify_files(self.owner_audio_path, tmp_path)
            os.remove(tmp_path)
            
            # prediction es un tensor booleano tensor([True]) o tensor([False])
            # score es un tensor con la similitud
            is_match = prediction.item()
            print(f"🔎 Biometría: Score {score.item():.2f} -> Match? {is_match}")
            
            return is_match
            
        except Exception as e:
            print(f"⚠️ Error en biometría: {e}")
            return False

voice_biometrics = VoiceBiometricsService()
