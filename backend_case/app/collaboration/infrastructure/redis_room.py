"""
Adaptador Redis de `CollaborationRoom` con fan-out Pub/Sub entre workers (ADR-0003).

Permite que múltiples workers de Uvicorn sincronicen eventos en tiempo real
(cursores, deltas, locks, presencia) a través del canal `pubsub:canvas:{canvasId}`.
Implementa entrega local inmediata combinada con discriminación de `originWorkerId`
para evitar ecos duplicados y tolerar fallas transitorias de Pub/Sub.
Todas las operaciones sobre `self._pubsub` están protegidas por un `asyncio.Lock`
para evitar carreras de concurrencia y desincronizaciones entre join y leave.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from backend_case.app.collaboration.application.ports.collaboration_room import (
    Connection,
    Session,
)

logger = logging.getLogger("collaboration.redis_room")


@dataclass
class _Member:
    session: Session
    connection: Connection


class RedisCollaborationRoom:
    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client
        self._worker_id = uuid.uuid4().hex[:8]
        self.rooms: dict[str, dict[str, _Member]] = {}
        self._pubsub = self._redis.pubsub()
        self._pubsub_lock = asyncio.Lock()
        self._listener_task: asyncio.Task[None] | None = None
        self._closed = False

    @staticmethod
    def _channel_name(canvas_id: str) -> str:
        return f"pubsub:canvas:{canvas_id}"

    def _ensure_listener(self) -> None:
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        while not self._closed:
            try:
                async for message in self._pubsub.listen():
                    if message.get("type") == "message":
                        await self._handle_remote_message(message)
                # Si listen() concluye normalmente (desuscripción total de canales), salir del loop
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._closed:
                    break
                logger.warning(
                    f"[RedisCollaborationRoom] Error en listener PubSub ({e}). "
                    "Reintentando en 1s..."
                )
                await asyncio.sleep(1.0)
                with contextlib.suppress(Exception):
                    async with self._pubsub_lock:
                        active_channels = [
                            self._channel_name(cid)
                            for cid, members in self.rooms.items()
                            if members
                        ]
                        if active_channels:
                            await self._pubsub.subscribe(*active_channels)
                        else:
                            break

    async def _handle_remote_message(self, message: dict[str, Any]) -> None:
        try:
            raw_data = message.get("data")
            if not raw_data:
                return
            data_str = raw_data if isinstance(raw_data, str) else raw_data.decode("utf-8")
            msg = json.loads(data_str)
        except Exception:
            return

        # Si el mensaje fue originado por este mismo worker, ignorar para evitar duplicado
        if msg.get("originWorkerId") == self._worker_id:
            return

        canvas_id = msg.get("canvasId")
        if not canvas_id:
            return

        room = self.rooms.get(canvas_id)
        if not room:
            return

        sender_session_id = msg.get("from", "")
        exclude_sender = msg.get("excludeSender", True)
        client_text = json.dumps(
            {
                "from": sender_session_id,
                "fromDisplayName": msg.get("fromDisplayName"),
                "payload": msg.get("payload"),
            }
        )

        dead_session_ids: list[str] = []
        for session_id, member in list(room.items()):
            if exclude_sender and session_id == sender_session_id:
                continue
            try:
                await member.connection.send_text(client_text)
            except Exception:
                dead_session_ids.append(session_id)

        for session_id in dead_session_ids:
            room.pop(session_id, None)

    async def join(
        self,
        canvas_id: str,
        connection: Connection,
        display_name: str | None = None,
        user_id: str | None = None,
    ) -> Session:
        session = Session(id=uuid.uuid4().hex[:12], display_name=display_name, user_id=user_id)

        async with self._pubsub_lock:
            canvas_members = self.rooms.setdefault(canvas_id, {})
            canvas_members[session.id] = _Member(session, connection)

            # Si es el primer miembro local en este canvas, suscribir el PubSub al canal
            if len(canvas_members) == 1:
                channel = self._channel_name(canvas_id)
                await self._pubsub.subscribe(channel)
                self._ensure_listener()

        return session

    async def leave(self, canvas_id: str, session: Session) -> None:
        async with self._pubsub_lock:
            room = self.rooms.get(canvas_id)
            if room is None:
                return
            room.pop(session.id, None)

            # Revalidar dentro de la sección crítica antes de desuscribirse
            if not room:
                self.rooms.pop(canvas_id, None)
                if canvas_id not in self.rooms or not self.rooms[canvas_id]:
                    channel = self._channel_name(canvas_id)
                    with contextlib.suppress(Exception):
                        await self._pubsub.unsubscribe(channel)

    async def members(self, canvas_id: str) -> list[Session]:
        room = self.rooms.get(canvas_id)
        if not room:
            return []
        return [m.session for m in room.values()]

    async def publish(
        self,
        canvas_id: str,
        sender_session_id: str,
        payload: Any,
        exclude_sender: bool = True,
    ) -> None:
        room = self.rooms.get(canvas_id)

        sender_display_name = None
        if room and sender_session_id in room:
            sender_display_name = room[sender_session_id].session.display_name

        client_message = json.dumps(
            {
                "from": sender_session_id,
                "fromDisplayName": sender_display_name,
                "payload": payload,
            }
        )

        # 1. Entrega local inmediata a los WebSockets de este worker
        if room:
            dead_session_ids: list[str] = []
            for session_id, member in list(room.items()):
                if exclude_sender and session_id == sender_session_id:
                    continue
                try:
                    await member.connection.send_text(client_message)
                except Exception:
                    dead_session_ids.append(session_id)

            for session_id in dead_session_ids:
                room.pop(session_id, None)

        # 2. Publicación a Redis Pub/Sub para que otros workers lo reciban
        pubsub_message = json.dumps(
            {
                "canvasId": canvas_id,
                "from": sender_session_id,
                "fromDisplayName": sender_display_name,
                "payload": payload,
                "excludeSender": exclude_sender,
                "originWorkerId": self._worker_id,
            }
        )
        channel = self._channel_name(canvas_id)
        try:
            await self._redis.publish(channel, pubsub_message)
        except Exception as e:
            logger.error(f"[RedisCollaborationRoom] Fallo al publicar en PubSub ({e})")

    async def close(self) -> None:
        self._closed = True
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
        async with self._pubsub_lock:
            with contextlib.suppress(Exception):
                if hasattr(self._pubsub, "aclose"):
                    await self._pubsub.aclose()
                else:
                    await self._pubsub.close()
