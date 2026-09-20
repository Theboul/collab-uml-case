"""
Endpoint WebSocket del canal de colaboración activo (ADR-0003, paso 1).
Sólo transporte: acepta la conexión, hace broadcast de los mensajes válidos al resto
de la sala del mismo `canvas_id`, y limpia el registro al desconectar. Lo que una
sesión puede enviar (tipos, campos, tamaño, frecuencia) está en `schemas.py` y
`rate_limit.py`; cualquier otra cosa se descarta o cierra la conexión.

Antes de aceptar el handshake se resuelve el rol del solicitante sobre el
lienzo (mismo `resolver_rol` que usa la API HTTP) — si no es ANFITRION ni
COLABORADOR, la conexión se cierra sin llegar a `accept()` ni asignarle
peer_id (nunca entra a la sala).

La sesión de DB para ese chequeo se abre y cierra manualmente en un bloque
acotado (`async with async_session_factory()`) en vez de inyectarse vía
`Depends()` a nivel del handler: un `Depends()` de sesión en un endpoint
`@websocket` queda abierto durante TODA la vida de la conexión (no solo la
duración de la request, como en un endpoint HTTP normal), lo que agota el
pool de conexiones con pocos WS concurrentes de larga duración.
"""

import contextlib
import json

from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasRepository
from backend_case.app.shared.db.base import async_session_factory
from backend_case.app.shared.security.dependencies import (
    get_current_user_optional_ws,
    get_ws_bearer_token,
    ws_accept_subprotocol,
)
from fastapi import APIRouter, Query, WebSocket

from core.uml_domain.exceptions import CanvasNoEncontrado

from .rate_limit import MAX_MESSAGES_PER_SECOND, TokenBucket
from .room_registry import collaboration_room_registry
from .schemas import InvalidClientMessageError, InvalidMessageFieldsError, parse_client_message

collaboration_ws_router = APIRouter(tags=["Collaboration"])

WS_FORBIDDEN_CLOSE_CODE = 4403
WS_POLICY_VIOLATION_CLOSE_CODE = 1008


@collaboration_ws_router.websocket("/ws/canvas/{canvas_id}/collaboration")
async def canvas_collaboration_websocket(
    websocket: WebSocket,
    canvas_id: str,
    display_name: str | None = Query(default=None),
) -> None:
    async with async_session_factory() as session:
        current_user = await get_current_user_optional_ws(session, get_ws_bearer_token(websocket))
        user_id = current_user.id if current_user else None
        service = CanvasService(CanvasRepository(session))
        try:
            res = await service.obtener_lienzo(canvas_id, user_id=user_id)
        except CanvasNoEncontrado:
            role = None
        else:
            role = res.role

    if role not in ("ANFITRION", "COLABORADOR"):
        await websocket.close(code=WS_FORBIDDEN_CLOSE_CODE)
        return

    peer_id = await collaboration_room_registry.connect(
        websocket, canvas_id, display_name, subprotocol=ws_accept_subprotocol(websocket)
    )
    await websocket.send_text(json.dumps({"type": "connected", "peerId": peer_id}))
    try:
        with contextlib.suppress(Exception):  # desconexión o falla de transporte: fin de la Sesión
            await _relay_messages(websocket, canvas_id, peer_id)
    finally:
        await collaboration_room_registry.disconnect(canvas_id, peer_id)


async def _relay_messages(websocket: WebSocket, canvas_id: str, peer_id: str) -> None:
    """
    Reenvía a la Sala solo mensajes válidos. El exceso de frecuencia y los campos inválidos de un
    tipo permitido se descartan sin cerrar (cursor y arrastre son flujos con pérdida); una violación
    de protocolo (demasiado grande, no es JSON, tipo no permitido) cierra la conexión con 1008.
    """
    bucket = TokenBucket(MAX_MESSAGES_PER_SECOND, burst=MAX_MESSAGES_PER_SECOND)
    while True:
        text = await websocket.receive_text()
        if not bucket.allow():
            continue
        try:
            payload = parse_client_message(text)
        except InvalidMessageFieldsError:
            continue
        except InvalidClientMessageError:
            await websocket.close(code=WS_POLICY_VIOLATION_CLOSE_CODE)
            return
        await collaboration_room_registry.broadcast(canvas_id, peer_id, payload)
