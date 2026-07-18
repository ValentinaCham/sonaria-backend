from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/sounds")
async def sound_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            result = {"type": "unknown", "message": "", "confidence": 0}
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
