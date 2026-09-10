"""
Registro en memoria de peers conectados por lienzo (ADR-0003, paso 1: canal de
transporte). Sin Redis, sin locks, sin presencia todavía — solo bookkeeping de
sockets y broadcast al resto de la sala.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass
class ConnectedPeer:
    websocket: WebSocket
    display_name: str | None = None


class CollaborationRoomRegistry:
    """
    Mantiene, por `canvas_id`, el conjunto de peers actualmente conectados y
    hace broadcast de mensajes entre ellos. `display_name` se acepta y se
    guarda desde ahora para no romper la firma de `connect()` en los pasos
    siguientes del roadmap (puntero de colaborador, lock), aunque este paso
    todavía no lo usa para nada.
    """

    def __init__(self) -> None:
        self.rooms: dict[str, dict[str, ConnectedPeer]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        canvas_id: str,
        display_name: str | None = None,
    ) -> str:
        await websocket.accept()
        peer_id = uuid.uuid4().hex[:12]
        self.rooms.setdefault(canvas_id, {})[peer_id] = ConnectedPeer(
            websocket=websocket, display_name=display_name
        )
        return peer_id

    async def disconnect(self, canvas_id: str, peer_id: str) -> None:
        room = self.rooms.get(canvas_id)
        if room is None:
            return
        room.pop(peer_id, None)
        if not room:
            del self.rooms[canvas_id]

    async def broadcast(self, canvas_id: str, sender_peer_id: str, payload: Any) -> None:
        room = self.rooms.get(canvas_id)
        if not room:
            return

        sender = room.get(sender_peer_id)
        message = json.dumps(
            {
                "from": sender_peer_id,
                "fromDisplayName": sender.display_name if sender else None,
                "payload": payload,
            }
        )
        dead_peer_ids: list[str] = []
        for peer_id, peer in list(room.items()):
            if peer_id == sender_peer_id:
                continue
            try:
                await peer.websocket.send_text(message)
            except Exception:  # noqa: BLE001 — cualquier falla de envío marca al peer como muerto
                dead_peer_ids.append(peer_id)

        for peer_id in dead_peer_ids:
            room.pop(peer_id, None)


collaboration_room_registry = CollaborationRoomRegistry()
