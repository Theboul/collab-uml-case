"""
Endpoint WebSocket del canal de colaboración activo (ADR-0003, CU5).
Sólo transporte y orquestación: autentica el handshake, entrega snapshots de locks
y presencia al unirse, retransmite o despacha mensajes válidos a través de
`CollaborationService`, y limpia locks y presencia al desconectar.
"""

import contextlib
import json

from fastapi import APIRouter, WebSocket

from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasRepository
from backend_case.app.shared.db.base import async_session_factory
from backend_case.app.shared.security.dependencies import (
    WS_UNAUTHORIZED_CLOSE_CODE,
    get_current_user_optional_ws,
    get_ws_bearer_token,
    ws_accept_subprotocol,
)
from core.uml_domain.exceptions import CanvasNoEncontrado

from .application.collaboration_service import CollaborationService
from .application.ports.collaboration_room import Session
from .dependencies import CollaborationServiceDep
from .rate_limit import MAX_MESSAGES_PER_SECOND, TokenBucket
from .schemas import InvalidClientMessageError, InvalidMessageFieldsError, parse_client_message

collaboration_ws_router = APIRouter(tags=["Collaboration"])

WS_FORBIDDEN_CLOSE_CODE = 4403
WS_POLICY_VIOLATION_CLOSE_CODE = 1008


@collaboration_ws_router.websocket("/ws/canvas/{canvas_id}/collaboration")
async def canvas_collaboration_websocket(
    websocket: WebSocket,
    canvas_id: str,
    collab_service: CollaborationServiceDep,
) -> None:
    token = get_ws_bearer_token(websocket)
    async with async_session_factory() as session:
        current_user = await get_current_user_optional_ws(session, token)
        user_id = str(current_user.id) if current_user and current_user.id else None
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

    # Decisión 1: display_name proviene siempre del usuario autenticado, no de query params
    display_name = current_user.display_name if current_user else None

    room_session = await collab_service.room.join(
        canvas_id, websocket, display_name=display_name, user_id=user_id
    )
    await websocket.send_text(json.dumps({"type": "connected", "peerId": room_session.id}))

    locks_snapshot, presence_snapshot = await collab_service.on_session_joined(
        canvas_id, room_session, user_id=user_id, display_name=display_name
    )
    await websocket.send_text(json.dumps({"type": "locks_snapshot", "locks": locks_snapshot}))
    await websocket.send_text(
        json.dumps({"type": "presence_snapshot", "sessions": presence_snapshot})
    )

    try:
        with contextlib.suppress(Exception):  # desconexión o falla de transporte: fin de la Sesión
            await _relay_messages(websocket, collab_service, canvas_id, room_session)
    finally:
        await collab_service.on_session_left(canvas_id, room_session)


async def _relay_messages(
    websocket: WebSocket,
    collab_service: CollaborationService,
    canvas_id: str,
    room_session: Session,
) -> None:
    """
    Reenvía a la Sala o despacha al servicio solo mensajes válidos.
    Campos inválidos de un tipo permitido y exceso de tasa se descartan sin cerrar;
    violaciones de protocolo (demasiado grande, no es JSON, tipo no permitido) cierran con 1008.
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

        msg_type = payload.get("type")
        if msg_type == "lock_acquire":
            granted, result_payload = await collab_service.acquire_lock(
                canvas_id, room_session, payload["elementId"]
            )
            if not granted:
                await websocket.send_text(json.dumps(result_payload))
        elif msg_type == "lock_release":
            await collab_service.release_lock(canvas_id, room_session, payload["elementId"])
        else:
            await collab_service.presence_service.heartbeat(canvas_id, room_session.id)
            await collab_service.room.publish(canvas_id, room_session.id, payload)
