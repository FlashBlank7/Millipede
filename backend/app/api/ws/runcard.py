import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.infra.eventbus.redis_bus import subscribe, runcard_channel, project_channel

router = APIRouter()


@router.websocket("/ws/runcard/{runcard_id}")
async def ws_runcard(websocket: WebSocket, runcard_id: uuid.UUID):
    await websocket.accept()
    try:
        async for event in subscribe(runcard_channel(str(runcard_id))):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/project/{project_id}")
async def ws_project(websocket: WebSocket, project_id: uuid.UUID):
    await websocket.accept()
    try:
        async for event in subscribe(project_channel(str(project_id))):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
