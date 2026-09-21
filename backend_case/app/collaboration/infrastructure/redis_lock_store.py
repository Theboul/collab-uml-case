"""
Adaptador Redis de `LockStore` (ADR-0003 y su Addendum).

Almacena los locks de elementos UML en Redis con TTL de 15 segundos y operaciones
atómicas (Lua) para control de concurrencia entre múltiples workers de Uvicorn.
El conteo del límite de 20 locks por sesión y la comprobación de titularidad se
ejecutan en un único script Lua atómico para evitar carreras entre workers.
La expiración (expires_at) se deriva directamente del TTL real de Redis (PTTL).
"""

import json
import time
from collections.abc import Callable
from typing import Any

from backend_case.app.collaboration.application.ports.lock_store import (
    LOCK_TTL_SECONDS,
    MAX_LOCKS_PER_SESSION,
    AcquireResult,
    Lock,
    LockHolder,
)

_LUA_ACQUIRE = """
local lock_key = KEYS[1]
local canvas_id = ARGV[1]
local session_id = ARGV[2]
local ttl = tonumber(ARGV[3])
local max_locks = tonumber(ARGV[4])
local payload = ARGV[5]

local existing = redis.call('GET', lock_key)
if existing then
    local pttl = redis.call('PTTL', lock_key)
    if pttl <= 0 then
        redis.call('DEL', lock_key)
        existing = nil
    else
        local data = cjson.decode(existing)
        if data.sessionId == session_id then
            redis.call('SET', lock_key, payload, 'EX', ttl)
            local new_pttl = redis.call('PTTL', lock_key)
            return cjson.encode({granted = true, pttl = new_pttl})
        else
            return cjson.encode({granted = false, reason = 'held', holder = data, pttl = pttl})
        end
    end
end

-- Comprobar límite de locks de la sesión en el lienzo atómicamente
local pattern = 'lock:canvas:' .. canvas_id .. ':element:*'
local all_keys = redis.call('KEYS', pattern)
local count = 0
for _, k in ipairs(all_keys) do
    local pttl = redis.call('PTTL', k)
    if pttl > 0 then
        local val = redis.call('GET', k)
        if val then
            local data = cjson.decode(val)
            if data.sessionId == session_id then
                count = count + 1
            end
        end
    end
end

if count >= max_locks then
    return cjson.encode({granted = false, reason = 'limit'})
end

redis.call('SET', lock_key, payload, 'EX', ttl)
local pttl = redis.call('PTTL', lock_key)
return cjson.encode({granted = true, pttl = pttl})
"""

_LUA_RELEASE = """
local lock_key = KEYS[1]
local session_id = ARGV[1]

local existing = redis.call('GET', lock_key)
if existing then
    local pttl = redis.call('PTTL', lock_key)
    if pttl <= 0 then
        redis.call('DEL', lock_key)
        return 0
    end
    local data = cjson.decode(existing)
    if data.sessionId == session_id then
        redis.call('DEL', lock_key)
        return 1
    end
end
return 0
"""


class RedisLockStore:
    def __init__(
        self,
        redis_client: Any,
        clock: Callable[[], float] = time.time,
        ttl_seconds: int = LOCK_TTL_SECONDS,
        max_locks_per_session: int = MAX_LOCKS_PER_SESSION,
    ) -> None:
        self._redis = redis_client
        self._clock = clock
        self._ttl_seconds = ttl_seconds
        self._max_locks = max_locks_per_session

    @staticmethod
    def _lock_key(canvas_id: str, element_id: str) -> str:
        return f"lock:canvas:{canvas_id}:element:{element_id}"

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> AcquireResult:
        key = self._lock_key(canvas_id, element_id)
        payload = json.dumps(
            {
                "sessionId": holder.session_id,
                "userId": holder.user_id,
                "displayName": holder.display_name,
            }
        )

        raw_res = await self._redis.eval(
            _LUA_ACQUIRE,
            1,
            key,
            canvas_id,
            holder.session_id,
            self._ttl_seconds,
            self._max_locks,
            payload,
        )
        data = json.loads(raw_res)

        if data.get("granted"):
            pttl = data.get("pttl", self._ttl_seconds * 1000)
            expires_at = self._clock() + (pttl / 1000.0)
            lock = Lock(
                element_id=element_id,
                holder=holder,
                expires_at=expires_at,
            )
            return AcquireResult(granted=True, lock=lock)

        reason = data.get("reason")
        if reason == "held":
            h_data = data.get("holder", {})
            existing_holder = LockHolder(
                session_id=h_data.get("sessionId", ""),
                user_id=h_data.get("userId"),
                display_name=h_data.get("displayName"),
            )
            pttl = data.get("pttl", 0)
            expires_at = self._clock() + (pttl / 1000.0)
            existing_lock = Lock(
                element_id=element_id,
                holder=existing_holder,
                expires_at=expires_at,
            )
            return AcquireResult(granted=False, lock=existing_lock, reason="held")

        return AcquireResult(granted=False, lock=None, reason="limit")

    async def release(self, canvas_id: str, element_id: str, session_id: str) -> bool:
        key = self._lock_key(canvas_id, element_id)
        res = await self._redis.eval(_LUA_RELEASE, 1, key, session_id)
        return bool(res == 1)

    async def release_all(self, canvas_id: str, session_id: str) -> list[str]:
        pattern = f"lock:canvas:{canvas_id}:element:*"
        released: list[str] = []
        prefix = f"lock:canvas:{canvas_id}:element:"

        async for key in self._redis.scan_iter(match=pattern):
            key_str = key if isinstance(key, str) else key.decode("utf-8")
            element_id = key_str[len(prefix) :]
            if await self.release(canvas_id, element_id, session_id):
                released.append(element_id)

        return released

    async def force_release(self, canvas_id: str, element_id: str) -> bool:
        key = self._lock_key(canvas_id, element_id)
        res = await self._redis.delete(key)
        return bool(res > 0)

    async def list(self, canvas_id: str) -> list[Lock]:
        pattern = f"lock:canvas:{canvas_id}:element:*"
        prefix = f"lock:canvas:{canvas_id}:element:"
        locks: list[Lock] = []

        async for key in self._redis.scan_iter(match=pattern):
            key_str = key if isinstance(key, str) else key.decode("utf-8")
            element_id = key_str[len(prefix) :]
            raw_val = await self._redis.get(key_str)
            if raw_val is None:
                continue
            pttl = await self._redis.pttl(key_str)
            if pttl <= 0:
                continue
            data = json.loads(raw_val)
            holder = LockHolder(
                session_id=data.get("sessionId", ""),
                user_id=data.get("userId"),
                display_name=data.get("displayName"),
            )
            expires_at = self._clock() + (pttl / 1000.0)
            locks.append(
                Lock(
                    element_id=element_id,
                    holder=holder,
                    expires_at=expires_at,
                )
            )

        return locks
