"""
Endpoint WebSocket del canal de colaboración activo (ADR-0003, paso 1).
Sólo transporte: acepta la conexión, hace broadcast de lo que recibe al resto
de la sala del mismo `canvas_id`, y limpia el registro al desconectar.
"""

import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .room_registry import collaboration_room_registry

collaboration_ws_router = APIRouter(tags=["Collaboration"])


@collaboration_ws_router.websocket("/ws/canvas/{canvas_id}/collaboration")
async def canvas_collaboration_websocket(
    websocket: WebSocket,
    canvas_id: str,
    display_name: str | None = Query(default=None),
) -> None:
    peer_id = await collaboration_room_registry.connect(websocket, canvas_id, display_name)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                payload = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                payload = text
            await collaboration_room_registry.broadcast(canvas_id, peer_id, payload)
    except WebSocketDisconnect:
        await collaboration_room_registry.disconnect(canvas_id, peer_id)
    except Exception:  # noqa: BLE001 — cualquier falla del loop debe liberar al peer igual
        await collaboration_room_registry.disconnect(canvas_id, peer_id)
