from contextlib import asynccontextmanager
from pathlib import Path
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import auth, conversations, events, sounds, upload, voices, enrollment
from app.websocket import audio_stream, sound_stream

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    # Inicializar biometría en background (descarga modelo y audio de Supabase)
    # Lo corremos en un thread para no bloquear el startup de FastAPI
    threading.Thread(target=voice_biometrics.initialize, daemon=True).start()
    yield


app = FastAPI(title="Inclusive AI Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(voices.router)
app.include_router(conversations.router)
app.include_router(sounds.router)
app.include_router(upload.router)
app.include_router(events.router)
app.include_router(audio_stream.router)
app.include_router(sound_stream.router)


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# ── Frontend de prueba (SONARIA Web Demo) ────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def frontend_index():
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"status": "ok", "message": "SONARIA backend running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

