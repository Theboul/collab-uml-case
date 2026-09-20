"""Adaptador del puerto `ChangePublisher`: difunde a la Sala un cambio ya confirmado."""

from backend_case.app.collaboration.application.ports.collaboration_room import CollaborationRoom
from backend_case.app.modeling.application.change_publisher import CanvasChange


class CollaborationChangePublisher:
    def __init__(self, room: CollaborationRoom) -> None:
        self._room = room

    async def canvas_changed(
        self, canvas_id: str, change: CanvasChange, origin_session_id: str = ""
    ) -> None:
        # `origin_session_id` (el `peerId` que manda el cliente) excluye del reenvío a la Sesión
        # que originó el cambio: su respuesta HTTP ya trae la versión nueva y el eco competiría
        # con ella (ciclo node:move/node:moved en un arrastre). Con "" (asistente, sin Sesión de
        # origen) llega a toda la Sala. Los demás aplican el delta solo si están exactamente en
        # `fromVersion`; si les falta alguno piden el Lienzo completo (contrato:
        # `contracts/canvas-delta.v1.json`).
        await self._room.publish(
            canvas_id,
            origin_session_id,
            {
                "type": "canvas_delta",
                "fromVersion": change.from_version,
                "toVersion": change.to_version,
                "delta": change.delta,
            },
        )
