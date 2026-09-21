"""
Servicio de presencia de sesiones (ADR-0003 y su Addendum).

Define el protocolo `PresenceService` y su implementación en memoria `InMemoryPresenceService`.
Gestiona la presencia activa de sesiones conectadas a un lienzo, con expiración
basada en TTL y reloj inyectable para pruebas sin sleep real.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

PRESENCE_TTL_SECONDS = 15.0


@dataclass(frozen=True)
class SessionPresence:
    session_id: str
    user_id: str | None
    display_name: str | None
    expires_at: float


class PresenceService(Protocol):
    """Protocolo del servicio de presencia de sesiones en un lienzo."""

    async def join(
        self,
        canvas_id: str,
        session_id: str,
        user_id: str | None,
        display_name: str | None,
    ) -> SessionPresence: ...

    async def heartbeat(self, canvas_id: str, session_id: str) -> bool: ...

    async def leave(self, canvas_id: str, session_id: str) -> bool: ...

    async def list_active(self, canvas_id: str) -> list[SessionPresence]: ...


class InMemoryPresenceService:
    """Implementación en memoria de PresenceService para desarrollo y pruebas."""

    def __init__(
        self,
        ttl_seconds: float = PRESENCE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._sessions: dict[str, dict[str, SessionPresence]] = {}

    def _clean_expired(self, canvas_id: str, now: float) -> dict[str, SessionPresence]:
        canvas_presence = self._sessions.get(canvas_id)
        if not canvas_presence:
            return {}
        expired = [sid for sid, p in canvas_presence.items() if now >= p.expires_at]
        for sid in expired:
            del canvas_presence[sid]
        if not canvas_presence:
            self._sessions.pop(canvas_id, None)
            return {}
        return canvas_presence

    async def join(
        self,
        canvas_id: str,
        session_id: str,
        user_id: str | None,
        display_name: str | None,
    ) -> SessionPresence:
        now = self._clock()
        self._clean_expired(canvas_id, now)
        presence = SessionPresence(
            session_id=session_id,
            user_id=user_id,
            display_name=display_name,
            expires_at=now + self._ttl_seconds,
        )
        self._sessions.setdefault(canvas_id, {})[session_id] = presence
        return presence

    async def heartbeat(self, canvas_id: str, session_id: str) -> bool:
        now = self._clock()
        canvas_presence = self._clean_expired(canvas_id, now)
        existing = canvas_presence.get(session_id)
        if existing is None:
            return False
        renewed = SessionPresence(
            session_id=existing.session_id,
            user_id=existing.user_id,
            display_name=existing.display_name,
            expires_at=now + self._ttl_seconds,
        )
        canvas_presence[session_id] = renewed
        return True

    async def leave(self, canvas_id: str, session_id: str) -> bool:
        now = self._clock()
        canvas_presence = self._clean_expired(canvas_id, now)
        if session_id in canvas_presence:
            del canvas_presence[session_id]
            if not canvas_presence:
                self._sessions.pop(canvas_id, None)
            return True
        return False

    async def list_active(self, canvas_id: str) -> list[SessionPresence]:
        now = self._clock()
        canvas_presence = self._clean_expired(canvas_id, now)
        return list(canvas_presence.values())
