from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, conversations, events, sounds, voices
from app.websocket import audio_stream, sound_stream


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(events.router)
app.include_router(audio_stream.router)
app.include_router(sound_stream.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
