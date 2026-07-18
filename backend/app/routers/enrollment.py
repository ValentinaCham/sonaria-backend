"""
Endpoint de Enrollment (Registro de Voz de la Dueña)
------------------------------------------------------
Uso:
  POST /enrollment/voice
  Content-Type: multipart/form-data
  Body: file = <archivo .wav>

Este endpoint recibe el audio de la dueña, lo sube a Supabase Storage,
y recarga el modelo de biometría en memoria.
"""

import io
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.voice_biometrics import voice_biometrics
from supabase import create_client

router = APIRouter(prefix="/enrollment", tags=["enrollment"])


@router.post("/voice")
async def enroll_owner_voice(file: UploadFile = File(...)):
    """
    Sube el audio de la dueña a Supabase Storage y recarga
    el modelo de biometría en memoria.
    """
    if not file.filename.lower().endswith((".wav", ".mp3", ".m4a", ".ogg")):
        raise HTTPException(status_code=400, detail="Formato de audio no soportado. Usa .wav, .mp3, .m4a o .ogg")

    audio_bytes = await file.read()
    
    if len(audio_bytes) < 10_000:
        raise HTTPException(status_code=400, detail="El audio es demasiado corto. Graba al menos 5 segundos.")

    # Subir a Supabase Storage
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        supabase.storage.from_(settings.OWNER_VOICE_BUCKET).upload(
            path=settings.OWNER_VOICE_PATH,
            file=audio_bytes,
            file_options={"content-type": file.content_type or "audio/wav", "upsert": "true"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subiendo a Supabase: {str(e)}")

    # Recargar biometría en memoria con el nuevo audio
    try:
        voice_biometrics.initialize()
    except Exception as e:
        # No es fatal — el audio quedó guardado en Supabase
        return JSONResponse(
            status_code=207,
            content={
                "message": "Audio subido correctamente, pero hubo un error al cargar el modelo en memoria. El servidor lo intentará al próximo reinicio.",
                "error": str(e)
            }
        )

    return {
        "message": "✅ Voz de la dueña registrada correctamente.",
        "bucket": settings.OWNER_VOICE_BUCKET,
        "path": settings.OWNER_VOICE_PATH,
        "biometrics_ready": voice_biometrics.is_ready,
    }


@router.get("/status")
def enrollment_status():
    """Verifica si el modelo de biometría está listo y si hay audio de la dueña."""
    import os
    audio_exists = os.path.exists(voice_biometrics.owner_audio_path)
    return {
        "biometrics_ready": voice_biometrics.is_ready,
        "owner_audio_downloaded": audio_exists,
        "owner_audio_size_kb": round(os.path.getsize(voice_biometrics.owner_audio_path) / 1024, 1) if audio_exists else 0,
        "bucket": settings.OWNER_VOICE_BUCKET,
        "path": settings.OWNER_VOICE_PATH,
    }
