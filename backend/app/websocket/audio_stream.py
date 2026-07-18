from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            result = {"speaker": "Desconocido", "text": "", "confidence": 0}
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
