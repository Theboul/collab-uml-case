"""Adaptador del puerto `ChangePublisher`: difunde a la Sala un cambio ya confirmado."""

from backend_case.app.collaboration.application.ports.collaboration_room import CollaborationRoom
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasResult
from backend_case.app.schemas.canvas import to_detail_schema


class CollaborationChangePublisher:
    def __init__(self, room: CollaborationRoom) -> None:
        self._room = room

    async def canvas_changed(
        self, canvas_id: str, result: CanvasResult, origin_session_id: str = ""
    ) -> None:
        # `origin_session_id` (el `peerId` que manda el cliente) excluye del reenvío a la Sesión
        # que originó el cambio: su respuesta HTTP ya trae la versión nueva y el eco competiría
        # con ella (ciclo node:move/node:moved en un arrastre). Con "" (asistente, sin Sesión de
        # origen) llega a toda la Sala; el guard de versión de RemoteCanvasSyncService sigue como
        # red de seguridad para ese caso y cualquier otro desfase real.
        canvas = to_detail_schema(result.lienzo, result.version, result.owner_id, result.room_name)
        await self._room.publish(
            canvas_id,
            origin_session_id,
            {"type": "canvas_update", "canvas": canvas.model_dump(mode="json")},
        )
