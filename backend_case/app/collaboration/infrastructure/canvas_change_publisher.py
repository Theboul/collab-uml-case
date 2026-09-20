"""Adaptador del puerto `ChangePublisher`: difunde a la Sala un cambio ya confirmado."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend_case.app.collaboration.application.ports.collaboration_room import CollaborationRoom
from backend_case.app.modeling.application.change_publisher import CanvasChange

if TYPE_CHECKING:
    from backend_case.app.collaboration.application.collaboration_service import (
        CollaborationService,
    )


class CollaborationChangePublisher:
    def __init__(
        self,
        room: CollaborationRoom,
        collaboration_service: CollaborationService | None = None,
    ) -> None:
        self._room = room
        self._collab_service = collaboration_service

    async def canvas_changed(
        self, canvas_id: str, change: CanvasChange, origin_session_id: str = ""
    ) -> None:
        # `origin_session_id` (el `peerId` que manda el cliente) excluye del reenvío a la Sesión
        # que originó el cambio: su respuesta HTTP ya trae la versión nueva y el eco competiría
        # con ella (ciclo node:move/node:moved en un arrastre). Con "" (asistente, sin Sesión de
        # origen) llega a toda la Sala.
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

        # Ajuste A: Delegar liberación por borrado a CollaborationService
        if self._collab_service is not None:
            await self._release_deleted_elements_locks(canvas_id, change.delta)

    async def _release_deleted_elements_locks(self, canvas_id: str, delta: dict[str, Any]) -> None:
        if self._collab_service is None:
            return
        model = delta.get("model", {})
        for kind_data in model.values():
            if isinstance(kind_data, dict):
                for element_id in kind_data.get("remove", []):
                    await self._collab_service.on_element_deleted(canvas_id, element_id)
