"""
Adaptador en memoria de `LockStore` (ADR-0003 y su Addendum).

Almacena los locks en un diccionario en memoria para desarrollo, pruebas unitarias
y despliegues de un único worker. El descarte de locks vencidos es perezoso (se limpian
al consultar o mutar), sin requerir hilos o procesos en segundo plano.
"""

import time
from collections.abc import Callable

from backend_case.app.collaboration.application.ports.lock_store import (
    LOCK_TTL_SECONDS,
    MAX_LOCKS_PER_SESSION,
    AcquireResult,
    Lock,
    LockHolder,
)


class InMemoryLockStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._locks: dict[str, dict[str, Lock]] = {}

    def _clean_expired(self, canvas_id: str, now: float) -> dict[str, Lock]:
        canvas_locks = self._locks.get(canvas_id)
        if not canvas_locks:
            return {}
        expired_ids = [
            element_id for element_id, lock in canvas_locks.items() if now >= lock.expires_at
        ]
        for element_id in expired_ids:
            del canvas_locks[element_id]
        if not canvas_locks:
            self._locks.pop(canvas_id, None)
            return {}
        return canvas_locks

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> AcquireResult:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)

        existing = canvas_locks.get(element_id)
        if existing is not None:
            if existing.holder.session_id == holder.session_id:
                renewed = Lock(
                    element_id=element_id,
                    holder=holder,
                    expires_at=now + LOCK_TTL_SECONDS,
                )
                self._locks.setdefault(canvas_id, {})[element_id] = renewed
                return AcquireResult(granted=True, lock=renewed)
            return AcquireResult(granted=False, lock=existing, reason="held")

        session_locks_count = sum(
            1 for lock in canvas_locks.values() if lock.holder.session_id == holder.session_id
        )
        if session_locks_count >= MAX_LOCKS_PER_SESSION:
            return AcquireResult(granted=False, lock=None, reason="limit")

        new_lock = Lock(
            element_id=element_id,
            holder=holder,
            expires_at=now + LOCK_TTL_SECONDS,
        )
        self._locks.setdefault(canvas_id, {})[element_id] = new_lock
        return AcquireResult(granted=True, lock=new_lock)

    async def release(self, canvas_id: str, element_id: str, session_id: str) -> bool:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        existing = canvas_locks.get(element_id)
        if existing is None:
            return False
        if existing.holder.session_id != session_id:
            return False
        del canvas_locks[element_id]
        if not canvas_locks:
            self._locks.pop(canvas_id, None)
        return True

    async def release_all(self, canvas_id: str, session_id: str) -> list[str]:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        if not canvas_locks:
            return []
        released: list[str] = []
        for element_id, lock in list(canvas_locks.items()):
            if lock.holder.session_id == session_id:
                del canvas_locks[element_id]
                released.append(element_id)
        if not canvas_locks:
            self._locks.pop(canvas_id, None)
        return released

    async def list(self, canvas_id: str) -> list[Lock]:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        return list(canvas_locks.values())
