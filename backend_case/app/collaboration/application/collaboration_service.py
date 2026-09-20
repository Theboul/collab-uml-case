"""
Servicio de aplicación de colaboración (ADR-0003, CU5).

Orquesta el almacén de locks (`LockStore`), la presencia (`PresenceService`) y las
notificaciones a la Sala (`CollaborationRoom`) para eventos de lock, presencia y borrado.
"""

from typing import Any

from backend_case.app.collaboration.application.ports.collaboration_room import (
    CollaborationRoom,
    Session,
)
from backend_case.app.collaboration.application.ports.lock_store import (
    LOCK_TTL_SECONDS,
    LockHolder,
    LockStore,
)
from backend_case.app.collaboration.application.presence_service import PresenceService


class CollaborationService:
    def __init__(
        self,
        room: CollaborationRoom,
        lock_store: LockStore,
        presence_service: PresenceService,
    ) -> None:
        self.room = room
        self.lock_store = lock_store
        self.presence_service = presence_service

    async def on_session_joined(
        self,
        canvas_id: str,
        session: Session,
        user_id: str | None,
        display_name: str | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Registra la presencia, obtiene snapshots de locks y presencia, y notifica
        a los demás miembros de la sala con `presence_joined`.
        """
        await self.presence_service.join(canvas_id, session.id, user_id, display_name)

        active_locks = await self.lock_store.list(canvas_id)
        locks_snapshot = [
            {
                "elementId": lock.element_id,
                "holder": {
                    "sessionId": lock.holder.session_id,
                    "userId": lock.holder.user_id,
                    "displayName": lock.holder.display_name,
                },
                "ttlMs": int(LOCK_TTL_SECONDS * 1000),
            }
            for lock in active_locks
        ]

        active_presence = await self.presence_service.list_active(canvas_id)
        presence_snapshot = [
            {
                "sessionId": p.session_id,
                "userId": p.user_id,
                "displayName": p.display_name,
            }
            for p in active_presence
        ]

        # Notificar a las demás sesiones de la sala
        await self.room.publish(
            canvas_id,
            session.id,
            {
                "type": "presence_joined",
                "session": {
                    "sessionId": session.id,
                    "userId": user_id,
                    "displayName": display_name,
                },
            },
        )

        return locks_snapshot, presence_snapshot

    async def on_session_left(self, canvas_id: str, session: Session) -> None:
        """
        Al salir una sesión: libera todos sus locks en el lienzo, notifica `lock_released`
        por cada uno, notifica `presence_left` y la retira de la sala y presencia.
        """
        released_element_ids = await self.lock_store.release_all(canvas_id, session.id)
        for elem_id in released_element_ids:
            await self.room.publish(
                canvas_id,
                session.id,
                {"type": "lock_released", "elementId": elem_id},
            )

        await self.presence_service.leave(canvas_id, session.id)
        await self.room.publish(
            canvas_id,
            session.id,
            {"type": "presence_left", "sessionId": session.id},
        )
        await self.room.leave(canvas_id, session)

    async def acquire_lock(
        self,
        canvas_id: str,
        session: Session,
        element_id: str,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Intenta adquirir o renovar el lock.
        Si se concede: difunde `lock_acquired` a TODA la sala (incluyendo al emisor
        con `exclude_sender=False`, Ajuste B) con `holder.sessionId`.
        Si se deniega: devuelve `(False, lock_denied_payload)` para enviar solo al solicitante.
        """
        holder = LockHolder(
            session_id=session.id,
            user_id=session.user_id,
            display_name=session.display_name,
        )
        res = await self.lock_store.acquire(canvas_id, element_id, holder)
        if res.granted:
            acquired_payload = {
                "type": "lock_acquired",
                "elementId": element_id,
                "holder": {
                    "sessionId": holder.session_id,
                    "userId": holder.user_id,
                    "displayName": holder.display_name,
                },
                "ttlMs": int(LOCK_TTL_SECONDS * 1000),
            }
            # Difunde a toda la sala, incluido el emisor
            await self.room.publish(
                canvas_id,
                session.id,
                acquired_payload,
                exclude_sender=False,
            )
            return True, acquired_payload
        else:
            held_holder = (
                {
                    "sessionId": res.lock.holder.session_id,
                    "userId": res.lock.holder.user_id,
                    "displayName": res.lock.holder.display_name,
                }
                if res.lock
                else None
            )
            denied_payload = {
                "type": "lock_denied",
                "elementId": element_id,
                "reason": res.reason,
                "holder": held_holder,
            }
            return False, denied_payload

    async def release_lock(
        self,
        canvas_id: str,
        session: Session,
        element_id: str,
    ) -> bool:
        """
        Libera el lock explícitamente si la sesión es el titular.
        Si libera, difunde `lock_released` a toda la sala.
        """
        released = await self.lock_store.release(canvas_id, element_id, session.id)
        if released:
            await self.room.publish(
                canvas_id,
                session.id,
                {"type": "lock_released", "elementId": element_id},
                exclude_sender=False,
            )
        return released

    async def on_element_deleted(self, canvas_id: str, element_id: str) -> bool:
        """
        Ajuste A: Si un elemento borrado tenía un lock activo, lo libera de inmediato
        y difunde `lock_released` a toda la sala sin esperar al vencimiento del TTL.
        """
        released = await self.lock_store.force_release(canvas_id, element_id)
        if released:
            await self.room.publish(
                canvas_id,
                "",
                {"type": "lock_released", "elementId": element_id},
            )
        return released
