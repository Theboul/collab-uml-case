"""
Adaptador en memoria de `CollaborationRoom`: las Sesiones viven en este proceso. Sirve para
desarrollo, tests y un único worker; con varios workers hace falta el adaptador Redis (Paso 6).
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from backend_case.app.collaboration.application.ports.collaboration_room import (
    Connection,
    Session,
)


@dataclass
class _Member:
    session: Session
    connection: Connection


class InMemoryCollaborationRoom:
    def __init__(self) -> None:
        self.rooms: dict[str, dict[str, _Member]] = {}

    async def join(
        self,
        canvas_id: str,
        connection: Connection,
        display_name: str | None = None,
        user_id: str | None = None,
    ) -> Session:
        session = Session(id=uuid.uuid4().hex[:12], display_name=display_name, user_id=user_id)
        self.rooms.setdefault(canvas_id, {})[session.id] = _Member(session, connection)
        return session

    async def leave(self, canvas_id: str, session: Session) -> None:
        room = self.rooms.get(canvas_id)
        if room is None:
            return
        room.pop(session.id, None)
        if not room:
            del self.rooms[canvas_id]

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
        if not room:
            return

        sender = room.get(sender_session_id)
        message = json.dumps(
            {
                "from": sender_session_id,
                "fromDisplayName": sender.session.display_name if sender else None,
                "payload": payload,
            }
        )
        dead_session_ids: list[str] = []
        for session_id, member in list(room.items()):
            if exclude_sender and session_id == sender_session_id:
                continue
            try:
                await member.connection.send_text(message)
            except Exception:  # cualquier falla de envío marca la Sesión como muerta
                dead_session_ids.append(session_id)

        for session_id in dead_session_ids:
            room.pop(session_id, None)
