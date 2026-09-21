"""
Adaptador Redis de presencia de sesiones (ADR-0003 y su Addendum).

Almacena la presencia de cada sesión en Redis con TTL de 15 segundos.
La expiración se deriva en tiempo de lectura a partir del PTTL real de Redis
(clock() + pttl / 1000.0), sin almacenar valores de tiempo en el payload JSON.
"""

import json
import time
from collections.abc import Callable
from typing import Any

from backend_case.app.collaboration.application.presence_service import (
    PRESENCE_TTL_SECONDS,
    SessionPresence,
)

_LUA_HEARTBEAT = """
local key = KEYS[1]
local ttl_ms = tonumber(ARGV[1])

local pttl = redis.call('PTTL', key)
if pttl > 0 then
    redis.call('PEXPIRE', key, ttl_ms)
    return 1
else
    if pttl == 0 then
        redis.call('DEL', key)
    end
    return 0
end
"""


class RedisPresenceService:
    def __init__(
        self,
        redis_client: Any,
        clock: Callable[[], float] = time.time,
        ttl_seconds: float = PRESENCE_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._clock = clock
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _presence_key(canvas_id: str, session_id: str) -> str:
        return f"presence:canvas:{canvas_id}:{session_id}"

    async def join(
        self,
        canvas_id: str,
        session_id: str,
        user_id: str | None,
        display_name: str | None,
    ) -> SessionPresence:
        key = self._presence_key(canvas_id, session_id)
        payload = json.dumps(
            {
                "sessionId": session_id,
                "userId": user_id,
                "displayName": display_name,
            }
        )
        ttl_ms = int(self._ttl_seconds * 1000)
        await self._redis.set(key, payload, px=ttl_ms)
        pttl = await self._redis.pttl(key)
        actual_pttl = pttl if pttl > 0 else ttl_ms
        expires_at = self._clock() + (actual_pttl / 1000.0)
        return SessionPresence(
            session_id=session_id,
            user_id=user_id,
            display_name=display_name,
            expires_at=expires_at,
        )

    async def heartbeat(self, canvas_id: str, session_id: str) -> bool:
        key = self._presence_key(canvas_id, session_id)
        ttl_ms = int(self._ttl_seconds * 1000)
        res = await self._redis.eval(_LUA_HEARTBEAT, 1, key, ttl_ms)
        return bool(res == 1)

    async def leave(self, canvas_id: str, session_id: str) -> bool:
        key = self._presence_key(canvas_id, session_id)
        res = await self._redis.delete(key)
        return bool(res > 0)

    async def list_active(self, canvas_id: str) -> list[SessionPresence]:
        pattern = f"presence:canvas:{canvas_id}:*"
        active: list[SessionPresence] = []

        async for key in self._redis.scan_iter(match=pattern):
            key_str = key if isinstance(key, str) else key.decode("utf-8")
            raw_val = await self._redis.get(key_str)
            if raw_val is None:
                continue
            pttl = await self._redis.pttl(key_str)
            if pttl <= 0:
                continue
            data = json.loads(raw_val)
            expires_at = self._clock() + (pttl / 1000.0)
            active.append(
                SessionPresence(
                    session_id=data.get("sessionId", ""),
                    user_id=data.get("userId"),
                    display_name=data.get("displayName"),
                    expires_at=expires_at,
                )
            )

        return active
