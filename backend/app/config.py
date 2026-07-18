from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DEEPGRAM_API_KEY: str = ""
    ASSEMBLYAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    JWT_SECRET: str = "default-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PORT: int = 8000
    UPLOAD_DIR: str = "uploads"

    # Permite obtener un token de prueba sin base de datos (solo para desarrollo/demo).
    ALLOW_DEV_LOGIN: bool = True

    # ── Limpieza de audio en tiempo real (antes de transcribir) ──
    ENABLE_AUDIO_CLEANING: bool = True      # reducción de ruido + VAD
    NOISE_REDUCTION_STRENGTH: float = 0.85  # 0.0 (suave) .. 1.0 (agresivo)
    ENABLE_VAD_GATE: bool = True            # atenúa cuando solo hay ambiente
    ENABLE_HIGHPASS: bool = True            # filtra retumbe de baja frecuencia

    # ── Análisis + clasificación de voz (diagrama de voz) ──
    ENABLE_VOICE_ANALYSIS: bool = True      # espectrograma + F0 + MFCC + clasificación

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
