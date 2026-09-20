"""Adaptador del puerto `ChangePublisher`: difunde a la Sala un cambio ya confirmado."""

from typing import Any

from backend_case.app.collaboration.application.ports.collaboration_room import CollaborationRoom
from backend_case.app.collaboration.application.ports.lock_store import LockStore
from backend_case.app.modeling.application.change_publisher import CanvasChange


class CollaborationChangePublisher:
    def __init__(
        self,
        room: CollaborationRoom,
        lock_store: LockStore | None = None,
    ) -> None:
        self._room = room
        self._lock_store = lock_store

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

        # Ajuste A: Liberar el lock cuando el elemento se borra de verdad.
        if self._lock_store is not None:
            await self._release_deleted_elements_locks(canvas_id, change.delta)

    async def _release_deleted_elements_locks(self, canvas_id: str, delta: dict[str, Any]) -> None:
        if self._lock_store is None:
            return
        model = delta.get("model", {})
        deleted_ids: list[str] = []
        for kind_data in model.values():
            if isinstance(kind_data, dict):
                deleted_ids.extend(kind_data.get("remove", []))

        for element_id in deleted_ids:
            released = await self._lock_store.force_release(canvas_id, element_id)
            if released:
                await self._room.publish(
                    canvas_id,
                    "",
                    {"type": "lock_released", "elementId": element_id},
                )
