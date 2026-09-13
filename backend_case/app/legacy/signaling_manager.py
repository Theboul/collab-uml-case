import asyncio
import json
import logging
import os
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("signaling")


class SignalingManager:
    """
    Manages WebRTC signaling WebSocket connections per room.
    Reproduces Django Channels RedisChannelLayer multi-process semantics.
    Uses Redis Pub/Sub if REDIS_URL or REDIS_HOST is configured,
    with automatic fallback to local distribution if Redis is not available.
    """

    def __init__(self):
        # room_name -> {peer_id: WebSocket}
        self.rooms: dict[str, dict[str, WebSocket]] = {}
        self.redis_client = None
        self.pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._subscribed_rooms: set[str] = set()

    async def init_redis(self):
        """Initializes Redis Pub/Sub connection if available."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            redis_host = os.getenv("REDIS_HOST")
            redis_port = os.getenv("REDIS_PORT", "6379")
            if redis_host:
                redis_url = f"redis://{redis_host}:{redis_port}/0"

        if redis_url:
            try:
                import redis.asyncio as aioredis
                self.redis_client = aioredis.from_url(redis_url, decode_responses=True)
                # Test ping
                await self.redis_client.ping()
                self.pubsub = self.redis_client.pubsub()
                self._listener_task = asyncio.create_task(self._redis_listener())
                logger.info(f"[SignalingManager] Connected to Redis at {redis_url} for channel layer coordination.")
            except Exception as e:
                logger.warning(f"[SignalingManager] Failed to connect to Redis ({e}). Running in single-instance local mode.")
                self.redis_client = None
                self.pubsub = None

    async def close_redis(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()

    async def _redis_listener(self):
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    data_str = message["data"]
                    try:
                        event = json.loads(data_str)
                        await self._dispatch_local(event)
                    except Exception as e:
                        logger.error(f"[SignalingManager] Error handling redis message: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[SignalingManager] Redis listener loop error: {e}")

    async def connect(self, websocket: WebSocket, room_name: str) -> str:
        await websocket.accept()
        peer_id = f"specific.{uuid.uuid4().hex[:16]}"

        if room_name not in self.rooms:
            self.rooms[room_name] = {}
            if self.pubsub and room_name not in self._subscribed_rooms:
                await self.pubsub.subscribe(f"canvas_room_{room_name}")
                self._subscribed_rooms.add(room_name)

        self.rooms[room_name][peer_id] = websocket

        # Notify presence join to all peers in the room
        await self._publish_event(
            room_name,
            {
                "event_type": "presence",
                "room_name": room_name,
                "action": "join",
                "peer": peer_id,
            },
        )
        return peer_id

    async def disconnect(self, room_name: str, peer_id: str):
        if room_name in self.rooms:
            self.rooms[room_name].pop(peer_id, None)

            # Notify presence leave
            await self._publish_event(
                room_name,
                {
                    "event_type": "presence",
                    "room_name": room_name,
                    "action": "leave",
                    "peer": peer_id,
                },
            )

            if not self.rooms[room_name]:
                del self.rooms[room_name]
                if self.pubsub and room_name in self._subscribed_rooms:
                    await self.pubsub.unsubscribe(f"canvas_room_{room_name}")
                    self._subscribed_rooms.remove(room_name)

    async def handle_message(self, room_name: str, sender_peer_id: str, data: dict[str, Any]):
        msg_type = data.get("type")

        if msg_type == "broadcast":
            await self._publish_event(
                room_name,
                {
                    "event_type": "broadcast",
                    "room_name": room_name,
                    "from": sender_peer_id,
                    "payload": data.get("payload"),
                },
            )
        elif msg_type == "signal":
            target_peer = data.get("to")
            await self._publish_event(
                room_name,
                {
                    "event_type": "signal",
                    "room_name": room_name,
                    "from": sender_peer_id,
                    "to": target_peer,
                    "payload": data.get("payload"),
                },
            )

    async def _publish_event(self, room_name: str, event: dict[str, Any]):
        if self.redis_client:
            channel = f"canvas_room_{room_name}"
            await self.redis_client.publish(channel, json.dumps(event))
        else:
            # Local in-process delivery
            await self._dispatch_local(event)

    async def _dispatch_local(self, event: dict[str, Any]):
        room_name = event.get("room_name")
        event_type = event.get("event_type")

        if room_name not in self.rooms:
            return

        if event_type == "presence":
            message = {
                "type": "presence",
                "action": event.get("action"),
                "peer": event.get("peer"),
            }
            await self._send_to_all(room_name, message)

        elif event_type == "broadcast":
            message = {
                "type": "broadcast",
                "from": event.get("from"),
                "payload": event.get("payload"),
            }
            await self._send_to_all(room_name, message)

        elif event_type == "signal":
            target_peer = event.get("to")
            if target_peer and target_peer in self.rooms[room_name]:
                ws = self.rooms[room_name][target_peer]
                message = {
                    "type": "signal",
                    "from": event.get("from"),
                    "payload": event.get("payload"),
                }
                try:
                    await ws.send_text(json.dumps(message))
                except Exception:
                    self.rooms[room_name].pop(target_peer, None)

    async def _send_to_all(self, room_name: str, message: dict[str, Any]):
        if room_name not in self.rooms:
            return
        text = json.dumps(message)
        dead_peers = []
        for pid, ws in list(self.rooms[room_name].items()):
            try:
                await ws.send_text(text)
            except Exception:
                dead_peers.append(pid)

        for pid in dead_peers:
            self.rooms[room_name].pop(pid, None)


signaling_manager = SignalingManager()
