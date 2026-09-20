"""
Endpoint WebSocket del canal de colaboración activo (ADR-0003, paso 1).
Sólo transporte: acepta la conexión, hace broadcast de los mensajes válidos al resto
de la sala del mismo `canvas_id`, y limpia el registro al desconectar. Lo que una
sesión puede enviar (tipos, campos, tamaño, frecuencia) está en `schemas.py` y
`rate_limit.py`; cualquier otra cosa se descarta o cierra la conexión.

Se acepta SIEMPRE el handshake antes de rechazar: cerrar antes de `accept()` llega
al navegador como un fallo de handshake sin código (1006), indistinguible de una
caída de red, y el cliente no sabría si reintentar. Tras aceptar se resuelve el rol
del solicitante sobre el lienzo (mismo `resolver_rol` que usa la API HTTP) y se
cierra con un código que el cliente puede leer: 4401 si presentó un token inválido
o vencido (puede renovarlo y reintentar), 4403 si no es ANFITRION ni COLABORADOR
(no debe reintentar). Un socket rechazado nunca entra a la sala ni recibe una Sesión.

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
    WS_UNAUTHORIZED_CLOSE_CODE,
    get_current_user_optional_ws,
    get_ws_bearer_token,
    ws_accept_subprotocol,
)
from fastapi import APIRouter, Query, WebSocket

from core.uml_domain.exceptions import CanvasNoEncontrado

from .application.ports.collaboration_room import CollaborationRoom, Session
from .dependencies import CollaborationRoomDep
from .rate_limit import MAX_MESSAGES_PER_SECOND, TokenBucket
from .schemas import InvalidClientMessageError, InvalidMessageFieldsError, parse_client_message

collaboration_ws_router = APIRouter(tags=["Collaboration"])

WS_FORBIDDEN_CLOSE_CODE = 4403
WS_POLICY_VIOLATION_CLOSE_CODE = 1008


@collaboration_ws_router.websocket("/ws/canvas/{canvas_id}/collaboration")
async def canvas_collaboration_websocket(
    websocket: WebSocket,
    canvas_id: str,
    room: CollaborationRoomDep,
    display_name: str | None = Query(default=None),
) -> None:
    token = get_ws_bearer_token(websocket)
    async with async_session_factory() as session:
        current_user = await get_current_user_optional_ws(session, token)
        user_id = current_user.id if current_user else None
        service = CanvasService(CanvasRepository(session))
        try:
            res = await service.obtener_lienzo(canvas_id, user_id=user_id)
        except CanvasNoEncontrado:
            role = None
        else:
            role = res.role

    await websocket.accept(subprotocol=ws_accept_subprotocol(websocket))
    if token and current_user is None:
        await websocket.close(code=WS_UNAUTHORIZED_CLOSE_CODE)  # token inválido o vencido: renovar
        return
    if role not in ("ANFITRION", "COLABORADOR"):
        await websocket.close(code=WS_FORBIDDEN_CLOSE_CODE)  # sin permiso: no reintentar
        return

    room_session = await room.join(canvas_id, websocket, display_name)
    await websocket.send_text(json.dumps({"type": "connected", "peerId": room_session.id}))
    try:
        with contextlib.suppress(Exception):  # desconexión o falla de transporte: fin de la Sesión
            await _relay_messages(websocket, room, canvas_id, room_session)
    finally:
        await room.leave(canvas_id, room_session)


async def _relay_messages(
    websocket: WebSocket, room: CollaborationRoom, canvas_id: str, room_session: Session
) -> None:
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
        await room.publish(canvas_id, room_session.id, payload)
